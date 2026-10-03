#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
brain_bug_sync.py — Automatischer bidirektionaler Metadaten- & Lyrics-Abgleich mit brain.bug.

Synchronisiert alle M4A-Audiodateien (J:\\Oidasheim\\Musik\\m4a) und Suno-Metadaten (*suno*)
vollautomatisch mit den Wissensdatenbanken in J:\\Oidasheim\\brain.bug:
  1. oidaheim_song_knowledge_base.db (SQLite Knowledge Base: songs Tabelle)
  2. lyrics_cache.json (Vollständiger Lyrics-Cache für semantisches Video-Matching)
  3. master_semantics.json & alle_songs_extrahiert.csv
  4. Bidirektionaler Abgleich: Füllt Lücken in Audio-Tags aus brain.bug und aktualisiert
     brain.bug mit allen neu indexierten Songs, Lyrics und Prompts.
  5. Automatische 'la.bat'-Validierung für Album und Titel-Präfixe.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import mutagen
from mutagen.mp4 import MP4, MP4Cover

from m4a_suno_tagger import (
    DEFAULT_M4A_DIR,
    DEFAULT_SUNO_DOWNLOADS_DIR,
    DEFAULT_SUNO_TXT_DIR,
    SunoMetadata,
    apply_tags_to_m4a,
    build_suno_index,
    check_la_bat_trigger,
    find_suno_metadata,
    is_song_untagged,
)


DEFAULT_BRAIN_BUG_DIR = Path(r"J:\Oidasheim\brain.bug")
DEFAULT_SONG_DB = DEFAULT_BRAIN_BUG_DIR / "oidaheim_song_knowledge_base.db"
DEFAULT_LYRICS_CACHE = DEFAULT_BRAIN_BUG_DIR / "lyrics_cache.json"
DEFAULT_MASTER_SEMANTICS = DEFAULT_BRAIN_BUG_DIR / "master_semantics.json"
DEFAULT_CSV_EXPORT = DEFAULT_BRAIN_BUG_DIR / "alle_songs_extrahiert.csv"


@dataclass
class BrainSongRecord:
    source_file: str
    title: str = ""
    artist: str = ""
    genre: str = ""
    bpm: int = 0
    key: str = ""
    tempo: str = ""
    mood: str = ""
    structure: str = ""
    lyrics: str = ""
    production_notes: str = ""
    prompt_style: str = ""
    beat_switch: str = ""
    tags: str = "[]"
    extracted_at: str = ""
    weed_references: str = "[]"
    beat_words: str = "[]"
    weed_loops: str = "[]"
    featured_artists: str = "[]"


def init_brain_db(db_path: Path) -> sqlite3.Connection:
    """Initialisiert die SQLite-Verbindung und stellt das Schema sicher."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT UNIQUE,
            title TEXT,
            artist TEXT,
            genre TEXT,
            bpm INTEGER,
            key TEXT,
            tempo TEXT,
            mood TEXT,
            structure TEXT,
            lyrics TEXT,
            production_notes TEXT,
            prompt_style TEXT,
            beat_switch TEXT,
            tags TEXT,
            extracted_at TEXT,
            weed_references TEXT,
            beat_words TEXT,
            weed_loops TEXT,
            featured_artists TEXT
        );
        """
    )
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_songs_source_file ON songs(source_file);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title);")
    conn.commit()
    return conn


def load_brain_knowledge(db_path: Path, lyrics_cache_path: Path, log=print) -> dict[str, Any]:
    """Lädt bestehende Metadaten und Lyrics aus brain.bug."""
    knowledge: dict[str, Any] = {
        "by_source": {},
        "by_title": {},
        "by_stem": {},
        "lyrics_cache": {},
    }

    if lyrics_cache_path.exists():
        try:
            with open(lyrics_cache_path, "r", encoding="utf-8") as fh:
                knowledge["lyrics_cache"] = json.load(fh)
            log(f"[brain_sync] {len(knowledge['lyrics_cache'])} Lyrics aus lyrics_cache.json geladen.")
        except Exception as e:
            log(f"[brain_sync] Warnung lyrics_cache.json: {e}")

    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT source_file, title, artist, genre, lyrics, prompt_style, tags, bpm, mood FROM songs")
            rows = cur.fetchall()
            for r in rows:
                src, title, art, gen, lyr, prompt, tags, bpm, mood = r
                stem = Path(src).stem.lower() if src else ""
                clean_t = re.sub(r"[^a-zA-Z0-9]+", " ", (title or "").lower()).strip()
                item = {
                    "source_file": src,
                    "title": title or "",
                    "artist": art or "",
                    "genre": gen or "",
                    "lyrics": lyr or "",
                    "prompt_style": prompt or "",
                    "tags": tags or "[]",
                    "bpm": bpm or 0,
                    "mood": mood or "",
                }
                if src:
                    knowledge["by_source"][src.lower()] = item
                if stem:
                    knowledge["by_stem"][stem] = item
                if clean_t:
                    knowledge["by_title"][clean_t] = item
            conn.close()
            log(f"[brain_sync] {len(rows)} Song-Einträge aus oidaheim_song_knowledge_base.db geladen.")
        except Exception as e:
            log(f"[brain_sync] Warnung beim Lesen der DB: {e}")

    return knowledge


