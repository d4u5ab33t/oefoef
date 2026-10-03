#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m4a_suno_tagger.py — Mass-Tagger & Metadaten-Abgleich aus allen Suno-Quellen (*suno*).

Liest und synchronisiert Metadaten, strukturierte Lyrics und hochauflösende Cover-Art
aus allen Suno-Verzeichnissen (J:\\Oidasheim\\Musik\\suno txt, J:\\Oidasheim\\Musik\\Suno Downloads, etc.)
und taggt M4A-Audiodateien unter J:\\Oidasheim\\Musik\\m4a sowie optionale MP3-Dateien.

Features:
  1. Multi-Source Ingestion: Parst sowohl 14.182 Suno .txt-Dateien als auch 10.300+ Suno Downloads
     (MP3 ID3v2-Tags, WOAS-UUIDs, Lyrics, Prompts & .jfif/.jpg Cover-Art).
  2. Intelligentes Metadaten-Merging: Führt Datenquellen nach UUID / Stem zusammen, um lückenlose
     Tags (Text, Style, Prompt, Artist, UUID und Cover) zu garantieren.
  3. "la.bat"-Erkennung: Wenn "la.bat" im Dateinamen, Prompt, Lyrics oder Tags vorkommt,
     wird das Album auf "la.bat" gesetzt und der Titel mit "la.bat - <Titel>" geprefixt.
  4. Cover-Art Embedding: Bettet Cover-Bilder (.jfif / .jpg / .png) direkt in den MP4-Atom 'covr' ein.
  5. Multi-Threaded Ausführung mit Live-Progress und Fehler-Resilienz.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import mutagen
import mutagen.id3
from mutagen.mp4 import MP4, MP4Cover

from config import MUSIK_ROOT, SUNO_TXT_ROOT


DEFAULT_M4A_DIR = Path(r"J:\Oidasheim\Musik\m4a")
DEFAULT_SUNO_TXT_DIR = Path(r"J:\Oidasheim\Musik\suno txt")
DEFAULT_SUNO_DOWNLOADS_DIR = Path(r"J:\Oidasheim\Musik\Suno Downloads")


@dataclass
class SunoMetadata:
    source_txt: str = ""
    file_hint: str = ""
    title: str = ""
    artist: str = ""
    lyrics: str = ""
    prompt_description: str = ""
    tags_string: str = ""
    track_id: str = ""
    duration: float = 0.0
    model_name: str = ""
    cover_path: str = ""
    source_origin: str = "suno_txt"


def parse_suno_txt(txt_path: Path) -> SunoMetadata | None:
    """Parst eine einzelne Suno .txt-Datei."""
    try:
        content = txt_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    lines = content.splitlines()
    file_hint = ""
    title = ""
    artist = ""
    track_id = ""
    lyrics_lines = []
    in_lyrics = False
    raw_api_str = ""
    in_raw_api = False

    for line in lines:
        sline = line.strip()
        if sline.startswith("Metadata for:"):
            file_hint = sline.replace("Metadata for:", "").strip()
        elif sline.startswith("Title:") and not title:
            title = sline.replace("Title:", "").strip()
        elif sline.startswith("Artist:") and not artist:
            artist = sline.replace("Artist:", "").strip()
        elif sline.startswith("Track ID:") and not track_id:
            track_id = sline.replace("Track ID:", "").strip()
        elif sline.startswith("--- Lyrics ---"):
            in_lyrics = True
            in_raw_api = False
            continue
        elif sline.startswith("--- Raw API Response ---"):
            in_lyrics = False
            in_raw_api = True
            continue
        elif sline.startswith("Cover Art URL:") or sline.startswith("--- Musical Information ---"):
            in_lyrics = False

        if in_lyrics:
            lyrics_lines.append(line)
        elif in_raw_api:
            raw_api_str += line + "\n"

    lyrics = "\n".join(lyrics_lines).strip()
    prompt_desc = ""
    tags_str = ""
    duration = 0.0
    model_name = ""

    if raw_api_str.strip():
        try:
            api_data = json.loads(raw_api_str.strip(), strict=False)
            if not title:
                title = api_data.get("title", "")
            if not artist:
                artist = api_data.get("display_name") or api_data.get("handle", "")
            meta = api_data.get("metadata", {}) or {}
            prompt_desc = meta.get("gpt_description_prompt", "") or ""
            tags_str = meta.get("tags", "") or ""
            duration = float(meta.get("duration", 0.0) or 0.0)
            model_name = api_data.get("model_name", "") or ""
            if not lyrics or lyrics.lower() == "[instrumental]":
                prompt_lyrics = meta.get("prompt", "") or ""
                if prompt_lyrics:
                    lyrics = prompt_lyrics
        except Exception:
            pass

    if not file_hint:
        stem = txt_path.stem
        file_hint = stem if stem.endswith(".m4a") else f"{stem}.m4a"

    return SunoMetadata(
        source_txt=str(txt_path),
        file_hint=file_hint,
        title=title,
        artist=artist or "Oidasheim",
        lyrics=lyrics,
        prompt_description=prompt_desc,
        tags_string=tags_str,
        track_id=track_id,
        duration=duration,
        model_name=model_name,
        source_origin="suno_txt",
    )


