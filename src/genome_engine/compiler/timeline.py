"""
timeline.py — Timeline segments and Edit Decision List (EDL) model.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class TimelineSegment:
    segment_id: int
    start_sec: float
    end_sec: float
    duration_sec: float
    section_name: str
    energy_level: float
    cut_style: str  # "hard_cut", "flash_cut", "zoom_push", "glitch_transition"
    sync_type: str  # "on_beat", "on_drop", "on_onset", "ambient"
    query_tags: List[str] = field(default_factory=list)
    assigned_clip_path: str = ""
    clip_in_sec: float = 0.0
    clip_out_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EditDecisionList:
    track_path: str
    total_duration_sec: float
    bpm: float
    style_name: str
    segments: List[TimelineSegment] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_path": self.track_path,
            "total_duration_sec": self.total_duration_sec,
            "bpm": self.bpm,
            "style_name": self.style_name,
            "segment_count": len(self.segments),
            "segments": [s.to_dict() for s in self.segments]
        }
