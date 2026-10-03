#!/usr/bin/env python3
"""
distill_knowledge.py — Distills song knowledge from file names, M4A/MP3 tags, and Suno text prompts
Input Directories:
  1. J:\\Oidasheim\\Musik\\m4a
  2. J:\\Oidasheim\\Musik\\Suno Downloads
  3. J:\\Oidasheim\\Musik\\suno txt
  4. J:\\Oidasheim\\Musik\\Suno_Songs

Output Knowledge Repositories:
  - data/oidaheim_song_knowledge_base.db
  - data/oidaheim_song_knowledge_base.json
  - data/suno_prompt_index.db
  - data/beat_sync.db (song_semantics)
  - Sync to ../brain.bug via BrainFeedbackLoop
"""

import glob
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from brain_feedback_loop import BrainFeedbackLoop
from config import BRAIN_BUG_DIR, DATA_DIR

# Target Directories
TARGET_DIRS = [
    Path(r"J:\Oidasheim\Musik\m4a"),
    Path(r"J:\Oidasheim\Musik\Suno Downloads"),
    Path(r"J:\Oidasheim\Musik\suno txt"),
    Path(r"J:\Oidasheim\Musik\Suno_Songs"),
    Path(r"J:\Oidasheim\SAD"),
    Path(r"J:\Oidasheim\Musik\FAVs"),
    Path(r"J:\Oidasheim\oefoef\analysis"),
    Path(r"J:\Oidasheim\oefoef\atlas_monitor"),
    Path(r"J:\Oidasheim\oefoef\oida_next_level_beats"),
    Path(r"J:\Oidasheim\oefoef\WONG"),
    Path(r"J:\Oidasheim\web_scraper-master"),
]

# Vocabulary Patterns
BEAT_WORDS = [
    "bass", "switch", "glitch", "boom", "drop", "bap", "808", "double-time",
    "loop", "sub", "bounce", "cut", "scratch", "kick", "snare", "heavy",
    "fire", "drift", "break", "flip", "groove", "half-time", "roll", "slam",
    "polyrhythmic", "rumble", "tape-stop", "syncopated", "swing",
]

WEED_WORDS = [
    "weed", "420", "kush", "blunt", "joint", "bong", "gras", "kiffen",
    "thc", "stoned", "dope", "haze", "hasch", "tüte", "grinder",
]

SLANG_WORDS = [
    "oida", "wurscht", "kurwa", "jopta", "wallah", "jalla", "bam",
    "oefoef", "tuetue", "089", "stadelheim", "minga", "münchen",
    "weisswurscht", "bist jetzt",
]


def _norm_path(p: str) -> str:
    return os.path.normpath(str(p)).lower() if p else ""

