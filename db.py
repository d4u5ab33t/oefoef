"""
db.py — Persistenz: beat_sync.db (SQLite) + libsync-flat-globe.db.json (Clip-Cache)

beat_sync.db enthält:
  songs(id, path, bpm, duration, tag_vector_json, analyzed_at)
  usage_history(clip_id, song_id, used_at, position_in_render)

libsync-flat-globe.db.json ist ein flacher Cache:
  { "<clip_path>": {"hash": ..., "duration":..., "tags":[...], "vector":[...],
                     "face_score":..., "motion_score":..., "analyzed_at":...} }
Der Name "flat globe" deutet auf einen flachen (nicht hierarchischen) globalen
Index aller Clips — genau dafür wird er hier verwendet, unabhängig davon in
welchem Unterordner von CLIP_POOL_DIR ein Clip liegt.
"""
import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from config import BEAT_SYNC_DB, FLAT_GLOBE_JSON

_GLOBE_LOCK = threading.RLock()


# ── SQLite: Songs + Usage-History ────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    path            TEXT UNIQUE NOT NULL,
    bpm             REAL,
    duration_sec    REAL,
    tag_vector_json TEXT,
    beatgrid_json   TEXT,
    sections_json   TEXT,
    music_dna_json  TEXT,
    analyzed_at     REAL
);

CREATE TABLE IF NOT EXISTS usage_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_path           TEXT NOT NULL,
    song_id             INTEGER,
    used_at             REAL,
    position_in_render  INTEGER,
    clip_in             REAL,
    clip_out            REAL,
    FOREIGN KEY(song_id) REFERENCES songs(id)
);

CREATE INDEX IF NOT EXISTS idx_usage_clip ON usage_history(clip_path);

CREATE TABLE IF NOT EXISTS experiences (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id         INTEGER NOT NULL,
    situation_json  TEXT NOT NULL,
    decision_json   TEXT NOT NULL,
    reward          REAL,
    alternatives_json TEXT,
    why             TEXT,
    film_dna_json   TEXT,
    created_at      REAL NOT NULL,
    FOREIGN KEY(song_id) REFERENCES songs(id)
);

