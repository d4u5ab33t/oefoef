"""
Atlas Monitor - database layer
--------------------------------
Plain sqlite3, no ORM. Two tables:

  posts             one row per tracked post/track (platform + external id)
  metrics_snapshots  one row per ingested measurement in time for a post

A "snapshot" is a single point-in-time reading of a post's public metrics
(views, likes, comments, shares). You (or a script you write) push these in
via POST /api/ingest whenever you check the post's stats - e.g. by copying
numbers from the TikTok/Instagram/YouTube creator dashboard, or via the
official platform APIs if you have API access. Atlas Monitor does not
scrape or auto-fetch anything itself.
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,          -- e.g. 'tiktok', 'instagram', 'youtube'
    external_id TEXT NOT NULL,       -- the post/video id on that platform
    track_title TEXT,
    artist TEXT,
    url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(platform, external_id)
);

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    shares INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_snapshots_post ON metrics_snapshots(post_id, recorded_at);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def upsert_post(platform, external_id, track_title=None, artist=None, url=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO posts (platform, external_id, track_title, artist, url)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(platform, external_id) DO UPDATE SET
                   track_title = COALESCE(excluded.track_title, posts.track_title),
                   artist      = COALESCE(excluded.artist, posts.artist),
                   url         = COALESCE(excluded.url, posts.url)
            """,
            (platform, external_id, track_title, artist, url),
        )
        row = conn.execute(
            "SELECT id FROM posts WHERE platform = ? AND external_id = ?",
            (platform, external_id),
        ).fetchone()
        return row["id"]


def add_snapshot(post_id, views, likes, comments, shares, recorded_at=None):
    with get_conn() as conn:
        if recorded_at:
            conn.execute(
                """INSERT INTO metrics_snapshots
                   (post_id, views, likes, comments, shares, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (post_id, views, likes, comments, shares, recorded_at),
            )
        else:
            conn.execute(
                """INSERT INTO metrics_snapshots
                   (post_id, views, likes, comments, shares)
                   VALUES (?, ?, ?, ?, ?)""",
                (post_id, views, likes, comments, shares),
            )


def list_posts_with_latest():
    """All posts joined with their most recent snapshot and the one before it
    (needed for velocity calculation)."""
    with get_conn() as conn:
        posts = conn.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
        result = []
        for p in posts:
            snaps = conn.execute(
                """SELECT * FROM metrics_snapshots WHERE post_id = ?
                   ORDER BY recorded_at DESC LIMIT 2""",
                (p["id"],),
            ).fetchall()
            result.append({"post": dict(p), "recent_snapshots": [dict(s) for s in snaps]})
        return result


def get_post_history(post_id):
    with get_conn() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            return None
        snaps = conn.execute(
            "SELECT * FROM metrics_snapshots WHERE post_id = ? ORDER BY recorded_at ASC",
            (post_id,),
        ).fetchall()
        return {"post": dict(post), "snapshots": [dict(s) for s in snaps]}


def delete_all_demo_data():
    """Wipe everything. Used by the reset button so demo data doesn't linger
    once real data starts coming in."""
    with get_conn() as conn:
        conn.execute("DELETE FROM metrics_snapshots")
        conn.execute("DELETE FROM posts")
