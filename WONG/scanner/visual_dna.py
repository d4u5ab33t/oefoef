import cv2
import numpy as np
import sqlite3
import hashlib
from pathlib import Path

class VisualScanner:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _compute_sha256(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def scan_clip(self, file_path: Path):
        """Extrahiert die DNA eines Clips."""
        cap = cv2.VideoCapture(str(file_path))
        motion_scores = []
        brightness_scores = []
        
        ret, prev_frame = cap.read()
        if not ret: return None
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

        while True:
            ret, frame = cap.read()
            if not ret: break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 1. Motion DNA (Optical Flow Approximation)
            diff = cv2.absdiff(gray, prev_gray)
            motion_scores.append(np.mean(diff))
            
            # 2. Color/Light DNA (Brightness)
            brightness_scores.append(np.mean(gray))
            
            prev_gray = gray

        # Aggregation der DNA
        dna = {
            "motion": float(np.mean(motion_scores)),
            "brightness": float(np.mean(brightness_scores)),
            "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS),
            "fps": cap.get(cv2.CAP_PROP_FPS)
        }
        cap.release()
        
        # 3. Auto-Tagging (Die Basis für unsere spätere Grammar Engine)
        tags = [".fast"] if dna["motion"] > 20 else [".slow"]
        if dna["brightness"] > 150: tags.append(".high_key")
        else: tags.append(".low_key")
            
        return dna, tags

    def ingest(self, clips_dir: str):
        print(f"[SCANNER] Durchsuche {clips_dir}...")
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        for file_path in Path(clips_dir).glob("*.mp4"):
            sha = self._compute_sha256(file_path)
            
            # Vermeide Duplikate
            if cur.execute("SELECT 1 FROM clips WHERE sha256=?", (sha,)).fetchone():
                continue
                
            dna, tags = self.scan_clip(file_path)
            
            cur.execute(
                "INSERT INTO clips (sha256, path, duration, tags_json) VALUES (?, ?, ?, ?)",
                (sha, str(file_path), dna["duration"], json.dumps(tags))
            )
            print(f"[DNA] Gescannt: {file_path.name} -> {tags}")
            
        conn.commit()
        conn.close()