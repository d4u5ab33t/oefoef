import json
import sqlite3
import pytest
from pathlib import Path

from brain_bug_sync import (
    BrainSongRecord,
    init_brain_db,
    load_brain_knowledge,
    extract_m4a_record,
    run_brain_bug_sync,
)


def test_init_brain_db_and_upsert(tmp_path: Path):
    db_path = tmp_path / "test_brain.db"
    conn = init_brain_db(db_path)
    cur = conn.cursor()

    rec = BrainSongRecord(
        source_file=str(tmp_path / "track_01.m4a"),
        title="Test Song",
        artist="Oidasheim Crew",
        genre="Bavarian Phonk",
        lyrics="[Verse]\nOida abgleich lauft.",
        prompt_style="Fast Phonk 160 BPM",
        tags='["phonk", "bass"]',
    )

    cur.execute(
        """
        INSERT INTO songs (
            source_file, title, artist, genre, bpm, key, tempo, mood, structure,
            lyrics, production_notes, prompt_style, beat_switch, tags, extracted_at,
            weed_references, beat_words, weed_loops, featured_artists
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_file) DO UPDATE SET
            title=excluded.title,
            lyrics=excluded.lyrics;
        """,
        (
            rec.source_file, rec.title, rec.artist, rec.genre, rec.bpm, rec.key,
            rec.tempo, rec.mood, rec.structure, rec.lyrics, rec.production_notes,
            rec.prompt_style, rec.beat_switch, rec.tags, rec.extracted_at,
            rec.weed_references, rec.beat_words, rec.weed_loops, rec.featured_artists,
        )
    )
    conn.commit()

    cur.execute("SELECT title, artist, lyrics FROM songs WHERE source_file=?", (rec.source_file,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "Test Song"
    assert row[1] == "Oidasheim Crew"
    assert "Oida" in row[2]
    conn.close()


def test_load_brain_knowledge(tmp_path: Path):
    db_path = tmp_path / "test_knowledge.db"
    conn = init_brain_db(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO songs (source_file, title, artist, lyrics) VALUES (?, ?, ?, ?)",
        ("j:/Oidasheim/Musik/m4a/oida_track.m4a", "Oida Track", "MC Oida", "[Chorus] Boom!")
    )
    conn.commit()
    conn.close()

    lyrics_cache_p = tmp_path / "lyrics_cache.json"
    lyrics_cache_p.write_text(json.dumps({"oida_track": "[Chorus] Boom!"}), encoding="utf-8")

    knowledge = load_brain_knowledge(db_path, lyrics_cache_p, log=lambda _: None)
    assert len(knowledge["by_stem"]) >= 1
    assert "oida_track" in knowledge["by_stem"]
    assert knowledge["lyrics_cache"].get("oida_track") == "[Chorus] Boom!"
