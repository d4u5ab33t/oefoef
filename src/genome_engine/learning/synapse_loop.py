"""
synapse_loop.py — Closed-loop Neural & Aesthetic Genome Auto-Learner.
"""
from dataclasses import dataclass, field
from typing import List, Dict
from genome_engine.genome.schema import VisualGenome


@dataclass
class VisualAnalysisProfile:
    avg_shot_duration_sec: float
    detected_cuts_per_min: float
    dominant_colors: List[str]
    motion_intensity: float  # 0.0 to 1.0


class AestheticGenomeLearner:
    """Learns visual genome parameters from video sample analysis."""

    def __init__(self, learning_rate: float = 0.2):
        self.learning_rate = learning_rate

    def analyze_reference(self, video_path: str) -> VisualAnalysisProfile:
        # Mock/simulated visual extraction (OpenCV/CLIP feature extraction)
        return VisualAnalysisProfile(
            avg_shot_duration_sec=0.8,
            detected_cuts_per_min=75.0,
            dominant_colors=["neon_magenta", "cyan"],
            motion_intensity=0.85
        )

    def adapt_visual_genome(self, genome: VisualGenome, profile: VisualAnalysisProfile) -> VisualGenome:
        # Update cuts per min toward observed reference
        new_cuts = (1.0 - self.learning_rate) * genome.target_cuts_per_min + self.learning_rate * profile.detected_cuts_per_min
        genome.target_cuts_per_min = round(new_cuts, 1)

        # Merge new dominant color palettes
        for c in profile.dominant_colors:
            if c not in genome.color_palette:
                genome.color_palette.append(c)

        if profile.motion_intensity > 0.8 and "whip_pan" not in genome.camera_motion:
            genome.camera_motion.append("whip_pan")

        return genome