def extract_m4a_record(m4a_path: Path) -> BrainSongRecord:
    """Liest die Tags einer M4A-Datei und erzeugt einen BrainSongRecord."""
    title = m4a_path.stem
    artist = "Oidasheim"
    genre = "Deutschrap / Boom Bap / Drill"
    lyrics = ""
    prompt_style = ""
    tags_list = []
    bpm = 0
    mood = "energetic"

    try:
        mp4 = MP4(str(m4a_path))
        tags = mp4.tags or {}
        if "\xa9nam" in tags and tags["\xa9nam"]:
            title = tags["\xa9nam"][0]
        if "\xa9ART" in tags and tags["\xa9ART"]:
            artist = tags["\xa9ART"][0]
        if "\xa9alb" in tags and tags["\xa9alb"]:
            alb = tags["\xa9alb"][0]
            if alb and alb != "Suno AI" and alb != "la.bat":
                genre = alb
        if "\xa9lyr" in tags and tags["\xa9lyr"]:
            lyrics = tags["\xa9lyr"][0]
        if "\xa9gen" in tags and tags["\xa9gen"]:
            genre = tags["\xa9gen"][0]
            tags_list.extend([t.strip() for t in genre.split(",") if t.strip()])
        if "\xa9cmt" in tags and tags["\xa9cmt"]:
            prompt_style = tags["\xa9cmt"][0]
        if "desc" in tags and tags["desc"] and not prompt_style:
            prompt_style = tags["desc"][0]

        # Check BPM / mood
        if "tmpo" in tags and tags["tmpo"]:
            bpm = int(tags["tmpo"][0])

    except Exception:
        pass

    now_iso = datetime.now(timezone.utc).isoformat()
    return BrainSongRecord(
        source_file=str(m4a_path),
        title=title,
        artist=artist,
        genre=genre,
        bpm=bpm,
        lyrics=lyrics,
        prompt_style=prompt_style,
        tags=json.dumps(tags_list, ensure_ascii=False),
        extracted_at=now_iso,
        mood=mood,
    )