-- Gelernte Song-Semantik aus Traktor-Tracklisten (*.nml / *.htm / *.html):
-- Titel/Artist/BPM/Key aus den Tags + vollstaendig strukturierte Lyrics
-- (Section-Marker, Beat-Switches/Movements, SFX, Ad-libs, Slang, Mood-Tags).
-- Siehe song_semantics.py fuer den Parser/Learner.
CREATE TABLE IF NOT EXISTS song_semantics (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    path                TEXT UNIQUE NOT NULL,
    source_file         TEXT,
    title               TEXT,
    artist              TEXT,
    bpm                 REAL,
    musical_key         TEXT,
    sections_json       TEXT,
    movements_json      TEXT,
    mood_tags_json      TEXT,
    slang_json          TEXT,
    beat_switch_count   INTEGER,
    sentiment           REAL,
    dominant_style      TEXT,
    energy_character    TEXT,
    style_weights_json  TEXT,
    mc_gender           TEXT,
    visual_objects_json TEXT,
    cluster_mask        INTEGER DEFAULT 0,
    prompt_description  TEXT,
    tension_score       REAL DEFAULT 0.5,
    punchline_density   REAL DEFAULT 0.0,
    learned_at          REAL NOT NULL
);
"""


@contextmanager
def get_conn():
    """Öffnet eine SQLite-Verbindung mit WAL-Journaling (crash-sicherer als
    das Standard-Rollback-Journal) und Busy-Timeout gegen "database is locked".

    Nutzt bewusst die eingebaute Transaktionsverwaltung von Python (conn.commit()
    / conn.rollback()) statt manueller "BEGIN"/"COMMIT"-SQL-Statements: Letzteres
    bricht, sobald irgendwo im Block executescript() aufgerufen wird (executescript
    committet intern selbst und beendet die Transaktion vorzeitig -> ein
    nachfolgendes manuelles COMMIT/ROLLBACK findet dann keine aktive Transaktion
    mehr und wirft "cannot commit/rollback - no transaction is active").
    conn.commit()/conn.rollback() sind dagegen immer sicher aufrufbar, auch wenn
    gerade keine Transaktion offen ist."""
    BEAT_SYNC_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(BEAT_SYNC_DB), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")   # WAL + NORMAL = crash-safe, aber schneller als FULL
    conn.execute("PRAGMA busy_timeout=30000;")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        songs_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(songs)")
        }
        if songs_columns and "path" not in songs_columns:
            _migrate_legacy_songs(conn, songs_columns)
        conn.executescript(SCHEMA)
        songs_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(songs)")
        }
        for column, definition in (
            ("duration_sec", "REAL"),
            ("tag_vector_json", "TEXT"),
            ("beatgrid_json", "TEXT"),
            ("sections_json", "TEXT"),
            ("music_dna_json", "TEXT"),
            ("analyzed_at", "REAL"),
        ):
            if column not in songs_columns:
                conn.execute(f"ALTER TABLE songs ADD COLUMN {column} {definition}")

        usage_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(usage_history)")
        }
        for column, definition in (
            ("clip_in", "REAL"),
            ("clip_out", "REAL"),
        ):
            if column not in usage_columns:
                conn.execute(f"ALTER TABLE usage_history ADD COLUMN {column} {definition}")

        # Style/Cut-Logic-Grundlage (siehe song_semantics.py)
        semantics_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(song_semantics)")
        }
        for column, definition in (
            ("dominant_style", "TEXT"),
            ("energy_character", "TEXT"),
            ("style_weights_json", "TEXT"),
            ("mc_gender", "TEXT"),
            ("visual_objects_json", "TEXT"),
            ("cluster_mask", "INTEGER DEFAULT 0"),
            ("prompt_description", "TEXT"),
            ("tension_score", "REAL DEFAULT 0.5"),
            ("punchline_density", "REAL DEFAULT 0.0"),
        ):
            if column not in semantics_columns:
                conn.execute(f"ALTER TABLE song_semantics ADD COLUMN {column} {definition}")



def _migrate_legacy_songs(conn, columns: set):
    """Übernimmt das frühere Musikdatenbank-Schema in die Projektstruktur."""
    if "file_path" not in columns:
        raise RuntimeError(
            "Die Tabelle songs hat ein unbekanntes Schema und kann nicht migriert werden."
        )

    conn.execute("ALTER TABLE songs RENAME TO songs_legacy")
    conn.execute("ALTER TABLE usage_history RENAME TO usage_history_legacy")
    conn.executescript(SCHEMA)
    conn.execute(
        """INSERT INTO songs (id, path, bpm, duration_sec, analyzed_at)
           SELECT id, file_path, bpm, time_sec, strftime('%s', 'now')
           FROM songs_legacy
           WHERE file_path IS NOT NULL AND file_path != ''
           ON CONFLICT(path) DO NOTHING"""
    )
    conn.execute(
        """INSERT INTO usage_history (id, clip_path, song_id, used_at, position_in_render)
           SELECT id, clip_path, song_id, used_at, position_in_render
           FROM usage_history_legacy"""
    )
    conn.execute("DROP TABLE usage_history_legacy")
    conn.execute("DROP TABLE songs_legacy")


def upsert_song(path: str, bpm: float, duration_sec: float,
                tag_vector: list, beatgrid: list, sections: list,
                music_dna: dict | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
                """INSERT INTO songs (path, bpm, duration_sec, tag_vector_json,
                                              beatgrid_json, sections_json, music_dna_json,
                                              analyzed_at)
                    VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET
                    bpm=excluded.bpm,
                    duration_sec=excluded.duration_sec,
                    tag_vector_json=excluded.tag_vector_json,
                    beatgrid_json=excluded.beatgrid_json,
                    sections_json=excluded.sections_json,
                    music_dna_json=excluded.music_dna_json,
                    analyzed_at=excluded.analyzed_at
               RETURNING id""",
            (path, bpm, duration_sec, json.dumps(tag_vector),
            json.dumps(beatgrid), json.dumps(sections), json.dumps(music_dna or {}),
             time.time()),
        )
        return cur.fetchone()[0]


# TOTE FUNKTION ENTFERNT (Deep-Wiring-Audit): get_recent_usage() (nur
# clip_path-Liste) wurde durch get_recent_usage_ranges() unten ersetzt
# (liefert zusätzlich clip_in/clip_out für die PARTIELLE Anti-Repeat-Sperre,
# siehe timeline_builder.py) -- main.py ruft ausschließlich noch
# get_recent_usage_ranges() auf. Die alte Variante hatte keinen Aufrufer mehr.

def get_clip_cooldowns(seconds: float = 60.0) -> set[str]:
    """Return clips used within the cooldown window, newest usage per clip."""
    cutoff = time.time() - max(0.0, seconds)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT clip_path FROM usage_history WHERE used_at >= ?",
            (cutoff,),
        ).fetchall()
    return {row[0] for row in rows}


def record_usage(clip_path: str, song_id: int, position_in_render: int,
                 clip_in: float | None = None, clip_out: float | None = None):
    """clip_in/clip_out = tatsächlich genutzter Zeitbereich im Quell-Clip
    (nicht der ganze Clip) — Grundlage für die partielle Anti-Repeat-Sperre
    in timeline_builder.py."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO usage_history (clip_path, song_id, used_at, position_in_render,
                                          clip_in, clip_out)
               VALUES (?,?,?,?,?,?)""",
            (clip_path, song_id, time.time(), position_in_render, clip_in, clip_out),
        )


def record_usage_many(records: list) -> None:
    """Batch-Variante von record_usage(): schreibt ALLE Segmente einer Timeline
    (typischerweise Dutzende bis Hunderte pro Song) über EINE einzige
    SQLite-Verbindung/Transaktion statt pro Segment eine eigene Connection zu
    öffnen/committen/schließen. Der alte Loop-Aufruf von record_usage() pro
    Segment war der dominante DB-Overhead in main.py::process_song bei Videos
    mit vielen Cuts. `records` ist eine Liste von Dicts mit den Keys
    clip_path, song_id, position_in_render, clip_in, clip_out."""
    if not records:
        return
    now = time.time()
    rows = [
        (r["clip_path"], r["song_id"], now, r["position_in_render"],
         r.get("clip_in"), r.get("clip_out"))
        for r in records
    ]
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO usage_history (clip_path, song_id, used_at, position_in_render,
                                          clip_in, clip_out)
               VALUES (?,?,?,?,?,?)""",
            rows,
        )


