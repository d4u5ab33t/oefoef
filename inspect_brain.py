import sqlite3
import os
import json

db_path = r"J:\Oidasheim\brain.bug\oidaheim_song_knowledge_base.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print("Tables in oidaheim_song_knowledge_base.db:", tables)
    for t in tables:
        cur.execute(f"SELECT count(*) FROM {t}")
        cnt = cur.fetchone()[0]
        cur.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cur.fetchall()]
        print(f"Table: {t} -> {cnt} rows | cols: {cols}")
        cur.execute(f"SELECT * FROM {t} LIMIT 1")
        sample = cur.fetchone()
        print(f"Sample row in {t}: {str(sample)[:120]}")
    conn.close()

# Also inspect lyrics_cache.json and master_semantics.json
for fname in ["lyrics_cache.json", "master_semantics.json", "suno_prompt_index.db", "alle_songs_extrahiert.csv"]:
    p = os.path.join(r"J:\Oidasheim\brain.bug", fname)
    if os.path.exists(p):
        sz = os.path.getsize(p)
        print(f"File {fname}: {sz} bytes")
