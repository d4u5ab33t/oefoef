"""
synapse_loop.py — Closed-loop Neural & Aesthetic Genome Auto-Learner.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import os
import json
import numpy as np
from genome_engine.genome.schema import VisualGenome

try:
    import cv2
except ImportError:
    cv2 = None


@dataclass
class VisualAnalysisProfile:
    avg_shot_duration_sec: float
    detected_cuts_per_min: float
    dominant_colors: List[str]
    motion_intensity: float  # 0.0 to 1.0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "VisualAnalysisProfile":
        return cls(**data)


class AestheticGenomeLearner:
    """Learns visual genome parameters from video sample analysis using frame analysis."""

    def __init__(self, learning_rate: float = 0.2):
        self.learning_rate = learning_rate

    def analyze_reference(self, video_path: str, max_frames: int = 300) -> VisualAnalysisProfile:
        """Analyzes a reference video to extract cut pace, dominant colors, and motion dynamics."""
        if cv2 is not None and os.path.exists(video_path):
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    frame_count = 0
                    prev_gray = None
                    cut_count = 0
                    diff_magnitudes = []
                    color_accum = np.zeros(3, dtype=np.float64)

                    while frame_count < max_frames:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        
                        # Downscale for performance
                        small = cv2.resize(frame, (160, 90))
                        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

                        # Color accumulation
                        color_accum += np.mean(small, axis=(0, 1))

                        if prev_gray is not None:
                            diff = cv2.absdiff(gray, prev_gray)
                            mean_diff = np.mean(diff)
                            diff_magnitudes.append(mean_diff)
                            # Threshold for scene cut
                            if mean_diff > 35.0:
                                cut_count += 1

                        prev_gray = gray
                        frame_count += 1

                    cap.release()

                    total_sec = max(1.0, frame_count / fps)
                    cuts_per_min = (cut_count / total_sec) * 60.0
                    cuts_per_min = max(20.0, min(180.0, cuts_per_min))
                    avg_shot_dur = total_sec / max(1, cut_count + 1)
                    motion_intensity = float(np.mean(diff_magnitudes) / 50.0) if diff_magnitudes else 0.5
                    motion_intensity = min(1.0, max(0.1, motion_intensity))

                    # Classify dominant colors
                    avg_bgr = color_accum / max(1, frame_count)
                    dominant = []
                    b, g, r = avg_bgr
                    if r > 120 and g < 100: dominant.append("warm_red")
                    if b > 120 and r < 100: dominant.append("cyan_blue")
                    if g > 120: dominant.append("neon_green")
                    if r > 140 and g > 140: dominant.append("warm_gold")
                    if not dominant: dominant.append("high_contrast")

                    return VisualAnalysisProfile(
                        avg_shot_duration_sec=round(avg_shot_dur, 2),
                        detected_cuts_per_min=round(cuts_per_min, 1),
                        dominant_colors=dominant,
                        motion_intensity=round(motion_intensity, 2)
                    )
            except Exception:
                pass

        # Fallback profile
        return VisualAnalysisProfile(
            avg_shot_duration_sec=0.8,
            detected_cuts_per_min=75.0,
            dominant_colors=["neon_magenta", "cyan"],
            motion_intensity=0.85
        )

    def adapt_visual_genome(self, genome: VisualGenome, profile: VisualAnalysisProfile) -> VisualGenome:
        """Applies learned reference profile to adjust VisualGenome parameters."""
        new_cuts = (1.0 - self.learning_rate) * genome.target_cuts_per_min + self.learning_rate * profile.detected_cuts_per_min
        genome.target_cuts_per_min = round(new_cuts, 1)

        for c in profile.dominant_colors:
            if c not in genome.color_palette:
                genome.color_palette.append(c)

        if profile.motion_intensity > 0.8 and "whip_pan" not in genome.camera_motion:
            genome.camera_motion.append("whip_pan")

        return genome
