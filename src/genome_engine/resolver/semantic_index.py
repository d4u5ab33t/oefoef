"""
semantic_index.py — Media asset index and semantic tag search.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Set
import os
import json
import re
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None


@dataclass
class MediaAsset:
    clip_path: str
    duration_sec: float = 10.0
    fps: float = 30.0
    width: int = 1920
    height: int = 1080
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "MediaAsset":
        return cls(**data)


class SemanticIndex:
    """Stores and queries media asset metadata by tags and energy."""

    VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

    def __init__(self):
        self.assets: List[MediaAsset] = []
        self._tag_index: Dict[str, List[MediaAsset]] = {}
        self._path_set: Set[str] = set()

    def add_asset(self, asset: MediaAsset):
        if asset.clip_path in self._path_set:
            return
        self.assets.append(asset)
        self._path_set.add(asset.clip_path)
        for tag in asset.tags:
            tag_clean = tag.lower().strip()
            if not tag_clean:
                continue
            if tag_clean not in self._tag_index:
                self._tag_index[tag_clean] = []
            self._tag_index[tag_clean].append(asset)

    def search_by_tags(self, query_tags: List[str]) -> List[MediaAsset]:
        matches: Dict[str, int] = {}
        for q in query_tags:
            q_clean = q.lower().strip()
            if q_clean in self._tag_index:
                for asset in self._tag_index[q_clean]:
                    matches[asset.clip_path] = matches.get(asset.clip_path, 0) + 1
        
        if not matches:
            return self.assets.copy()

        # Sort by match score (highest count of matching tags first)
        sorted_paths = sorted(matches.keys(), key=lambda k: matches[k], reverse=True)
        path_to_asset = {a.clip_path: a for a in self.assets}
        return [path_to_asset[p] for p in sorted_paths if p in path_to_asset]

    @staticmethod
    def _extract_tags_from_name(file_path: str) -> List[str]:
        """Extracts descriptive keyword tags from filename and parent directory."""
        path = Path(file_path)
        raw_text = f"{path.parent.name} {path.stem}"
        # Replace punctuation/underscores with spaces
        words = re.split(r"[_\-\s\.\(\)\[\]\d]+", raw_text)
        tags = [w.lower() for w in words if len(w) >= 3 and not w.isdigit()]
        return list(set(tags))

    @staticmethod
    def _probe_video_file(file_path: str) -> tuple[float, float, int, int]:
        """Probes video duration (sec), fps, width, height using OpenCV if available."""
        if cv2 is not None and os.path.exists(file_path):
            try:
                cap = cv2.VideoCapture(file_path)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
                    cap.release()
                    duration = frame_count / fps if fps > 0 and frame_count > 0 else 10.0
                    return round(duration, 2), round(fps, 2), width, height
            except Exception:
                pass
        return 10.0, 30.0, 1920, 1080

    def scan_directory(self, dir_path: str, recursive: bool = True) -> int:
        """Scans a directory on disk and adds all video files to the semantic index."""
        p = Path(dir_path)
        if not p.exists():
            return 0

        pattern = "**/*" if recursive else "*"
        count = 0
        for entry in p.glob(pattern):
            if entry.is_file() and entry.suffix.lower() in self.VIDEO_EXTENSIONS:
                str_path = str(entry.resolve())
                if str_path not in self._path_set:
                    dur, fps, w, h = self._probe_video_file(str_path)
                    tags = self._extract_tags_from_name(str_path)
                    asset = MediaAsset(
                        clip_path=str_path,
                        duration_sec=dur,
                        fps=fps,
                        width=w,
                        height=h,
                        tags=tags
                    )
                    self.add_asset(asset)
                    count += 1
        return count

    def save_cache(self, cache_file: str) -> None:
        """Saves current index to JSON cache."""
        os.makedirs(os.path.dirname(os.path.abspath(cache_file)), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in self.assets], f, indent=2)

    def load_cache(self, cache_file: str) -> bool:
        """Loads index from JSON cache if valid."""
        if not os.path.exists(cache_file):
            return False
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                self.add_asset(MediaAsset.from_dict(item))
            return True
        except Exception:
            return False