def scan_suno_downloads_folder(downloads_dir: Path, log=print) -> list[SunoMetadata]:
    """Scannt und extrahiert Metadaten und Cover-Art aus Suno Downloads Unterordnern."""
    if not downloads_dir.exists():
        return []

    try:
        subdirs = [downloads_dir / d for d in os.listdir(downloads_dir) if (downloads_dir / d).is_dir()]
    except Exception as e:
        log(f"[suno_tagger] Warnung beim Lesen von {downloads_dir}: {e}")
        return []

    results: list[SunoMetadata] = []

    def _process_subdir(subdir: Path) -> list[SunoMetadata]:
        local_metas: list[SunoMetadata] = []
        try:
            items = os.listdir(subdir)
        except Exception:
            return local_metas

        cover_files = [subdir / f for f in items if f.lower().endswith((".jfif", ".jpg", ".jpeg", ".png"))]
        default_cover = str(cover_files[0]) if cover_files else ""

        for item in items:
            if not item.lower().endswith(".mp3"):
                continue
            mp3_path = subdir / item
            title = ""
            artist = ""
            lyrics = ""
            prompt_desc = ""
            track_id = ""
            tags_str = ""

            try:
                id3 = mutagen.id3.ID3(str(mp3_path))
                if "TIT2" in id3:
                    title = str(id3["TIT2"])
                if "TPE1" in id3:
                    artist = str(id3["TPE1"])
                if "USLT::eng" in id3:
                    lyrics = str(id3["USLT::eng"])
                elif "USLT" in id3:
                    lyrics = str(id3["USLT"])
                if "COMM::eng" in id3:
                    prompt_desc = str(id3["COMM::eng"])
                elif "COMM" in id3:
                    prompt_desc = str(id3["COMM"])
                if "TCON" in id3:
                    tags_str = str(id3["TCON"])

                # WOAS URL (https://suno.com/song/<UUID>)
                if "WOAS" in id3:
                    woas_val = str(id3["WOAS"])
                    uuid_match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", woas_val)
                    if uuid_match:
                        track_id = uuid_match.group(1)

                # TXXX:comment (id=<UUID>)
                if not track_id and "TXXX:comment" in id3:
                    txxx_val = str(id3["TXXX:comment"])
                    uuid_match = re.search(r"id=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", txxx_val)
                    if uuid_match:
                        track_id = uuid_match.group(1)
            except Exception:
                pass

            if not title:
                title = mp3_path.stem

            # Passendes Cover finden
            item_stem = mp3_path.stem
            cover_path = default_cover
            for cf in cover_files:
                if cf.stem == item_stem or cf.stem.startswith(item_stem):
                    cover_path = str(cf)
                    break

            local_metas.append(
                SunoMetadata(
                    source_txt=str(mp3_path),
                    file_hint=f"{mp3_path.stem}.m4a",
                    title=title,
                    artist=artist or "Oidasheim",
                    lyrics=lyrics,
                    prompt_description=prompt_desc,
                    tags_string=tags_str,
                    track_id=track_id,
                    cover_path=cover_path,
                    source_origin="suno_downloads",
                )
            )

        return local_metas

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        sub_results = executor.map(_process_subdir, subdirs)
        for chunk in sub_results:
            results.extend(chunk)

    return results