def get_recent_usage_ranges(limit: int = 500) -> list:
    """Letzte N genutzte Clip-AUSSCHNITTE (neueste zuerst) — für die partielle
    Anti-Repeat-Sperre: sperrt nur den tatsächlich genutzten Zeitbereich eines
    Clips, nicht den ganzen Clip (siehe timeline_builder._pick_start_point)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT clip_path, clip_in, clip_out, used_at FROM usage_history
               ORDER BY used_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {"clip_path": r[0], "clip_in": r[1], "clip_out": r[2], "used_at": r[3]}
        for r in rows
    ]


def get_clip_cooldown_ranges(seconds: float = 60.0) -> dict:
    """Wie get_clip_cooldowns, aber mit den konkreten genutzten Zeitbereichen
    statt nur den Clip-Pfaden — ebenfalls Grundlage der partiellen Sperre."""
    cutoff = time.time() - max(0.0, seconds)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT clip_path, clip_in, clip_out FROM usage_history
               WHERE used_at >= ? AND clip_in IS NOT NULL AND clip_out IS NOT NULL""",
            (cutoff,),
        ).fetchall()
    ranges: dict = {}
    for clip_path, clip_in, clip_out in rows:
        ranges.setdefault(clip_path, []).append((clip_in, clip_out))
    return ranges


# TOTE FUNKTION ENTFERNT (Deep-Wiring-Audit): total_uses() (Einzel-Clip,
# eine DB-Verbindung PRO Aufruf) wurde durch total_uses_many() unten ersetzt
# (eine Verbindung für ALLE Clips auf einmal, siehe dessen Docstring-Prinzip
# analog zu record_usage_many()) -- keine verbliebenen Aufrufer der
# Einzel-Variante in der Pipeline.

