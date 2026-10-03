#!/usr/bin/env python3
"""
main.py — ART DIRECTOR BEAT SYNC VIDEO EDITOR
1-Click: MP3 + Clips -> Epic Music Video
Offline-first, direct-subprocess-ffmpeg, keine Cloud-API, keine GPU-Pflicht.

=== DYNAMISCHE RHYTHMUS-SCHNITTE (DYNAMIC RHYTHM ON-POINT CUTS) ===
Neue Features für präzise, musiksynchrone Videoschnitte:

1. RHYTHM_PATTERN DETECTION:
   - intro: Anfang des Videos
   - expansion: Plötzlich längere Segmente
   - compression: Schnellere Schnitte (kurze Segmente)
   - energy_surge: Hohe Energie-Spitzen
   - buildup: Energie-Aufbau
   - beat_drop: Exakte Beat-Drops (alle 4 Beats)
   - peak: Höhepunkte
   - dense_motion: Hohe Bewegungs-Dichte
   - steady: Gleichmäßige Schnitte

2. SYNC_TYPE (Synchronisations-Genauigkeit):
   - snap_drop: Präziser Schnitt auf Beat-Drops
   - energy_peak: Auf Energie-Höhepunkte
   - on_beat: Exakt auf den Beat
   - syncopated: Leicht gegen den Beat (Synkopation)
   - polyrhythm: Komplexe Rhythm-Patterns
   - breath: Atemraum in ruhigen Sektionen

3. CUT_STYLE (Schnitt-Art):
   - hard_cut: Direkter Schnitt (Intro/Outro)
   - jump_cut: Große Energie-Änderungen
   - push: Energie-Aufbau zwischen Clips
   - break: Energie-Abfall
   - whip: Schnelle Übergänge bei Bewegung
   - dissolve: Sanfter Übergang
   - fade_out: Ausblenden

Nutzung:
    python main.py                              # verarbeitet ALLE mp3s in FAVs/**
    python main.py --song "J:/path/to/song.mp3" # nur einen Song
    python main.py --limit 5                    # nur die ersten 5 (zum Testen)
    python main.py --rebuild-globe              # ClipPool-Cache komplett neu analysieren
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import swag_banners
import audio_analysis
import clip_pool
import db
import mp3_scanner
from config import LOG_DIR, ROOT_DIR

from creative_genome import FilmDNA, build_intent, compile_style, genome_manifest, update_film_dna
from film_genome import compile_film_genome
from timeline_builder import build_timeline


START_BANNER = r'''   
    ██████╗ ███████╗ █████╗ ████████╗    ███████╗██╗   ██╗███╗   ██╗ ██████╗
    ██╔══██╗██╔════╝██╔══██╗╚══██╔══╝    ██╔════╝╚██╗ ██╔╝████╗  ██║██╔════╝
    ██████╔╝█████╗  ███████║   ██║       ███████╗ ╚████╔╝ ██╔██╗ ██║██║
    ██╔══██╗██╔══╝  ██╔══██║   ██║       ╚════██║  ╚██╔╝  ██║╚██╗██║██║
    ██████╔╝███████╗██║  ██║   ██║       ███████║   ██║   ██║ ╚████║╚██████╗
    ╚══════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝       ╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝

🎬 Scanne Clip-Pool in
1-Click: MP3 + Clips → Epic Music Videos
Automatisches Matching von Songs und Clips basierend auf semantischen Eigenschaften.
Musikvideo-Pipeline 1-Click-1-File

██╗    ██╗███████╗   ███████╗██████╗   ██╗████████╗
██║    ██║██╔════╝   ██╔════╝██╔══██╗  ██║╚══██╔══╝
██║ █╗ ██║█████╗     █████╗  ██║  ██║  ██║   ██║
██║███╗██║██╔══╝     ██╔══╝  ██║  ██║  ██║   ██║
╚███╔███╝███████╗    ███████╗██████╔╝  ██║   ██║
 ╚══╝╚══╝ ╚══════╝   ╚══════╝╚═════╝   ╚═╝   ╚═╝'''


def log(msg: str):
    print(msg, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "run.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass  # Logging darf den Run niemals blockieren


def _versioned_output_path(output_dir: Path, song_path: str, platform: str) -> Path:
    """Nächster freier Versionsname (v01, v02, ...) für Vorab-Naming (EDL/Genome)."""
    safe_name = "".join(c for c in Path(song_path).stem if c.isalnum() or c in " _-").strip()
    suffix = "_tiktok" if platform == "tiktok" else ""
    version = 1
    while True:
        candidate = output_dir / f"{safe_name}_beatsync{suffix}_v{version:02d}.mp4"
        if not candidate.exists():
            return candidate
        version += 1


def _finalize_versioned_output(rendered_path: Path, planned_path: Path) -> Path:
    """
    Wird NACH erfolgreichem Rendern aufgerufen. Stellt sicher, dass das fertige Video
    immer unter einem freien, fortlaufenden 'v++'-Namen landet — auch wenn zwischen
    Render-Start und Render-Ende ein anderer Lauf denselben Versionsnamen belegt hat
    (race condition) oder der Renderer selbst einen abweichenden Dateinamen erzeugt hat.
    Verschiebt zusätzlich die Sidecar-Dateien (.edl.json / .genome.json), falls der
    Zielname sich ändert.
    """
    output_dir = planned_path.parent
    stem = planned_path.stem  # z.B. "song_beatsync_v01"
    # Basisname ohne die "_vNN"-Endung ermitteln
    if "_v" in stem and stem.rsplit("_v", 1)[1].isdigit():
        base, _, _ = stem.rpartition("_v")
    else:
        base = stem

    final_path = planned_path
    version = int(stem.rsplit("_v", 1)[1]) if "_v" in stem and stem.rsplit("_v", 1)[1].isdigit() else 1
    # Falls der geplante Pfad inzwischen belegt ist (z.B. Race Condition), nächste freie Version suchen
    while final_path.exists() and final_path.resolve() != rendered_path.resolve():
        version += 1
        final_path = output_dir / f"{base}_v{version:02d}.mp4"

    if rendered_path.resolve() != final_path.resolve():
        rendered_path.replace(final_path)
        # Sidecar-Dateien mitverschieben, falls vorhanden
        for ext in (".edl.json", ".genome.json"):
            old_side = rendered_path.with_suffix(ext) if rendered_path.suffix else Path(str(rendered_path) + ext)
            old_side = planned_path.with_suffix(ext)
            new_side = final_path.with_suffix(ext)
            if old_side.exists() and old_side.resolve() != new_side.resolve():
                old_side.replace(new_side)

    return final_path


def _detect_rhythm_pattern(segment, idx: int, timeline: list) -> str:
    """Detektiert dynamische Rhythmus-Muster basierend auf Segmentabfolge."""
    if idx == 0:
        return "intro"
    
    prev_segment = timeline[idx - 1]
    curr_duration = segment.end_sec - segment.start_sec
    prev_duration = prev_segment.end_sec - prev_segment.start_sec
    
    # Pattern Detection
    duration_ratio = curr_duration / (prev_duration + 0.001)
    
    if duration_ratio > 1.8:
        return "expansion"  # Plötzlich längeres Segment
    elif duration_ratio < 0.6:
        return "compression"  # Kürzeres Segment = schnellere Cuts
    elif segment.target_energy > 0.8:
        return "energy_surge"  # Hohe Energie
    elif segment.target_energy < 0.3:
        return "buildup"  # Aufbau
    elif idx % 4 == 0:
        return "beat_drop"  # Jeden 4. Beat
    elif segment.section_label == "high":
        return "peak"
    elif segment.information_density > 0.7:
        return "dense_motion"  # Bewegungsreich
    else:
        return "steady"


def _calculate_sync_type(segment, idx: int, timeline: list) -> str:
    """Berechnet den Synchronisationstyp für On-Point-Cuts."""
    energy = segment.target_energy
    
    if segment.section_label == "high":
        if energy > 0.85:
            return "snap_drop"  # Präziser Drop-Cut
        else:
            return "energy_peak"
    elif segment.section_label == "low":
        return "breath"
    elif energy > 0.75:
        return "on_beat"  # Exakt auf den Beat
    elif energy > 0.5:
        return "syncopated"  # Leicht gegen den Beat (synkopiert)
    else:
        return "polyrhythm"  # Komplexere Rhythm-Pattern


def _calculate_cut_style(segment, idx: int, timeline: list) -> str:
    """Berechnet den Schnitt-Stil basierend auf Kontext."""
    if idx < 2:
        return "hard_cut"  # Intro: harter Schnitt
    
    if idx >= len(timeline) - 2:
        return "fade_out"  # Outro: Ausblenden
    
    next_segment = timeline[idx + 1] if idx + 1 < len(timeline) else None
    if not next_segment:
        return "hard_cut"
    
    energy_delta = next_segment.target_energy - segment.target_energy
    
    if abs(energy_delta) > 0.4:
        return "jump_cut"  # Große Energie-Änderung
    elif energy_delta > 0.2:
        return "push"  # Energie-Aufbau
    elif energy_delta < -0.2:
        return "break"  # Energie-Abfall
    elif next_segment.information_density > 0.6:
        return "whip"  # Schnelle Übergänge bei Bewegung
    else:
        return "dissolve"  # Sanfter Übergang



def _build_render_script(song: mp3_scanner.SongInfo, timeline: list,
                         style: Any, output_path: Path) -> dict:
    if not timeline:
        raise ValueError("Leere Timeline: kein Render-Skript möglich.")
    sequence = []
    for idx, segment in enumerate(timeline):
        duration = round(segment.end_sec - segment.start_sec, 3)
        if duration <= 0 or not segment.clip_path:
            raise ValueError("Ungültiges Timeline-Segment im Render-Skript.")
        
        # Dynamic Rhythm Sync Pattern Detection
        rhythm_pattern = _detect_rhythm_pattern(segment, idx, timeline)
        sync_type = _calculate_sync_type(segment, idx, timeline)
        cut_style = _calculate_cut_style(segment, idx, timeline)
        
        sequence.append({
            "start": round(segment.start_sec, 3),
            "end": round(segment.end_sec, 3),
            "duration": duration,
            "clip": segment.clip_path,
            "clip_in": round(segment.clip_in_point, 3),
            "effect": segment.transition or "cut",
            "rhythm_sync": sync_type,
            "rhythm_pattern": rhythm_pattern,
            "cut_style": cut_style,
            "section": segment.section_label,
            "theme": segment.theme,
            "target_energy": round(segment.target_energy, 4),
            "information_density": round(segment.information_density, 4),
        })
    script = {
        "version": "synapse-edl-v1",
        "project": song.title or Path(song.path).stem,
        "artist": song.artist,
        "source_audio": song.path,
        "output": str(output_path),
        "style": style.name,
        "sequence": sequence,
    }
    return script


def process_song(song: mp3_scanner.SongInfo, globe: dict, output_dir: Path,
                 style, platform: str = "full", dry_run: bool = False) -> bool:
    log(f"=== Verarbeite: {song.path} ===")
    try:
        audio = audio_analysis.analyze_song(song.path)
    except Exception as e:
        log(f"[main] Audioanalyse fehlgeschlagen, überspringe Song: {e}")
        return False

    song_id = db.upsert_song(
        path=song.path, bpm=audio.bpm, duration_sec=audio.duration_sec,
        tag_vector=song.tag_vector, beatgrid=audio.beat_times, sections=audio.sections,
        music_dna=audio.music_dna,
    )

    recent_used = db.get_recent_usage_ranges()
    timeline = build_timeline(
        song.tag_vector, audio, globe, recent_used, style=style, platform=platform,
    )
    log(f"[main] Timeline mit {len(timeline)} Segmenten gebaut "
        f"(BPM={audio.bpm:.1f}, Dauer={audio.duration_sec:.1f}s).")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = _versioned_output_path(output_dir, song.path, platform)
    render_script = _build_render_script(song, timeline, style, output_path)
    script_path = output_path.with_suffix(".edl.json")
    script_path.write_text(json.dumps(render_script, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"[script] validiertes EDL geschrieben -> {script_path}")

    if dry_run:
        log(f"[main] Dry-run: Rendering übersprungen -> {script_path}")
    else:
        try:
            import renderer
            rendered_path = renderer.render_music_video(timeline, song.path, str(output_path), log=log)
            if not rendered_path or not Path(rendered_path).is_file():
                raise RuntimeError("Renderer meldete keinen gültigen Output.")
            final_path = _finalize_versioned_output(Path(rendered_path), output_path)
            if final_path != output_path:
                log(f"[main] Video final benannt (v++): {output_path.name} -> {final_path.name}")
                output_path = final_path
                script_path = output_path.with_suffix(".edl.json")
        except Exception as e:
            log(f"[main] Rendering fehlgeschlagen: {e}\n{traceback.format_exc()}")
            return False

        for pos, seg in enumerate(timeline):
            db.record_usage(seg.clip_path, song_id, pos,
                             clip_in=seg.clip_in_point,
                             clip_out=seg.clip_in_point + (seg.end_sec - seg.start_sec))

    dna = FilmDNA()
    for segment in timeline:
        clip_meta = globe.get(segment.clip_path)
        if clip_meta is None:
            log(f"[main] Warnung: Clip fehlt im Globe-Cache, überspringe DNA-Update: {segment.clip_path}")
            continue
        intent = build_intent(segment.section_label, segment.target_energy, style, song.tag_vector)
        update_film_dna(dna, intent, clip_meta)
    film_genome = compile_film_genome(song.tag_vector, audio.sections, timeline, style)
    manifest_path = output_path.with_suffix(".genome.json")
    manifest = genome_manifest(song, style, dna)
    manifest["film_genome"] = film_genome.to_dict()
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    db.record_experience(
        song_id,
        {"sections": len(audio.sections), "bpm": audio.bpm},
        {"segments": len(timeline), "style": style.name},
        0.0,
        [],
        "Deterministic resolver: energy, semantic tags, information density and continuity.",
        dna.to_dict(),
    )

    log(f"[main] FERTIG -> {output_path}")
    return True


def main():
    # Swag Banner Integration
    print(swag_banners.get_swag_banner(), flush=True)
    print(START_BANNER, flush=True)
    parser = argparse.ArgumentParser(description="1-Click MP3 + Clips -> Music Video")
    parser.add_argument("--song", type=str, default=None,
                         help="Nur diesen einen Song verarbeiten (Pfad).")
    parser.add_argument("--limit", type=int, default=None,
                         help="Nur die ersten N gefundenen Songs verarbeiten.")
    parser.add_argument("--rebuild-globe", action="store_true",
                         help="Clip-Pool-Cache (flat-globe) komplett neu analysieren.")
    parser.add_argument("--output-dir", type=str,
                         default=str(ROOT_DIR / "output"),
                         help="Zielordner für fertige Videos.")
    parser.add_argument("--style", type=str, default="cinematic",
                        help="Lokales Genome-Style-Paket (z.B. cinematic, trap-pack, horror-pack).")
    parser.add_argument("--platform", choices=("full", "tiktok"), default="full",
                        help="Ausgabeprofil: vollständiger Song oder 15s Short-Form mit Hook/Loop-Cut.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur Analyse, validiertes EDL-JSON und Genome schreiben; kein Video rendern.")
    args = parser.parse_args()

    db.init_db()
    style = compile_style(args.style, ROOT_DIR / "styles")
    log(f"[genome] Style Compiler: {style.name} (deterministisch)")

    log("[main] Lade / aktualisiere Clip-Pool-Index (flat globe) ...")
    globe = {} if args.rebuild_globe else db.load_flat_globe()
    try:
        globe = clip_pool.build_or_update_globe(
            globe, log=log, save_every=25, on_progress=db.save_flat_globe,
        )
    except KeyboardInterrupt:
        log("[main] Abgebrochen (Ctrl+C). Clip-Pool-Fortschritt wurde gesichert, "
            "kein Rendering gestartet. Nächster Lauf setzt beim Clip-Scan fort.")
        sys.exit(130)
    db.save_flat_globe(globe)  # finaler Stand (auch für den "nichts Neues"-Fall)
    log(f"[main] Clip-Pool-Index bereit: {len(globe)} Clips.")

    if args.song:
        target = Path(args.song).resolve()
        all_songs = mp3_scanner.scan_all_songs()
        songs = [s for s in all_songs if Path(s.path).resolve() == target]
        if not songs:
            # Fallback: case-insensitive comparison (Windows-Pfade)
            target_str = str(target).lower()
            songs = [s for s in all_songs if str(Path(s.path).resolve()).lower() == target_str]
        if not songs:
            log(f"[main] Song nicht gefunden: {args.song}")
            log(f"[main] Gescannte Songs ({len(all_songs)}): "
                + ", ".join(s.path for s in all_songs[:10])
                + (" ..." if len(all_songs) > 10 else ""))
            sys.exit(1)
    else:
        songs = mp3_scanner.scan_all_songs()
        if args.limit:
            songs = songs[: args.limit]

    log(f"[main] {len(songs)} Song(s) zur Verarbeitung.")
    output_dir = Path(args.output_dir)
    ok, failed = 0, 0
    for song in songs:
        if process_song(song, globe, output_dir, style, platform=args.platform,
                dry_run=args.dry_run):
            ok += 1
        else:
            failed += 1

    log(f"[main] Abgeschlossen: {ok} erfolgreich, {failed} fehlgeschlagen.")


if __name__ == "__main__":
    main()