def build_suno_index(
    suno_sources: list[Path] | None = None,
    log=print,
) -> dict[str, Any]:
    """Baut einen umfassenden Multi-Source Lookup-Index über alle Suno-Quellen (*suno*)."""
    if suno_sources is None:
        suno_sources = [DEFAULT_SUNO_TXT_DIR, DEFAULT_SUNO_DOWNLOADS_DIR]

    log(f"[suno_tagger] Indexiere alle Suno-Metadaten aus: {[str(p) for p in suno_sources]}...")
    t0 = time.time()

    all_metas: list[SunoMetadata] = []

    for src in suno_sources:
        if not src.exists():
            continue
        if src.is_file() and src.suffix.lower() == ".txt":
            m = parse_suno_txt(src)
            if m:
                all_metas.append(m)
        elif "download" in src.name.lower():
            dl_metas = scan_suno_downloads_folder(src, log=log)
            all_metas.extend(dl_metas)
            log(f"[suno_tagger] {len(dl_metas)} Downloads-Einträge aus {src.name} extrahiert.")
        else:
            txt_files = list(src.glob("*.txt"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
                txt_results = executor.map(parse_suno_txt, txt_files)
                for m in txt_results:
                    if m:
                        all_metas.append(m)
            log(f"[suno_tagger] {len(txt_files)} .txt-Dateien aus {src.name} verarbeitet.")

    by_exact_name: dict[str, SunoMetadata] = {}
    by_stem: dict[str, SunoMetadata] = {}
    by_track_id: dict[str, SunoMetadata] = {}
    by_short_id: dict[str, SunoMetadata] = {}
    by_title: dict[str, SunoMetadata] = {}

    def _merge_meta(existing: SunoMetadata, new: SunoMetadata) -> SunoMetadata:
        """Kombiniert zwei Metadaten-Objekte, um die reichhaltigsten Felder zu erhalten."""
        return SunoMetadata(
            source_txt=existing.source_txt or new.source_txt,
            file_hint=existing.file_hint or new.file_hint,
            title=existing.title or new.title,
            artist=existing.artist if (existing.artist and existing.artist != "Oidasheim") else (new.artist or existing.artist),
            lyrics=existing.lyrics if len(existing.lyrics) >= len(new.lyrics) else new.lyrics,
            prompt_description=existing.prompt_description or new.prompt_description,
            tags_string=existing.tags_string or new.tags_string,
            track_id=existing.track_id or new.track_id,
            duration=existing.duration or new.duration,
            model_name=existing.model_name or new.model_name,
            cover_path=existing.cover_path or new.cover_path,
            source_origin="merged" if existing.source_origin != new.source_origin else existing.source_origin,
        )

    for meta in all_metas:
        # 1. Exact file hint
        if meta.file_hint:
            fh_low = meta.file_hint.lower()
            if fh_low in by_exact_name:
                meta = _merge_meta(by_exact_name[fh_low], meta)
            by_exact_name[fh_low] = meta
            by_stem[Path(fh_low).stem.lower()] = meta

        # 2. Stem
        src_p = Path(meta.source_txt)
        txt_stem = src_p.stem.lower()
        if txt_stem.endswith(".m4a"):
            txt_stem = txt_stem[:-4]
        if txt_stem in by_stem:
            meta = _merge_meta(by_stem[txt_stem], meta)
        by_stem[txt_stem] = meta

        # 3. Track UUID
        if meta.track_id:
            tid_low = meta.track_id.lower()
            if tid_low in by_track_id:
                meta = _merge_meta(by_track_id[tid_low], meta)
            by_track_id[tid_low] = meta
            short_id = tid_low[:8]
            by_short_id[short_id] = meta

        # 4. Hex UUIDs aus Stem extrahieren
        hex_matches = re.findall(r"[0-9a-fA-F]{8}", txt_stem)
        for h in hex_matches:
            h_low = h.lower()
            if h_low in by_short_id:
                by_short_id[h_low] = _merge_meta(by_short_id[h_low], meta)
            else:
                by_short_id[h_low] = meta

        # 5. Titel
        if meta.title:
            clean_t = re.sub(r"[^a-zA-Z0-9]+", " ", meta.title.lower()).strip()
            if clean_t:
                if clean_t in by_title:
                    by_title[clean_t] = _merge_meta(by_title[clean_t], meta)
                else:
                    by_title[clean_t] = meta

    elapsed = time.time() - t0
    log(f"[suno_tagger] Index fertig in {elapsed:.2f}s: {len(by_stem)} Stems, {len(by_short_id)} UUIDs, {len(by_title)} Titel.")

    return {
        "by_exact_name": by_exact_name,
        "by_stem": by_stem,
        "by_track_id": by_track_id,
        "by_short_id": by_short_id,
        "by_title": by_title,
    }


def find_suno_metadata(audio_path: Path, index: dict[str, Any]) -> SunoMetadata | None:
    """Findet deterministisch die passenden Suno-Metadaten für eine Audio-Datei."""
    fname_low = audio_path.name.lower()
    stem_low = audio_path.stem.lower()

    # 1. Exakter Dateiname
    if fname_low in index.get("by_exact_name", {}):
        return index["by_exact_name"][fname_low]

    # 2. Stem Match
    if stem_low in index.get("by_stem", {}):
        return index["by_stem"][stem_low]

    # 3. Short Hex UUID
    hex_matches = re.findall(r"[0-9a-fA-F]{8}", stem_low)
    for h in hex_matches:
        h_low = h.lower()
        if h_low in index.get("by_short_id", {}):
            return index["by_short_id"][h_low]

    # 4. Bereinigter Titel
    clean_stem = re.sub(r"[^a-zA-Z0-9]+", " ", stem_low).strip()
    if clean_stem in index.get("by_title", {}):
        return index["by_title"][clean_stem]

    return None


def is_song_untagged(mp4_obj: MP4) -> bool:
    """Prüft, ob ein Song ungetaggt ist (fehlender Titel, Artist, Lyrics oder Tag-Flag)."""
    tags = mp4_obj.tags
    if not tags:
        return True

    has_title = bool(tags.get("\xa9nam") and tags.get("\xa9nam")[0].strip())
    has_artist = bool(tags.get("\xa9ART") and tags.get("\xa9ART")[0].strip())
    has_lyrics = bool(tags.get("\xa9lyr") and tags.get("\xa9lyr")[0].strip())
    is_brainbug_tagged = bool(tags.get("----:com.oidaheim.brainbug:TAGGED"))

    if not has_title or not has_artist:
        return True
    if not is_brainbug_tagged and not has_lyrics:
        return True

    return False


def check_la_bat_trigger(audio_path: Path, meta: SunoMetadata | None, existing_tags: Any) -> bool:
    """Prüft, ob 'la.bat' im Kontext dieses Songs vorkommt."""
    checks = [
        str(audio_path).lower(),
        audio_path.name.lower(),
    ]
    if meta:
        checks.extend([
            meta.source_txt.lower(),
            meta.title.lower(),
            meta.prompt_description.lower(),
            meta.tags_string.lower(),
            meta.lyrics.lower(),
        ])
    if existing_tags:
        for k, v in existing_tags.items():
            checks.append(str(v).lower())

    for text in checks:
        if "la.bat" in text or "la_bat" in text or "labat" in text:
            return True
    return False


def apply_tags_to_m4a(
    m4a_path: Path,
    meta: SunoMetadata | None,
    force: bool = False,
    embed_cover: bool = True,
) -> tuple[str, str]:
    """Wendet Metadaten, Lyrics und Cover-Art auf eine .m4a-Datei an.
    Gibt (Status, Details) zurück: 'tagged', 'skipped', 'error'."""
    try:
        mp4 = MP4(m4a_path)
    except Exception as e:
        return "error", f"Konnte MP4 nicht öffnen: {e}"

    untagged = is_song_untagged(mp4)
    is_la_bat = check_la_bat_trigger(m4a_path, meta, mp4.tags)
    has_cover = bool(mp4.tags and "covr" in mp4.tags and mp4.tags["covr"])
    needs_cover = embed_cover and bool(meta and meta.cover_path) and not has_cover

    if not untagged and not force and not is_la_bat and not needs_cover:
        return "skipped", "Bereits vollständig getaggt"

    if mp4.tags is None:
        mp4.add_tags()

    # Bestimme Titel
    title = meta.title if (meta and meta.title) else m4a_path.stem
    clean_title = title.strip()
    if is_la_bat:
        if not clean_title.lower().startswith("la.bat"):
            clean_title = f"la.bat - {clean_title}"

    # Bestimme Artist
    artist = (meta.artist if (meta and meta.artist) else "Oidasheim").strip()

    # Bestimme Album
    if is_la_bat:
        album = "la.bat"
    elif meta and meta.tags_string:
        first_tag = meta.tags_string.split(",")[0].strip().title()
        album = first_tag if first_tag else "Suno AI"
    else:
        album = "Suno AI"

    # Setze Standard MP4 Tags
    mp4.tags["\xa9nam"] = [clean_title]
    mp4.tags["\xa9ART"] = [artist]
    mp4.tags["\xa9alb"] = [album]

    if meta and meta.lyrics:
        mp4.tags["\xa9lyr"] = [meta.lyrics]

    if meta and meta.tags_string:
        mp4.tags["\xa9gen"] = [meta.tags_string]

    comment = meta.prompt_description if (meta and meta.prompt_description) else ""
    if comment:
        mp4.tags["\xa9cmt"] = [comment]
        mp4.tags["desc"] = [comment]

    # iTunes Custom Freeform Tags
    if meta and meta.track_id:
        mp4.tags["----:com.apple.iTunes:SUNO_TRACK_ID"] = meta.track_id.encode("utf-8")
    if meta and meta.tags_string:
        mp4.tags["----:com.apple.iTunes:SUNO_STYLE_TAGS"] = meta.tags_string.encode("utf-8")
    if meta and meta.model_name:
        mp4.tags["----:com.apple.iTunes:SUNO_MODEL"] = meta.model_name.encode("utf-8")
    if is_la_bat:
        mp4.tags["----:com.apple.iTunes:SUNO_PROJECT"] = b"la.bat"

    # Cover-Art einbetten
    if embed_cover and meta and meta.cover_path and (force or not has_cover):
        try:
            cov_p = Path(meta.cover_path)
            if cov_p.exists():
                img_data = cov_p.read_bytes()
                fmt = MP4Cover.FORMAT_PNG if cov_p.suffix.lower() == ".png" else MP4Cover.FORMAT_JPEG
                mp4.tags["covr"] = [MP4Cover(img_data, imageformat=fmt)]
        except Exception:
            pass

    mp4.tags["----:com.oidaheim.brainbug:TAGGED"] = b"1"

    try:
        mp4.save()
        return "tagged", f"Title='{clean_title}', Album='{album}', Artist='{artist}'"
    except Exception as e:
        return "error", f"Fehler beim Speichern von {m4a_path.name}: {e}"


def run_tagging_process(
    m4a_dir: Path,
    suno_sources: list[Path] | None = None,
    force: bool = False,
    embed_cover: bool = True,
    workers: int = 32,
    log=print,
) -> dict[str, int]:
    """Haupt-Pipeline zum Abgleich und Taggen aller M4A-Audiodateien."""
    if not m4a_dir.exists():
        log(f"❌ M4A-Verzeichnis nicht gefunden: {m4a_dir}")
        return {"total": 0, "tagged": 0, "skipped": 0, "errors": 0, "la_bat": 0, "cover_embedded": 0}

    index = build_suno_index(suno_sources=suno_sources, log=log)

    log(f"\n[suno_tagger] Scanne M4A-Audiodateien in: {m4a_dir}...")
    m4a_files = sorted(m4a_dir.glob("*.m4a"))
    total_files = len(m4a_files)
    log(f"[suno_tagger] {total_files} .m4a-Dateien gefunden.")

    stats = {
        "total": total_files,
        "tagged": 0,
        "skipped": 0,
        "errors": 0,
        "la_bat": 0,
        "cover_embedded": 0,
    }

    t0 = time.time()
    log(f"[suno_tagger] Starte parallelen Metadaten-Abgleich mit {workers} Worker-Threads...")

    def _tag_single(m4a_p: Path) -> tuple[str, str, bool, bool]:
        meta = find_suno_metadata(m4a_p, index)
        had_cov = bool(meta and meta.cover_path)
        status, details = apply_tags_to_m4a(m4a_p, meta, force=force, embed_cover=embed_cover)
        is_la = "la.bat" in details or check_la_bat_trigger(m4a_p, meta, None)
        return status, details, is_la, had_cov

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_file = {executor.submit(_tag_single, f): f for f in m4a_files}

        for idx, future in enumerate(concurrent.futures.as_completed(future_to_file), 1):
            f = future_to_file[future]
            try:
                status, details, is_la, had_cov = future.result()
                if status == "tagged":
                    stats["tagged"] += 1
                    if is_la:
                        stats["la_bat"] += 1
                    if had_cov:
                        stats["cover_embedded"] += 1
                elif status == "skipped":
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1
            except Exception as e:
                stats["errors"] += 1

            if idx % 1000 == 0 or idx == total_files:
                pct = (idx / total_files) * 100.0
                rate = idx / max(0.1, time.time() - t0)
                log(f"[suno_tagger] Fortschritt: {idx}/{total_files} ({pct:.1f}%) | "
                    f"Getaggt: {stats['tagged']} (la.bat: {stats['la_bat']}, Cover: {stats['cover_embedded']}) | "
                    f"Übersprungen: {stats['skipped']} | Fehler: {stats['errors']} | "
                    f"Tempo: {rate:.1f} Songs/s")

    elapsed = time.time() - t0
    log(f"\n╔════════════════════════════════════════════════════════════════════════════════╗")
    log(f"║ 🎯 SUNO METADATEN-ABGLEICH ABSCHLUSS-REPORT                                    ║")
    log(f"╠════════════════════════════════════════════════════════════════════════════════╣")
    log(f"║ • Gesamte Songs:       {stats['total']:<56} ║")
    log(f"║ • Erfolgreich getaggt: {stats['tagged']:<56} ║")
    log(f"║ • 'la.bat'-Präfixe:    {stats['la_bat']:<56} ║")
    log(f"║ • Cover-Art eingebettet:{stats['cover_embedded']:<55} ║")
    log(f"║ • Bereits getaggt:     {stats['skipped']:<56} ║")
    log(f"║ • Fehler / Warnungen:  {stats['errors']:<56} ║")
    log(f"║ • Benötigte Zeit:      {elapsed:.2f}s ({stats['total']/max(0.1, elapsed):.1f} Songs/s){' ' * 32} ║")
    log(f"╚════════════════════════════════════════════════════════════════════════════════╝")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Multi-Source Suno Lyrics & Metadata Tag Reconciler")
    parser.add_argument("--m4a-dir", type=str, default=str(DEFAULT_M4A_DIR), help="Pfad zum M4A Ordner")
    parser.add_argument(
        "--suno-sources",
        type=str,
        nargs="+",
        default=[str(DEFAULT_SUNO_TXT_DIR), str(DEFAULT_SUNO_DOWNLOADS_DIR)],
        help="Pfade oder Patterns zu Suno Metadaten-Quellen",
    )
    parser.add_argument("--force", action="store_true", help="Bereits getaggte Songs überschreiben")
    parser.add_argument("--no-cover", action="store_true", help="Cover-Art nicht einbetten")
    parser.add_argument("--workers", type=int, default=32, help="Anzahl paralleler Threads")
    args = parser.parse_args()

    sources = [Path(s) for s in args.suno_sources]

    run_tagging_process(
        m4a_dir=Path(args.m4a_dir),
        suno_sources=sources,
        force=args.force,
        embed_cover=not args.no_cover,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