def total_uses_many(clip_paths) -> dict:
    """Lädt die Nutzungshäufigkeit mehrerer Clips mit einer Verbindung.
    Verhindert den SQLite-Parameter-Überlauf (too many SQL variables) bei großen
    Clip-Pools (> 32k Clips), indem alle Nutzungen aggregiert und im Speicher
    zugeordnet werden."""
    paths_set = set(clip_paths)
    if not paths_set:
        return {}
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT clip_path, COUNT(*)
               FROM usage_history
               GROUP BY clip_path"""
        ).fetchall()
    return {path: count for path, count in rows if path in paths_set}


def get_session_locked_clips(
    usable_clips: dict | list | set,
    lock_ratio: float = 0.667,
    cooldown_hours: float = 48.0,
    max_global_uses: int = 5
) -> set[str]:
    """Ermittelt die 2/3-Pool-Sperre über Sessions hinweg.
    Sperrt die zuletzt und am häufigsten genutzten Clips persistent über SQLite/Session-Historie,
    sodass garantiert mindestens 1/3 (1.0 - lock_ratio) frische, ungenutzte Clips
    rotieren und maximale Vielfalt gewährleistet ist."""
    if not usable_clips:
        return set()

    usable_set = set(usable_clips.keys()) if isinstance(usable_clips, dict) else set(usable_clips)
    total_usable = len(usable_set)
    if total_usable <= 3:
        return set()

    max_lock_count = int(total_usable * min(0.80, max(0.10, lock_ratio)))
    min_fresh_guarantee = max(1, total_usable - max_lock_count)

    now = time.time()
    cutoff_time = now - (cooldown_hours * 3600.0)

    with get_conn() as conn:
        recent_rows = conn.execute(
            """SELECT clip_path, MAX(used_at) as last_used, COUNT(*) as cnt
               FROM usage_history
               WHERE clip_path IS NOT NULL
               GROUP BY clip_path
               ORDER BY last_used DESC""",
        ).fetchall()

    locked: set[str] = set()

    for row in recent_rows:
        path, last_used, cnt = row[0], row[1], row[2]
        if path in usable_set:
            if (last_used and last_used >= cutoff_time) or (cnt and cnt >= max_global_uses):
                locked.add(path)
                if len(locked) >= max_lock_count:
                    break

    if len(locked) < max_lock_count:
        for row in recent_rows:
            path = row[0]
            if path in usable_set and path not in locked:
                locked.add(path)
                if len(locked) >= max_lock_count:
                    break

    if (total_usable - len(locked)) < min_fresh_guarantee:
        locked_list = list(locked)
        locked = set(locked_list[:max_lock_count])

    return locked



def record_experience(song_id: int, situation: dict, decision: dict,
                      reward: float, alternatives: list, why: str,
                      film_dna: dict) -> None:
    """Stores explainable decisions; reward may be updated by later feedback."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO experiences
               (song_id, situation_json, decision_json, reward,
                alternatives_json, why, film_dna_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (song_id, json.dumps(situation), json.dumps(decision), reward,
             json.dumps(alternatives), why, json.dumps(film_dna), time.time()),
        )


