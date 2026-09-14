"""
semantic_index.py — Media asset index and semantic tag search.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import os


@dataclass
class MediaAsset:
    clip_path: str
    duration_sec: float = 10.0
    fps: float = 30.0
    width: int = 1920
    height: int = 1080
    tags: List[str] = field(default_factory=list)


class SemanticIndex:
    """Stores and queries media asset metadata by tags and energy."""

    def __init__(self):
        self.assets: List[MediaAsset] = []
        self._tag_index: Dict[str, List[MediaAsset]] = {}

    def add_asset(self, asset: MediaAsset):
        self.assets.append(asset)
        for tag in asset.tags:
            tag_clean = tag.lower().strip()
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

        # Sort by match score
        sorted_paths = sorted(matches.keys(), key=lambda k: matches[k], reverse=True)
        path_to_asset = {a.clip_path: a for a in self.assets}
        return [path_to_asset[p] for p in sorted_paths if p in path_to_asset]
