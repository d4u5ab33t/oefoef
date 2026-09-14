"""
schema.py — Visual & Rhythm Genome dataclasses and serialization.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import json
import time


@dataclass
class SectionInfo:
    start_sec: float
    end_sec: float
    label: str  # "intro", "verse", "chorus", "bridge", "outro"
    energy: float


@dataclass
class RhythmGenome:
    bpm: float
    duration_sec: float
    beat_times: List[float] = field(default_factory=list)
    onset_times: List[float] = field(default_factory=list)
    energy_curve: List[float] = field(default_factory=list)
    sections: List[SectionInfo] = field(default_factory=list)
    drop_timestamps: List[float] = field(default_factory=list)


@dataclass
class VisualGenome:
    style_name: str = "alpine_drill_comedy"
    target_cuts_per_min: float = 60.0
    camera_motion: List[str] = field(default_factory=lambda: ["push_zoom", "3d_pan", "wobble_shake"])
    color_palette: List[str] = field(default_factory=lambda: ["vhs_warm", "high_contrast", "cyber_neon"])
    fx_tags: List[str] = field(default_factory=lambda: ["glitch", "datamosh", "flash_cut"])
    transition_policy: str = "rhythm_quantized"


@dataclass
class GenomeData:
    audio_path: str
    rhythm: RhythmGenome
    visual: VisualGenome
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenomeData":
        sections = [SectionInfo(**s) for s in data["rhythm"]["sections"]]
        rhythm_dict = dict(data["rhythm"])
        rhythm_dict["sections"] = sections
        rhythm = RhythmGenome(**rhythm_dict)
        visual = VisualGenome(**data["visual"])
        return cls(
            audio_path=data["audio_path"],
            rhythm=rhythm,
            visual=visual,
            created_at=data.get("created_at", time.time())
        )
