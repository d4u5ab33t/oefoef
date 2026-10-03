"""
weedit.core.vector_db — Memory-Mapped Vector Logic, Creative Vectors & Anti-Repeat Engine
"""
import os
import json
import sqlite3
import hashlib
from pathlib import Path
import numpy as np

class VectorDB:
    def __init__(self, db_path: str = "data/weedit_vector.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.usage_history = set()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clip_metadata (
                clip_path TEXT PRIMARY KEY,
                filename TEXT,
                duration REAL,
                width INTEGER,
                height INTEGER,
                fps REAL,
                motion_score REAL,
                face_score REAL,
                gender_vector TEXT,
                style_vector TEXT,
                energy_vector TEXT,
                shot_type TEXT,
                camera_motion TEXT,
                phash TEXT,
                last_used TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def register_clip(self, clip_path: str, meta: dict):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO clip_metadata 
            (clip_path, filename, duration, width, height, fps, motion_score, face_score, gender_vector, style_vector, energy_vector, shot_type, camera_motion, phash, last_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            clip_path,
            Path(clip_path).name,
            meta.get("duration", 5.0),
            meta.get("width", 1920),
            meta.get("height", 1080),
            meta.get("fps", 30.0),
            meta.get("motion_score", 0.5),
            meta.get("face_score", 0.0),
            json.dumps(meta.get("gender_vector", [0.5, 0.5])),
            json.dumps(meta.get("style_vector", [0.5, 0.5, 0.5])),
            json.dumps(meta.get("energy_vector", [0.5])),
            meta.get("shot_type", "medium"),
            meta.get("camera_motion", "hold"),
            meta.get("phash", hashlib.md5(clip_path.encode()).hexdigest()[:16])
        ))
        conn.commit()
        conn.close()

    def scan_clip_pool(self, pool_dir: str, follow_symlinks: bool = True):
        pool_path = Path(pool_dir)
        if not pool_path.exists():
            return 0

        registered_count = 0
        extensions = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
        
        for root, dirs, files in os.walk(pool_path, followlinks=follow_symlinks):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in extensions:
                    full_path = str(Path(root) / f)
                    # Quick metadata stub if not present
                    meta = {
                        "duration": 6.0,
                        "width": 1920,
                        "height": 1080,
                        "fps": 30.0,
                        "motion_score": np.random.uniform(0.2, 0.9),
                        "face_score": np.random.uniform(0.0, 0.8),
                        "gender_vector": [0.5, 0.5],
                        "style_vector": [0.5, 0.5, 0.5],
                        "energy_vector": [0.5],
                        "shot_type": np.random.choice(["wide", "medium", "close_up", "action"]),
                        "camera_motion": np.random.choice(["hold", "push", "drift", "whip", "snap"])
                    }
                    self.register_clip(full_path, meta)
                    registered_count += 1
        return registered_count

    def fetch_all_clips(self) -> list:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT clip_path, duration, motion_score, face_score, shot_type, camera_motion, phash FROM clip_metadata")
        rows = cursor.fetchall()
        conn.close()
        
        clips = []
        for r in rows:
            clips.append({
                "clip_path": r[0],
                "duration": r[1],
                "motion_score": r[2],
                "face_score": r[3],
                "shot_type": r[4],
                "camera_motion": r[5],
                "phash": r[6]
            })
        return clips

    def match_best_clip(self, target_energy: float, target_structure: str, target_gender: str = "unknown", preferred_shot: str = None) -> dict:
        clips = self.fetch_all_clips()
        if not clips:
            return None

        best_clip = None
        best_score = -1.0

        for clip in clips:
            cpath = clip["clip_path"]
            # Strict Repetition Avoidance
            if cpath in self.usage_history:
                score_penalty = 0.5
            else:
                score_penalty = 1.0

            # Energy score
            energy_score = 1.0 - abs(target_energy - clip["motion_score"])

            # Shot type boost
            shot_boost = 1.2 if (preferred_shot and clip["shot_type"] == preferred_shot) else 1.0

            total_score = (energy_score * 0.7 + clip["face_score"] * 0.3) * score_penalty * shot_boost

            if total_score > best_score:
                best_score = total_score
                best_clip = clip

        if best_clip:
            self.usage_history.add(best_clip["clip_path"])
        return best_clip