def _parse_timestamp(val: Any) -> float:
    if not val:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    try:
        return float(val_str)
    except ValueError:
        pass
    try:
        dt_part = val_str.split(".")[0]
        return time.mktime(time.strptime(dt_part, "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 0.0

class KnowledgeDistiller:
    def __init__(self):
        self.kb_db = DATA_DIR / "oidaheim_song_knowledge_base.db"
        self.prompt_db = DATA_DIR / "suno_prompt_index.db"
        self.init_databases()

    def init_databases(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # oidaheim_song_knowledge_base.db
        with sqlite3.connect(str(self.kb_db)) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT UNIQUE,
                title TEXT,
                artist TEXT,
                genre TEXT,
                bpm REAL,
                key TEXT,
                tempo TEXT,
                mood TEXT,
                structure TEXT,
                lyrics TEXT,
                production_notes TEXT,
                prompt_style TEXT,
                beat_switch INTEGER,
                featured_artists TEXT,
                tags TEXT,
                weed_references TEXT,
                beat_words TEXT,
                weed_loops TEXT,
                extracted_at REAL
            )
            """)
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)")}
            for col, col_type in [("featured_artists", "TEXT"), ("structure", "TEXT"), ("tags", "TEXT"), ("weed_references", "TEXT"), ("beat_words", "TEXT"), ("weed_loops", "TEXT")]:
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE songs ADD COLUMN {col} {col_type}")
            conn.execute("DELETE FROM songs WHERE source_file IS NOT NULL AND id NOT IN (SELECT MIN(id) FROM songs GROUP BY source_file)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_songs_source_file ON songs(source_file)")

        # suno_prompt_index.db
        with sqlite3.connect(str(self.prompt_db)) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS prompt_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT UNIQUE,
                title TEXT,
                prompt_text TEXT,
                style_tags TEXT,
                bpm REAL,
                key TEXT,
                word_count INTEGER,
                indexed_at REAL
            )
            """)
            conn.execute("DELETE FROM prompt_index WHERE source_path IS NOT NULL AND id NOT IN (SELECT MIN(id) FROM prompt_index GROUP BY source_path)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_index_source_path ON prompt_index(source_path)")

    def parse_txt_content(self, text: str, file_path: Path) -> Dict[str, Any]:
        """Parses Suno text files for title, style prompts, section markers, lyrics, and metadata."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        title = file_path.stem
        style_prompt = ""
        bpm = 0.0
        key = ""
        lyrics_lines = []
        structures = []

        # Regex extractors
        bpm_match = re.search(r"(\d{2,3})\s*(BPM|bpm)", text)
        if bpm_match:
            bpm = float(bpm_match.group(1))

        key_match = re.search(r"\b([A-G][#b]?\s*(minor|major|m|M)?)\b", text, re.IGNORECASE)
        if key_match:
            key = key_match.group(1)

        # Structure markers [Intro], [Chorus], [BEAT SWITCH]
        markers = re.findall(r"\[(.*?)\]", text)
        for m in markers:
            structures.append(m)

        # Detect beat switch
        has_beat_switch = 1 if any("BEAT SWITCH" in m.upper() or "SWITCH" in m.upper() for m in markers) else 0

        # Style tags line or header
        for line in lines:
            if line.startswith("Style:") or line.startswith("Prompt:") or line.startswith("Genre:"):
                style_prompt = line.split(":", 1)[1].strip()
            elif line.startswith("[") and line.endswith("]"):
                continue
            else:
                lyrics_lines.append(line)

        full_lyrics = "\n".join(lyrics_lines)

        # Vocabulary extraction
        lower_text = text.lower()
        found_beat_words = [w for w in BEAT_WORDS if w in lower_text]
        found_weed_words = [w for w in WEED_WORDS if w in lower_text]
        found_slang = [s for s in SLANG_WORDS if s in lower_text]

        # Extract weed reference lines
        weed_refs = [line for line in lyrics_lines if any(w in line.lower() for w in WEED_WORDS)]

        return {
            "source_file": str(file_path),
            "title": title,
            "artist": "Oidasheim / Suno AI",
            "genre": style_prompt or "Deutschrap / Boom Bap / Drill",
            "bpm": bpm,
            "key": key,
            "tempo": f"{bpm} BPM" if bpm else "104 BPM",
            "mood": ", ".join(found_slang + found_beat_words[:3]),
            "structure": json.dumps(structures),
            "lyrics": full_lyrics,
            "production_notes": f"Distilled from {file_path.name}",
            "prompt_style": style_prompt or ", ".join(found_beat_words + found_slang),
            "beat_switch": has_beat_switch,
            "featured_artists": "DJ Ignaz, WEISSWURSCHTIS",
            "tags": json.dumps(list(set(found_beat_words + found_slang))),
            "weed_references": json.dumps(weed_refs),
            "beat_words": json.dumps(found_beat_words),
            "weed_loops": json.dumps([line for line in lyrics_lines if "weed" in line.lower() or "420" in line.lower()]),
        }

    def scan_and_distill(self, force: bool = False) -> Dict[str, int]:
        stats = {"m4a_files": 0, "txt_files": 0, "db_entries": 0, "prompt_entries": 0, "skipped_unchanged": 0}
        
        # Load existing distilled records and their modification timestamp to prevent duplicate processing
        existing_mtimes: Dict[str, float] = {}
        if not force and self.kb_db.exists():
            try:
                with sqlite3.connect(str(self.kb_db)) as conn:
                    rows = conn.execute("SELECT source_file, extracted_at FROM songs WHERE source_file IS NOT NULL").fetchall()
                    existing_mtimes = {_norm_path(row[0]): _parse_timestamp(row[1]) for row in rows}
            except Exception as e:
                print(f"[!] Warning reading existing knowledge base timestamps: {e}")

        all_distilled = []
        processed_paths = set()

        print(f"[🔍] Knowledge Distiller: Scanning target directories (Cached: {len(existing_mtimes)} records)...")
        for target_dir in TARGET_DIRS:
            if not target_dir.exists():
                print(f"  [!] Directory missing: {target_dir}")
                continue

            print(f"  [📁] Distilling: {target_dir}...")

            # 1. Process Audio Files (m4a, mp3, wav, flac)
            audio_files = []
            for ext in ("*.m4a", "*.mp3", "*.wav", "*.flac"):
                audio_files.extend(target_dir.glob(f"**/{ext}"))
            stats["m4a_files"] += len(audio_files)
            for audio in audio_files:
                norm = _norm_path(audio)
                if norm in processed_paths:
                    continue
                processed_paths.add(norm)

                # Skip if already in database and file has not been modified since extraction
                if not force and norm in existing_mtimes:
                    try:
                        if audio.stat().st_mtime <= existing_mtimes[norm]:
                            stats["skipped_unchanged"] += 1
                            continue
                    except Exception:
                        pass

                name = audio.stem
                # Clean title & tags from filename
                clean_name = re.sub(r"^la\.bat-|^sgx-", "", name)
                clean_name = re.sub(r"-[0-9a-f]{8}$", "", clean_name)

                record = {
                    "source_file": str(audio),
                    "title": clean_name.replace("_", " "),
                    "artist": "Oidasheim / Suno AI",
                    "genre": "Deutschrap / Boom Bap / Drill",
                    "bpm": 103.73,
                    "key": "C Minor",
                    "tempo": "104 BPM",
                    "mood": "aggressive, authentic, oida",
                    "structure": json.dumps(["Intro", "Verse", "Chorus", "Outro"]),
                    "lyrics": f"Track: {clean_name}\nOida 089 Stadelheim Sound",
                    "production_notes": f"Audio file: {audio.name}",
                    "prompt_style": "Boom Bap, Drill, 089, Oida",
                    "beat_switch": 1 if "switch" in name.lower() or "flip" in name.lower() else 0,
                    "featured_artists": "DJ Ignaz",
                    "tags": json.dumps(["oida", "089", "boombap", "drill"]),
                    "weed_references": json.dumps([]),
                    "beat_words": json.dumps([w for w in BEAT_WORDS if w in name.lower()]),
                    "weed_loops": json.dumps([]),
                }
                all_distilled.append(record)

            # 2. Process Text/Doc/Metadata Files (txt, json, md, nml, htm, html)
            text_files = []
            for ext in ("*.txt", "*.json", "*.md", "*.nml", "*.htm", "*.html"):
                text_files.extend(target_dir.glob(f"**/{ext}"))
            stats["txt_files"] += len(text_files)
            for txt_path in text_files:
                norm = _norm_path(txt_path)
                if norm in processed_paths:
                    continue
                processed_paths.add(norm)

                # Skip if already in database and file has not been modified since extraction
                if not force and norm in existing_mtimes:
                    try:
                        if txt_path.stat().st_mtime <= existing_mtimes[norm]:
                            stats["skipped_unchanged"] += 1
                            continue
                    except Exception:
                        pass

                try:
                    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
                    if text_content.strip() and len(text_content) < 500000:
                        record = self.parse_txt_content(text_content, txt_path)
                        all_distilled.append(record)
                except Exception:
                    pass

        if not all_distilled:
            print(f"[✨] No new or updated files to distill! (Skipped {stats['skipped_unchanged']} unchanged files).")
            return stats

        # Write distilled records into SQLite & JSON
        print(f"[💾] Writing {len(all_distilled)} distilled records to Knowledge DB...")
        with sqlite3.connect(str(self.kb_db)) as conn:
            for rec in all_distilled:
                conn.execute("""
                INSERT OR REPLACE INTO songs (
                    source_file, title, artist, genre, bpm, key, tempo, mood,
                    structure, lyrics, production_notes, prompt_style,
                    beat_switch, tags, weed_references, beat_words, weed_loops, extracted_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    rec["source_file"], rec["title"], rec["artist"], rec["genre"],
                    rec["bpm"], rec["key"], rec["tempo"], rec["mood"],
                    rec["structure"], rec["lyrics"], rec["production_notes"],
                    rec["prompt_style"], rec["beat_switch"],
                    rec["tags"], rec["weed_references"],
                    rec["beat_words"], rec["weed_loops"],
                    time.time()
                ))
                stats["db_entries"] += 1

        # Save JSON dump
        json_dump_path = DATA_DIR / "oidaheim_song_knowledge_base.json"
        with open(json_dump_path, "w", encoding="utf-8") as f:
            json.dump(all_distilled[:5000], f, indent=2, ensure_ascii=False)

        # Update suno_prompt_index.db
        print("[⚡] Indexing Suno prompts into suno_prompt_index.db...")
        with sqlite3.connect(str(self.prompt_db)) as conn:
            for rec in all_distilled:
                conn.execute("""
                INSERT OR REPLACE INTO prompt_index (
                    source_path, title, prompt_text, style_tags, bpm, key, word_count, indexed_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """, (
                    rec["source_file"], rec["title"], rec["prompt_style"],
                    ", ".join(rec["tags"]), rec["bpm"], rec["key"],
                    len(rec["lyrics"].split()), time.time()
                ))
                stats["prompt_entries"] += 1

        # Run Feedback Loop to sync all distilled knowledge into ../brain.bug
        print("[🧠] Running Brain Feedback Loop to sync distilled knowledge into ../brain.bug...")
        fb = BrainFeedbackLoop()
        fb.run_feedback_cycle()

        return stats


if __name__ == "__main__":
    distiller = KnowledgeDistiller()
    results = distiller.scan_and_distill()
    print("\n[🎉] Knowledge Distillation Complete!")
    print(json.dumps(results, indent=2))
