import sqlite3
import json
import os
from pathlib import Path

brain_dir = Path(r"J:\Oidasheim\brain.bug")
db_path = brain_dir / "oidaheim_song_knowledge_base.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check schema and indexes
cur.execute("PRAGMA index_list('songs')")
print("Indexes on songs table:", cur.fetchall())

# Check sample entries
cur.execute("SELECT id, source_file, title, artist, genre, length(lyrics), tags FROM songs ORDER BY id DESC LIMIT 5")
rows = cur.fetchall()
print("Latest 5 songs in DB:")
for r in rows:
    print(" ", r)

conn.close()

# Check lyrics_cache.json format
lyrics_cache_p = brain_dir / "lyrics_cache.json"
if lyrics_cache_p.exists():
    try:
        with open(lyrics_cache_p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            print(f"lyrics_cache.json entries: {len(data)}, sample keys: {list(data.keys())[:5]}")
    except Exception as e:
        print("lyrics_cache err:", e)
