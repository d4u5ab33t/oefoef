"""
timeline.py — Timeline segments and Edit Decision List (EDL) model.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import json
import os


@dataclass
class TimelineSegment:
    segment_id: int
    start_sec: float
    end_sec: float
    duration_sec: float
    section_name: str
    energy_level: float
    cut_style: str = "hard_cut"  # "hard_cut", "flash_cut", "zoom_push", "glitch_transition", "fade_black"
    sync_type: str = "on_beat"   # "on_beat", "on_drop", "on_onset", "ambient"
    query_tags: List[str] = field(default_factory=list)
    assigned_clip_path: str = ""
    clip_in_sec: float = 0.0
    clip_out_sec: float = 0.0
    motion_directive: str = "static"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineSegment":
        return cls(
            segment_id=int(data.get("segment_id", 1)),
            start_sec=float(data.get("start_sec", 0.0)),
            end_sec=float(data.get("end_sec", 0.0)),
            duration_sec=float(data.get("duration_sec", 0.0)),
            section_name=str(data.get("section_name", "verse")),
            energy_level=float(data.get("energy_level", 0.5)),
            cut_style=str(data.get("cut_style", "hard_cut")),
            sync_type=str(data.get("sync_type", "on_beat")),
            query_tags=list(data.get("query_tags", [])),
            assigned_clip_path=str(data.get("assigned_clip_path", "")),
            clip_in_sec=float(data.get("clip_in_sec", 0.0)),
            clip_out_sec=float(data.get("clip_out_sec", 0.0)),
            motion_directive=str(data.get("motion_directive", "static"))
        )


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

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save_json(self, output_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EditDecisionList":
        segments = [
            TimelineSegment.from_dict(s)
            for s in data.get("segments", [])
        ]
        return cls(
            track_path=str(data.get("track_path", "")),
            total_duration_sec=float(data.get("total_duration_sec", 0.0)),
            bpm=float(data.get("bpm", 120.0)),
            style_name=str(data.get("style_name", "cinematic")),
            segments=segments
        )

    @classmethod
    def from_json(cls, json_str: str) -> "EditDecisionList":
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def load_json(cls, file_path: str) -> "EditDecisionList":
        with open(file_path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())

    def validate_integrity(self) -> List[str]:
        """Validates that timeline segments are contiguous without gaps or negative durations."""
        issues = []
        if not self.segments:
            issues.append("EDL has no segments.")
            return issues

        prev_end = 0.0
        for i, seg in enumerate(self.segments):
            if seg.duration_sec <= 0.0:
                issues.append(f"Segment {seg.segment_id} has invalid duration {seg.duration_sec}s.")
            if abs(seg.start_sec - prev_end) > 0.05 and i > 0:
                issues.append(f"Gap or overlap detected before segment {seg.segment_id}: expected {prev_end}s, got {seg.start_sec}s.")
            prev_end = seg.end_sec

        return issues