# ── Song-Semantik (gelernt aus Traktor-NML/HTML-Tracklisten) ────────────────
def upsert_song_semantics(path: str, source_file: str, title: str, artist: str,
                           bpm: float, musical_key: str, sections: list,
                           movements: list, mood_tags: list, slang: dict,
                           beat_switch_count: int, sentiment: float,
                           dominant_style: str | None = None,
                           energy_character: str | None = None,
                           style_weights: dict | None = None,
                           mc_gender: str | None = None) -> int:
    """dominant_style/energy_character/style_weights/mc_gender (siehe song_semantics.
    analyze_lyrics): optional mit Default None/None/{}/None für Aufrufer, die noch
    das alte Signaturformat nutzen -> bestehende Aufrufe bleiben lauffähig."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO song_semantics
                    (path, source_file, title, artist, bpm, musical_key,
                     sections_json, movements_json, mood_tags_json, slang_json,
                     beat_switch_count, sentiment, dominant_style, energy_character,
                     style_weights_json, mc_gender, learned_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET
                    source_file=excluded.source_file,
                    title=excluded.title,
                    artist=excluded.artist,
                    bpm=excluded.bpm,
                    musical_key=excluded.musical_key,
                    sections_json=excluded.sections_json,
                    movements_json=excluded.movements_json,
                    mood_tags_json=excluded.mood_tags_json,
                    slang_json=excluded.slang_json,
                    beat_switch_count=excluded.beat_switch_count,
                    sentiment=excluded.sentiment,
                    dominant_style=excluded.dominant_style,
                    energy_character=excluded.energy_character,
                    style_weights_json=excluded.style_weights_json,
                    mc_gender=excluded.mc_gender,
                    learned_at=excluded.learned_at
               RETURNING id""",
            (path, source_file, title, artist, bpm, musical_key,
             json.dumps(sections, ensure_ascii=False), json.dumps(movements, ensure_ascii=False),
             json.dumps(mood_tags, ensure_ascii=False), json.dumps(slang, ensure_ascii=False),
             beat_switch_count, sentiment, dominant_style, energy_character,
             json.dumps(style_weights or {}, ensure_ascii=False), mc_gender, time.time()),
        )
        return cur.fetchone()[0]


