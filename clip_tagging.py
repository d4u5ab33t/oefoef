#!/usr/bin/env python3
"""
clip_tagging.py -- Schreibt "wann/wie/wo/was/warum verwendet"-Metadaten + die
vollen Clip-Analyse-Metainfos (aus dem Globe-Cache, siehe clip_pool.py)
DIREKT in die MP4-Tags der QUELL-Clip-Dateien selbst -- nicht nur ins
.edl.json-Sidecar oder in den Globe-Cache. Laeuft per verlustfreiem ffmpeg-
Remux (-c copy, kein Re-Encode), aufgerufen nach jedem erfolgreichen Render
(siehe main.py::process_song -> tag_clips_after_render()).

WARUM eine eigene Datei statt Teil von renderer.py/main.py: modifiziert
(anders als renderer.py, das nur die AUSGABE beschreibt) tatsaechlich die
Original-Clip-Dateien in der Nutzer-Bibliothek -- bewusst isoliert mit
eigener defensiver Fehlerbehandlung (ein einzelner kaputter/gesperrter/
schreibgeschuetzter Clip darf NIEMALS den Gesamtrender crashen lassen) und
eigenem Ein/Aus-Schalter (config.TAG_SOURCE_CLIPS_ENABLED, main.py
--no-clip-tags).

MP4-CONTAINER-EINSCHRAENKUNG (empirisch verifiziert): ffmpegs mov/mp4-Muxer
akzeptiert nur eine FESTE WHITELIST an Metadata-Keys (title, artist, album,
comment, genre, date, composer, copyright, description, synopsis, show,
episode_id, network, lyrics, grouping, ...). Voellig freie Custom-Keys (z.B.
"oefoef_usage_log") werden beim Muxen OHNE Fehlermeldung STILLSCHWEIGEND
VERWORFEN und tauchen bei ffprobe nie wieder auf (getestet). Deshalb werden
hier bewusst drei bereits unterstuetzte Standard-Keys zweckentfremdet:
  - comment:      kurze, menschenlesbare Ein-Zeilen-Zusammenfassung der
                   LETZTEN Verwendung (auf einen Blick lesbar in jedem
                   Player/Tag-Reader, ohne JSON parsen zu muessen).
  - description:  JSON-Snapshot der STATISCHEN Clip-Analyse-Metainfos aus
                   dem Globe-Cache (tags, motion_score, camera_movement,
                   object_flow, gender_vector, duration, entropy, ...).
  - synopsis:      JSON-Liste der letzten N Verwendungen (wann/wo/wie/warum),
                   neueste zuerst, gekappt bei
                   config.CLIP_TAG_USAGE_LOG_MAX_ENTRIES.
title/artist/... werden bewusst NICHT angefasst, falls der Nutzer dort schon
eigene, sinnvolle Werte gepflegt hat.
"""
import concurrent.futures
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from config import CLIP_TAG_TIMEOUT_SEC, CLIP_TAG_USAGE_LOG_MAX_ENTRIES, CLIP_TAG_WORKERS, FFMPEG_BIN, FFPROBE_BIN


