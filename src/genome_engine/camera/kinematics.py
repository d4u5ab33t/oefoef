"""
kinematics.py — Camera motion, speed ramping, and transformation curves.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any
import math


@dataclass
class CameraKeyframe:
    time_sec: float
    zoom_scale: float  # e.g. 1.0 -> 1.2
    pan_x: float       # pixels or normalized offset
    pan_y: float
    rotation_deg: float
    focal_length_mm: float = 35.0


@dataclass
class CameraTrajectory:
    motion_type: str  # "push_zoom", "whip_pan", "orbit", "static"
    keyframes: List[CameraKeyframe] = field(default_factory=list)
    letterbox_aspect: float = 2.39  # Anamorphic ratio

    def sample_at(self, t: float) -> CameraKeyframe:
        if not self.keyframes:
            return CameraKeyframe(t, 1.0, 0.0, 0.0, 0.0)
        if len(self.keyframes) == 1:
            return self.keyframes[0]

        # Linear interpolation between keyframes
        if t <= self.keyframes[0].time_sec:
            return self.keyframes[0]
        if t >= self.keyframes[-1].time_sec:
            return self.keyframes[-1]

        for i in range(len(self.keyframes) - 1):
            k1, k2 = self.keyframes[i], self.keyframes[i + 1]
            if k1.time_sec <= t <= k2.time_sec:
                factor = (t - k1.time_sec) / (k2.time_sec - k1.time_sec)
                return CameraKeyframe(
                    time_sec=round(t, 3),
                    zoom_scale=round(k1.zoom_scale + factor * (k2.zoom_scale - k1.zoom_scale), 3),
                    pan_x=round(k1.pan_x + factor * (k2.pan_x - k1.pan_x), 2),
                    pan_y=round(k1.pan_y + factor * (k2.pan_y - k1.pan_y), 2),
                    rotation_deg=round(k1.rotation_deg + factor * (k2.rotation_deg - k1.rotation_deg), 2),
                    focal_length_mm=round(k1.focal_length_mm + factor * (k2.focal_length_mm - k1.focal_length_mm), 1)
                )

        return self.keyframes[-1]


class KinematicsEngine:
    """Generates dynamic camera motion keyframe trajectories."""

    @staticmethod
    def generate_push_zoom(duration: float, start_scale: float = 1.0, end_scale: float = 1.25) -> CameraTrajectory:
        kf1 = CameraKeyframe(0.0, start_scale, 0.0, 0.0, 0.0, focal_length_mm=35.0)
        kf2 = CameraKeyframe(duration, end_scale, 0.0, 0.0, 0.0, focal_length_mm=50.0)
        return CameraTrajectory(motion_type="push_zoom", keyframes=[kf1, kf2])

    @staticmethod
    def generate_whip_pan(duration: float, pan_distance: float = 200.0) -> CameraTrajectory:
        kf1 = CameraKeyframe(0.0, 1.0, -pan_distance, 0.0, -5.0)
        kf2 = CameraKeyframe(duration * 0.5, 1.05, 0.0, 0.0, 0.0)
        kf3 = CameraKeyframe(duration, 1.0, pan_distance, 0.0, 5.0)
        return CameraTrajectory(motion_type="whip_pan", keyframes=[kf1, kf2, kf3])
