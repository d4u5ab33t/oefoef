import cv2
import numpy as np
import sqlite3
import json
from pathlib import Path
from typing import List
from sklearn.cluster import KMeans
from core.ir import ClipDNA

class ScannerPipeline:
    def __init__(self, db_path: Path = Path(".weed_cache/genome.db")):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._init_db()

    def _init_db(self):
        self.conn.execute("""CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY, 
            file_path TEXT UNIQUE, 
            motion_entropy REAL, 
            camera_motion TEXT, 
            genes TEXT, 
            duration_ms INTEGER
        )""")
        self.conn.commit()

    def scan_directory(self, clips_dir: Path) -> List[ClipDNA]:
        results = []
        extensions = {"*.mp4", "*.mov", "*.avi", "*.mkv", "*.webm"}
        video_files = []
        for ext in extensions:
            video_files.extend(clips_dir.rglob(ext))

        print(f"🔍 Found {len(video_files)} potential video files (recursive).")

        for vid in video_files:
            abs_path = str(vid.resolve())
            cursor = self.conn.execute("SELECT id FROM clips WHERE file_path = ?", (abs_path,))
            if cursor.fetchone() is not None:
                print(f"  ⏭️  Skipping (already in DB): {vid.name}")
                continue

            try:
                dna = self._scan_video(vid)
                self._save_to_db(dna)
                results.append(dna)
                print(f"  ✅ Scanned: {vid.name} | Genes: {', '.join(dna.genes)}")
            except Exception as e:
                print(f"  ⚠️  Failed to scan {vid.name}: {e}")
                continue

        print(f"\n🎉 Successfully scanned {len(results)} new clips.")
        return results

    def _save_to_db(self, clip: ClipDNA):
        self.conn.execute("""
            INSERT OR REPLACE INTO clips (id, file_path, motion_entropy, camera_motion, genes, duration_ms) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (clip.id, clip.file_path, clip.motion_entropy, clip.camera_motion, json.dumps(clip.genes), clip.duration_ms))
        self.conn.commit()

    def _scan_video(self, video_path: Path) -> ClipDNA:
        cap = cv2.VideoCapture(str(video_path))
        frames = []
        frame_count = 0
        max_frames = 30

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            if frame_count % 5 == 0 and len(frames) < max_frames:
                frames.append(frame)
            frame_count += 1
            if frame_count > 300: break
        cap.release()

        duration_ms = int((frame_count / 30.0) * 1000) if frame_count > 0 else 5000

        motion_entropy = 0.5
        if len(frames) > 1:
            prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
            motions = []
            for frame in frames[1:]:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                motions.append(np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)))
                prev_gray = gray
            motion_entropy = float(np.mean(motions) / 10.0)

        colors = ["#ffffff"]
        if frames:
            pixels = frames[len(frames)//2].reshape(-1, 3)[::20]
            if len(pixels) > 5:
                kmeans = KMeans(n_clusters=3, random_state=42, n_init=10).fit(pixels)
                colors = [f"#{int(c[2]):02x}{int(c[1]):02x}{int(c[0]):02x}" for c in kmeans.cluster_centers_]

        cam_motion = "static"
        if motion_entropy > 0.8: cam_motion = "handheld"
        elif motion_entropy > 0.5: cam_motion = "push"
        elif motion_entropy > 0.3: cam_motion = "pan"

        genes = []
        if motion_entropy > 0.6: genes.append(".fast")
        else: genes.append(".slow")
        if any("ff" in c.lower() for c in colors): genes.append(".warm")
        if any("0000" in c.lower() or "0000ff" in c.lower() for c in colors): genes.append(".cold")
        genes.append(".hero")

        return ClipDNA(
            file_path=str(video_path.resolve()),
            duration_ms=duration_ms,
            motion_entropy=min(1.0, motion_entropy), 
            dominant_colors=colors,
            detected_objects=["person"], 
            detected_faces=1,
            camera_motion=cam_motion, 
            lighting="neutral",
            embedding_vector_id=f"vec_{video_path.stem}", 
            genes=genes
        )