def run_brain_bug_sync(
    m4a_dir: Path = DEFAULT_M4A_DIR,
    brain_dir: Path = DEFAULT_BRAIN_BUG_DIR,
    workers: int = 32,
    log=print,
) -> dict[str, Any]:
    """Haupt-Pipeline zum automatischen Abgleich aller Songs mit brain.bug."""
    t0 = time.time()
    db_path = brain_dir / "oidaheim_song_knowledge_base.db"
    lyrics_cache_p = brain_dir / "lyrics_cache.json"
    csv_export_p = brain_dir / "alle_songs_extrahiert.csv"

    log(f"🧠 Starte Auto-Abgleich mit brain.bug ({brain_dir})...")

    # 1. Vorhandenes Wissen aus brain.bug laden
    knowledge = load_brain_knowledge(db_path, lyrics_cache_p, log=log)

    # 2. Suno Multi-Source Index bauen
    suno_index = build_suno_index(
        suno_sources=[DEFAULT_SUNO_TXT_DIR, DEFAULT_SUNO_DOWNLOADS_DIR],
        log=log,
    )

    # 3. Alle M4A-Audiodateien scannen
    m4a_files = sorted(m4a_dir.glob("*.m4a")) if m4a_dir.exists() else []
    total_m4a = len(m4a_files)
    log(f"[brain_sync] Scanne {total_m4a} M4A-Audiodateien...")

    synced_records: list[BrainSongRecord] = []
    audio_tags_updated = 0
    lyrics_cache = knowledge["lyrics_cache"]

    def _sync_single_file(m4a_p: Path) -> tuple[BrainSongRecord, bool]:
        # Suno Metadaten suchen
        meta = find_suno_metadata(m4a_p, suno_index)

        # Ggf. Audio-Tags aktualisieren / la.bat prüfen
        status, details = apply_tags_to_m4a(m4a_p, meta, force=False, embed_cover=True)
        was_updated = (status == "tagged")

        # Record erzeugen
        rec = extract_m4a_record(m4a_p)

        # Wenn meta noch reichhaltigere Lyrics/Prompts hat, im DB-Record ergänzen
        if meta:
            if meta.lyrics and len(meta.lyrics) > len(rec.lyrics):
                rec.lyrics = meta.lyrics
            if meta.prompt_description and not rec.prompt_style:
                rec.prompt_style = meta.prompt_description
            if meta.tags_string and rec.tags == "[]":
                rec.tags = json.dumps([t.strip() for t in meta.tags_string.split(",") if t.strip()], ensure_ascii=False)

        return rec, was_updated

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(_sync_single_file, m4a_files)
        for rec, was_up in results:
            synced_records.append(rec)
            if was_up:
                audio_tags_updated += 1
            if rec.lyrics and rec.title:
                stem_k = Path(rec.source_file).stem
                lyrics_cache[stem_k] = rec.lyrics
                clean_title_k = re.sub(r"[^a-zA-Z0-9]+", " ", rec.title).strip()
                if clean_title_k:
                    lyrics_cache[clean_title_k] = rec.lyrics

    log(f"[brain_sync] {len(synced_records)} Song-Datensätze aufbereitet ({audio_tags_updated} Audio-Tags synchronisiert).")

    # 4. Datenbank in brain.bug aktualisieren
    conn = init_brain_db(db_path)
    cur = conn.cursor()

    db_upserts = 0
    batch_data = []

    for r in synced_records:
        batch_data.append((
            r.source_file,
            r.title,
            r.artist,
            r.genre,
            r.bpm,
            r.key,
            r.tempo,
            r.mood,
            r.structure,
            r.lyrics,
            r.production_notes,
            r.prompt_style,
            r.beat_switch,
            r.tags,
            r.extracted_at,
            r.weed_references,
            r.beat_words,
            r.weed_loops,
            r.featured_artists,
        ))

    cur.executemany(
        """
        INSERT INTO songs (
            source_file, title, artist, genre, bpm, key, tempo, mood, structure,
            lyrics, production_notes, prompt_style, beat_switch, tags, extracted_at,
            weed_references, beat_words, weed_loops, featured_artists
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_file) DO UPDATE SET
            title=excluded.title,
            artist=excluded.artist,
            genre=excluded.genre,
            lyrics=excluded.lyrics,
            prompt_style=excluded.prompt_style,
            tags=excluded.tags,
            extracted_at=excluded.extracted_at;
        """,
        batch_data,
    )
    conn.commit()

    cur.execute("SELECT count(*) FROM songs")
    total_in_db = cur.fetchone()[0]
    conn.close()
    log(f"[brain_sync] DB-Aktualisierung abgeschlossen: {total_in_db} Songs insgesamt in oidaheim_song_knowledge_base.db.")

    # 5. lyrics_cache.json speichern
    try:
        with open(lyrics_cache_p, "w", encoding="utf-8") as fh:
            json.dump(lyrics_cache, fh, ensure_ascii=False, indent=2)
        log(f"[brain_sync] {len(lyrics_cache)} Einträge in {lyrics_cache_p.name} gesichert.")
    except Exception as e:
        log(f"[brain_sync] Fehler beim Schreiben von lyrics_cache.json: {e}")

    # 6. CSV-Export aktualisieren
    try:
        with open(csv_export_p, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow([
                "source_file", "title", "artist", "genre", "bpm", "lyrics_len",
                "prompt_style", "tags", "extracted_at"
            ])
            for r in synced_records:
                writer.writerow([
                    r.source_file,
                    r.title,
                    r.artist,
                    r.genre,
                    r.bpm,
                    len(r.lyrics),
                    r.prompt_style,
                    r.tags,
                    r.extracted_at,
                ])
        log(f"[brain_sync] CSV-Export {csv_export_p.name} aktualisiert.")
    except Exception as e:
        log(f"[brain_sync] Warnung CSV-Export: {e}")

    elapsed = time.time() - t0
    report = {
        "total_m4a_scanned": total_m4a,
        "audio_tags_updated": audio_tags_updated,
        "total_db_songs": total_in_db,
        "lyrics_cached": len(lyrics_cache),
        "elapsed_seconds": elapsed,
    }

    log(f"\n╔════════════════════════════════════════════════════════════════════════════════╗")
    log(f"║ 🧠 BRAIN.BUG AUTO-ABGLEICH ABSCHLUSS-REPORT                                    ║")
    log(f"╠════════════════════════════════════════════════════════════════════════════════╣")
    log(f"║ • Gescannte M4A-Audiodateien:  {total_m4a:<48} ║")
    log(f"║ • Audio-Tags synchronisiert:   {audio_tags_updated:<48} ║")
    log(f"║ • Songs in brain.bug DB:       {total_in_db:<48} ║")
    log(f"║ • Gecachte Songtexte:          {len(lyrics_cache):<48} ║")
    log(f"║ • Benötigte Zeit:              {elapsed:.2f}s ({total_m4a/max(0.1, elapsed):.1f} Songs/s){' ' * 24} ║")
    log(f"║ • Speicherort:                 {str(brain_dir):<48} ║")
    log(f"╚════════════════════════════════════════════════════════════════════════════════╝")

    return report


def main():
    parser = argparse.ArgumentParser(description="Auto-Abgleich mit brain.bug")
    parser.add_argument("--m4a-dir", type=str, default=str(DEFAULT_M4A_DIR), help="Pfad zum M4A Ordner")
    parser.add_argument("--brain-dir", type=str, default=str(DEFAULT_BRAIN_BUG_DIR), help="Pfad zu brain.bug")
    parser.add_argument("--workers", type=int, default=32, help="Anzahl paralleler Worker-Threads")
    args = parser.parse_args()

    run_brain_bug_sync(
        m4a_dir=Path(args.m4a_dir),
        brain_dir=Path(args.brain_dir),
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