def _probe_duration(path: str) -> float | None:
    try:
        result = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        return float(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _read_existing_usage_log(clip_path: str) -> list:
    """Liest den bereits im Clip gespeicherten "synopsis"-Tag (Verlauf
    frueherer Verwendungen, siehe Moduldoc) und parsed ihn zurueck zu einer
    Liste -- neue Eintraege werden VORNE angehaengt (siehe
    tag_clips_after_render), damit die Historie ueber viele Render-Laeufe
    hinweg erhalten bleibt statt bei jedem Lauf ueberschrieben zu werden.
    Gibt bei fehlendem/kaputtem/nicht-JSON-Tag einfach [] zurueck -- ein
    korrupter alter Tag darf das Schreiben eines neuen niemals blockieren."""
    try:
        result = subprocess.run(
            [FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
             "-show_entries", "format_tags=synopsis", clip_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        data = json.loads(result.stdout)
        raw = data.get("format", {}).get("tags", {}).get("synopsis")
        if not raw:
            return []
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def build_static_clip_info(clip_meta: dict | None) -> dict:
    """Extrahiert die fuer Menschen relevanten Analyse-Metainfos aus einem
    Globe-Cache-Eintrag (siehe clip_pool.analyze_clip) -- bewusst eine
    Teilmenge (keine internen/grossen Felder wie "vector"/"alternative_start_
    points"/"bad_frame_ranges"), damit der "description"-Tag lesbar und
    kompakt bleibt statt den kompletten internen Cache-Eintrag zu spiegeln."""
    if not isinstance(clip_meta, dict):
        return {}
    return {
        "duration_sec": clip_meta.get("duration"),
        "tags": clip_meta.get("tags"),
        "description": clip_meta.get("description"),
        "motion_score": clip_meta.get("motion_score"),
        "camera_movement": clip_meta.get("camera_movement"),
        "object_flow": clip_meta.get("object_flow"),
        "gender_vector": clip_meta.get("gender_vector"),
        "lighting": clip_meta.get("lighting"),
        "color": clip_meta.get("color"),
        "entropy": clip_meta.get("entropy"),
        "playback_ok": clip_meta.get("playback_ok"),
    }


def _build_usage_entry(song: Any, output_path: str, platform: str, position: int,
                       seg: dict) -> dict:
    """Baut EINEN Verwendungs-Log-Eintrag aus einem render_script["sequence"]-
    Segment (siehe main.py::_build_render_script) -- beantwortet WANN (date),
    WO (song/output/platform/position), WAS (section/theme/duration), WIE
    (rhythm_pattern/sync_type/cut_style/target_energy) und WARUM
    (match_reason) dieser Clip an dieser Stelle verwendet wurde."""
    return {
        "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "song": getattr(song, "title", None) or Path(getattr(song, "path", "")).stem,
        "artist": getattr(song, "artist", None) or "Unknown Artist",
        "output": Path(output_path).name,
        "platform": platform,
        "position": position,
        "start_sec": seg.get("start"),
        "duration_sec": seg.get("duration"),
        "section": seg.get("section"),
        "theme": seg.get("theme"),
        "rhythm_pattern": seg.get("rhythm_pattern"),
        "sync_type": seg.get("rhythm_sync"),
        "cut_style": seg.get("cut_style"),
        "target_energy": seg.get("target_energy"),
        "match_reason": seg.get("match_reason"),
    }


def _write_clip_tags(clip_path: str, tags: dict, log) -> bool:
    """Remuxed einen Clip mit neuen Metadata-Tags (-c copy, verlustfrei) in
    eine temporaere Datei IM SELBEN Ordner (damit os.replace() am Ende
    atomar innerhalb desselben Dateisystems bleibt) und ersetzt das Original
    erst NACH einer Plausibilitaetspruefung (Dauer der neuen Datei muss zur
    Originaldauer passen -- Schutz gegen einen kaputten/leeren Remux, der
    sonst den originalen Clip durch Datenmuell ersetzen wuerde). Gibt bei
    JEDEM Fehlschlag False zurueck (nie eine Exception nach oben durchreichen)
    -- der Aufrufer (tag_clips_after_render) behandelt das als "uebersprungen,
    nicht kritisch"."""
    src = Path(clip_path)
    if not src.is_file():
        return False
    tmp_path = src.with_name(f"{src.stem}.oefoef_tagtmp{src.suffix}")
    try:
        orig_duration = _probe_duration(str(src))
        cmd = [FFMPEG_BIN, "-y", "-nostdin", "-i", str(src), "-map", "0", "-c", "copy"]
        for key, val in tags.items():
            if val is None or val == "":
                continue
            cmd += ["-metadata", f"{key}={val}"]
        cmd.append(str(tmp_path))
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=CLIP_TAG_TIMEOUT_SEC)
        if result.returncode != 0 or not tmp_path.is_file() or tmp_path.stat().st_size < 1024:
            log(f"[clip_tagging] Remux fehlgeschlagen fuer {src.name}: "
                f"{(result.stderr or '')[-300:]}")
            return False
        new_duration = _probe_duration(str(tmp_path))
        if (orig_duration is not None and new_duration is not None
                and abs(new_duration - orig_duration) > 0.5):
            log(f"[clip_tagging] Dauer-Mismatch nach Remux ({src.name}): "
                f"original={orig_duration:.2f}s neu={new_duration:.2f}s -> verworfen, Original bleibt unangetastet.")
            return False
        tmp_path.replace(src)  # atomarer Ersatz (gleicher Ordner/gleiches Dateisystem)
        return True
    except Exception as e:
        log(f"[clip_tagging] Fehler beim Tag-Schreiben ({src.name}): {e}")
        return False
    finally:
        try:
            if tmp_path.is_file():
                tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _tag_one_clip(clip_path: str, clip_meta: dict | None, new_entries: list, log) -> bool:
    existing_log = _read_existing_usage_log(clip_path)
    merged_log = (new_entries + existing_log)[:CLIP_TAG_USAGE_LOG_MAX_ENTRIES]

    latest = new_entries[0] if new_entries else (merged_log[0] if merged_log else {})
    comment_parts = [f"Zuletzt: {latest.get('date', '?')} in '{latest.get('song', '?')}'",
                      f"Pos {latest.get('position', '?')}"]
    if latest.get("match_reason"):
        comment_parts.append(f"Grund: {latest['match_reason']}")
    comment = " | ".join(comment_parts)
    if len(new_entries) > 1:
        comment += f" (+{len(new_entries) - 1}x weitere Verwendung(en) in diesem Lauf)"

    static_info = build_static_clip_info(clip_meta)
    tags = {
        "comment": comment,
        "description": json.dumps(static_info, ensure_ascii=False) if static_info else None,
        "synopsis": json.dumps(merged_log, ensure_ascii=False),
    }
    return _write_clip_tags(clip_path, tags, log)


def tag_clips_after_render(timeline: list, globe: dict | None, song: Any,
                           render_script: dict, platform: str, log=None) -> None:
    """Haupteinstieg (aufgerufen aus main.py::process_song NACH einem
    erfolgreichen, nicht-Dry-Run-Render): schreibt fuer jeden im aktuellen
    Render tatsaechlich verwendeten Clip einen aktualisierten Verwendungs-
    verlauf + die vollen Analyse-Metainfos in dessen eigene MP4-Tags.

    Rein additiv/best-effort -- laeuft NACH clip_pool.update_learned_from_
    render() (das den Globe-CACHE pflegt, unabhaengig von dieser Funktion,
    die die tatsaechlichen DATEIEN auf der Platte anfasst). Ein Fehler bei
    EINEM Clip ueberspringt nur diesen Clip (siehe _write_clip_tags), ein
    Fehler in dieser Funktion insgesamt wird vom Aufrufer abgefangen und
    darf den Song niemals als fehlgeschlagen markieren."""
    def _log(msg: str):
        if log:
            log(msg)

    sequence = render_script.get("sequence") or []
    if not sequence:
        return

    # Pro Clip-Pfad ALLE Verwendungen in diesem Render sammeln (ein Clip
    # kann mehrfach in derselben Timeline auftauchen), neueste zuerst.
    entries_by_clip: dict[str, list] = {}
    for pos, seg in enumerate(sequence, start=1):
        clip_path = seg.get("clip")
        if not clip_path:
            continue
        entry = _build_usage_entry(song, render_script.get("output", ""), platform, pos, seg)
        entries_by_clip.setdefault(clip_path, []).insert(0, entry)

    if not entries_by_clip:
        return

    _log(f"[clip_tagging] Schreibe Nutzungs-/Analyse-Tags in {len(entries_by_clip)} Quell-Clip(s) "
         f"(wann/wie/wo/was/warum verwendet) ...")

    ok_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CLIP_TAG_WORKERS) as pool:
        futures = {
            pool.submit(_tag_one_clip, clip_path, (globe or {}).get(clip_path), entries, _log): clip_path
            for clip_path, entries in entries_by_clip.items()
        }
        for future in concurrent.futures.as_completed(futures):
            clip_path = futures[future]
            try:
                if future.result():
                    ok_count += 1
            except Exception as e:
                _log(f"[clip_tagging] Unerwarteter Fehler bei {Path(clip_path).name}: {e}")

    _log(f"[clip_tagging] {ok_count}/{len(entries_by_clip)} Quell-Clip(s) getaggt.")