def upsert_song_semantics_many(records: list[dict]) -> None:
    """Batch-Variante von upsert_song_semantics(): schreibt ALLE gelernten
    Songs eines song_semantics.py-Scans (typischerweise mehrere tausend bis
    zehntausende) über EINE einzige SQLite-Verbindung/Transaktion statt pro
    Song eine eigene Connection zu öffnen/committen/schließen (WAL-PRAGMAs +
    fsync bei jedem einzelnen Aufruf). Der alte Loop-Aufruf von
    upsert_song_semantics() pro Song war neben dem mp3-Pfad-Resolving
    (siehe song_semantics.build_filename_index) der zweite dominante Grund
    für die extreme Laufzeit des Song-Semantik-Scans bei größeren FAVs-
    Ordnern. `records` sind Dicts mit denselben Keys wie die Parameter von
    upsert_song_semantics (path, source_file, title, artist, bpm,
    musical_key, sections, movements, mood_tags, slang, beat_switch_count,
    sentiment, dominant_style, energy_character, style_weights, mc_gender)."""
    if not records:
        return
    now = time.time()
    rows = [
        (r["path"], r["source_file"], r["title"], r["artist"], r["bpm"], r["musical_key"],
         json.dumps(r["sections"], ensure_ascii=False), json.dumps(r["movements"], ensure_ascii=False),
         json.dumps(r["mood_tags"], ensure_ascii=False), json.dumps(r["slang"], ensure_ascii=False),
         r["beat_switch_count"], r["sentiment"], r.get("dominant_style"), r.get("energy_character"),
         json.dumps(r.get("style_weights") or {}, ensure_ascii=False), r.get("mc_gender"),
         json.dumps(r.get("visual_objects") or [], ensure_ascii=False),
         int(r.get("cluster_mask", 0)),
         r.get("prompt_description") or "",
         float(r.get("tension_score", 0.5)),
         float(r.get("punchline_density", 0.0)),
         now)
        for r in records
    ]
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO song_semantics
                    (path, source_file, title, artist, bpm, musical_key,
                     sections_json, movements_json, mood_tags_json, slang_json,
                     beat_switch_count, sentiment, dominant_style, energy_character,
                     style_weights_json, mc_gender, visual_objects_json, cluster_mask,
                     prompt_description, tension_score, punchline_density, learned_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET
                    source_file=excluded.source_file,
                    title=excluded.title,
                    artist=excluded.artist,
                    bpm=excluded.bpm,
                    musical_key=excluded.musical_key,
                    sections_json=excluded.sections_json,
                    movements_json=excluded.movements_json,
                    mood_tags_json=excluded.mood_tags_json,
                    slang_json=excluded.slang_json,
                    beat_switch_count=excluded.beat_switch_count,
                    sentiment=excluded.sentiment,
                    dominant_style=excluded.dominant_style,
                    energy_character=excluded.energy_character,
                    style_weights_json=excluded.style_weights_json,
                    mc_gender=excluded.mc_gender,
                    visual_objects_json=excluded.visual_objects_json,
                    cluster_mask=excluded.cluster_mask,
                    prompt_description=excluded.prompt_description,
                    tension_score=excluded.tension_score,
                    punchline_density=excluded.punchline_density,
                    learned_at=excluded.learned_at""",
            rows,
        )


def get_song_semantics(path: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT path, source_file, title, artist, bpm, musical_key,
                      sections_json, movements_json, mood_tags_json, slang_json,
                      beat_switch_count, sentiment, dominant_style, energy_character,
                      style_weights_json, mc_gender, visual_objects_json, cluster_mask,
                      prompt_description, tension_score, punchline_density, learned_at
               FROM song_semantics WHERE path=?""",
            (path,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_semantics(row)


def get_all_song_semantics() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT path, source_file, title, artist, bpm, musical_key,
                      sections_json, movements_json, mood_tags_json, slang_json,
                      beat_switch_count, sentiment, dominant_style, energy_character,
                      style_weights_json, mc_gender, visual_objects_json, cluster_mask,
                      prompt_description, tension_score, punchline_density, learned_at
               FROM song_semantics"""
        ).fetchall()
    return [_row_to_semantics(r) for r in rows]


def _row_to_semantics(row) -> dict:
    (path, source_file, title, artist, bpm, musical_key,
     sections_json, movements_json, mood_tags_json, slang_json,
     beat_switch_count, sentiment, dominant_style, energy_character,
     style_weights_json, mc_gender, visual_objects_json, cluster_mask,
     prompt_description, tension_score, punchline_density, learned_at) = row
    return {
        "path": path, "source_file": source_file, "title": title, "artist": artist,
        "bpm": bpm, "musical_key": musical_key,
        "sections": json.loads(sections_json or "[]"),
        "movements": json.loads(movements_json or "[]"),
        "mood_tags": json.loads(mood_tags_json or "[]"),
        "slang": json.loads(slang_json or "{}"),
        "beat_switch_count": beat_switch_count, "sentiment": sentiment,
        "dominant_style": dominant_style, "energy_character": energy_character,
        "style_weights": json.loads(style_weights_json or "{}"),
        "mc_gender": mc_gender,
        "visual_objects": json.loads(visual_objects_json or "[]"),
        "cluster_mask": cluster_mask or 0,
        "prompt_description": prompt_description or "",
        "tension_score": tension_score if tension_score is not None else 0.5,
        "punchline_density": punchline_density if punchline_density is not None else 0.0,
        "learned_at": learned_at,
    }



# ── Flat-Globe JSON Cache (Clip-Feature-Index) ───────────────────────────────
def load_flat_globe() -> dict:
    """Lädt den Cache. Bei Korruption (z.B. durch Absturz mitten im Schreiben
    einer *anderen* Instanz) wird NICHT stillschweigend alles verworfen:
    - zuerst wird die .bak-Datei (letzter bekannter guter Stand) versucht
    - erst wenn auch die fehlt/korrupt ist, wird leer gestartet
    Die korrupte Originaldatei wird zur Analyse nach .corrupt verschoben
    statt überschrieben zu werden."""
    with _GLOBE_LOCK:
        if FLAT_GLOBE_JSON.exists():
            try:
                with FLAT_GLOBE_JSON.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"[db] WARNUNG: {FLAT_GLOBE_JSON} ist korrupt ({e}). "
                      f"Versuche Backup ...")
                corrupt_copy = FLAT_GLOBE_JSON.with_suffix(".json.corrupt")
                try:
                    FLAT_GLOBE_JSON.replace(corrupt_copy)
                    print(f"[db] Korrupte Datei gesichert als {corrupt_copy}.")
                except OSError:
                    pass

        bak = FLAT_GLOBE_JSON.with_suffix(".json.bak")
        if bak.exists():
            try:
                with bak.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[db] Backup {bak} erfolgreich geladen.")
                return data
            except (json.JSONDecodeError, UnicodeDecodeError):
                print(f"[db] Backup {bak} ist ebenfalls korrupt. Starte leer.")

        return {}


def save_flat_globe(globe: dict):
    """Atomarer, abbruchsicherer Write:
      1. neuen Stand nach .tmp schreiben (unvollständiger Schreibvorgang bei
         Absturz betrifft nur die .tmp-Datei, nie die echte Datei)
      2. bisherige gültige Datei nach .bak rotieren (Fallback für load_flat_globe)
      3. .tmp atomar auf den Zielnamen umbenennen (os-level atomic rename)
    """
    with _GLOBE_LOCK:
        FLAT_GLOBE_JSON.parent.mkdir(parents=True, exist_ok=True)
        tmp = FLAT_GLOBE_JSON.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(globe, f, ensure_ascii=False, indent=2)

        if FLAT_GLOBE_JSON.exists():
            bak = FLAT_GLOBE_JSON.with_suffix(".json.bak")
            try:
                FLAT_GLOBE_JSON.replace(bak)
            except OSError:
                pass  # Rotation ist best-effort, darf den eigentlichen Save nicht verhindern

        tmp.replace(FLAT_GLOBE_JSON)  # atomarer Rename, kein halbgeschriebenes JSON möglich


# ── LibSync Management & Health API ───────────────────────────────────────────
def validate_flat_globe() -> tuple[bool, str]:
    """Prüft die Integrität von libsync-flat-globe.db.json."""
    if not FLAT_GLOBE_JSON.exists():
        return False, f"{FLAT_GLOBE_JSON} existiert nicht."
    try:
        with _GLOBE_LOCK:
            with FLAT_GLOBE_JSON.open("r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, dict):
            return False, "Format ungültig (kein JSON-Objekt)."
        return True, f"OK ({len(data)} Clips indiziert)."
    except Exception as e:
        return False, f"Fehler beim Laden ({e})."


def libsync_stats() -> dict:
    """Gibt eine Diagnose-Übersicht des Flat-Globe-Caches zurück."""
    globe = load_flat_globe()
    import clip_pool
    return clip_pool.libsync_summary(globe)


def repair_flat_globe(log=print) -> tuple[dict, int]:
    """Validiert und repariert fehlende Metadaten im Flat-Globe-Cache."""
    globe = load_flat_globe()
    import clip_pool
    globe, repaired = clip_pool.libsync_validate_and_repair(globe, log=log)
    if repaired > 0:
        save_flat_globe(globe)
        log(f"[db] {repaired} Einträge in {FLAT_GLOBE_JSON.name} aktualisiert und atomar gespeichert.")
    return globe, repaired


def prune_dead_clips(log=print) -> tuple[dict, list[str]]:
    """Lädt den Flat-Globe-Cache, entfernt alle toten Dateieinträge und speichert das Ergebnis atomar."""
    globe = load_flat_globe()
    import clip_pool
    globe, dead = clip_pool.prune_dead_clips(globe, on_progress=save_flat_globe, log=log)
    return globe, dead


def purge_clip_entry(clip_path: str, log=print) -> bool:
    """Entfernt einen einzelnen fehlerhaften Clip atomar aus dem Flat-Globe-Cache."""
    if not clip_path:
        return False
    with _GLOBE_LOCK:
        globe = load_flat_globe()
        if clip_path in globe:
            del globe[clip_path]
            save_flat_globe(globe)
            log(f"[db] 🗑️ Clip atomar aus {FLAT_GLOBE_JSON.name} entfernt: {clip_path}")
            try:
                from vector_tree import get_global_vector_tree
                tree = get_global_vector_tree()
                if clip_path in tree.leaves:
                    tree.build_from_globe(globe, force_rebuild=True)
            except Exception:
                pass
            return True
        return False


def prune_failed_clips(log=print) -> tuple[dict, list[str]]:
    """Entfernt alle als fehlerhaft markierten Clips (Encode-Fehler / playback_ok=False) aus dem Cache."""
    globe = load_flat_globe()
    import clip_pool
    globe, failed = clip_pool.purge_failed_clips(globe, on_progress=save_flat_globe, log=log)
    return globe, failed


