"""
kinematics.py — Camera motion, speed ramping, and transformation curves.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math


@dataclass
class CameraKeyframe:
    time_sec: float
    zoom_scale: float  # e.g. 1.0 -> 1.25
    pan_x: float       # horizontal offset in pixels
    pan_y: float       # vertical offset in pixels
    rotation_deg: float = 0.0
    focal_length_mm: float = 35.0


@dataclass
class CameraTrajectory:
    motion_type: str  # "push_zoom", "whip_pan", "dutch_roll", "subwoofer_shake", "static"
    keyframes: List[CameraKeyframe] = field(default_factory=list)
    letterbox_aspect: float = 2.39  # Anamorphic aspect ratio

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
                factor = (t - k1.time_sec) / max(1e-6, (k2.time_sec - k1.time_sec))
                return CameraKeyframe(
                    time_sec=round(t, 3),
                    zoom_scale=round(k1.zoom_scale + factor * (k2.zoom_scale - k1.zoom_scale), 3),
                    pan_x=round(k1.pan_x + factor * (k2.pan_x - k1.pan_x), 2),
                    pan_y=round(k1.pan_y + factor * (k2.pan_y - k1.pan_y), 2),
                    rotation_deg=round(k1.rotation_deg + factor * (k2.rotation_deg - k1.rotation_deg), 2),
                    focal_length_mm=round(k1.focal_length_mm + factor * (k2.focal_length_mm - k1.focal_length_mm), 1)
                )

        return self.keyframes[-1]

    def to_ffmpeg_filter(self, width: int = 1920, height: int = 1080, fps: float = 30.0) -> str:
        """Translates camera kinematics into FFmpeg video filter expression."""
        if not self.keyframes or self.motion_type == "static":
            return f"scale={width}:{height}"

        dur = self.keyframes[-1].time_sec if self.keyframes else 1.0
        total_frames = max(1, int(dur * fps))

        if self.motion_type == "push_zoom":
            start_z = self.keyframes[0].zoom_scale
            end_z = self.keyframes[-1].zoom_scale
            # zoompan filter syntax: zoompan=z='zoom_expression':d=total_frames:s=WxH
            zoom_expr = f"min(zoom+{(end_z - start_z) / total_frames:.6f},{end_z:.3f})"
            return f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"

        elif self.motion_type == "whip_pan":
            pan_dist = self.keyframes[-1].pan_x if self.keyframes else 100.0
            return f"scale={int(width*1.15)}:{int(height*1.15)},crop={width}:{height}:'({pan_dist}/2)*(sin(2*PI*t/{dur}))':0"

        elif self.motion_type == "subwoofer_shake":
            return f"scale={int(width*1.1)}:{int(height*1.1)},crop={width}:{height}:'10*sin(50*t)':'10*cos(50*t)'"

        elif self.motion_type == "dutch_roll":
            max_deg = self.keyframes[-1].rotation_deg if self.keyframes else 5.0
            rad = max_deg * (math.pi / 180.0)
            return f"rotate='{rad:.4f}*sin(2*PI*t/{dur})':ow={width}:oh={height}"

        return f"scale={width}:{height}"


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

    @staticmethod
    def generate_subwoofer_shake(duration: float) -> CameraTrajectory:
        keyframes = [
            CameraKeyframe(0.0, 1.05, 0.0, 0.0, 0.0),
            CameraKeyframe(duration * 0.25, 1.08, 15.0, -10.0, 1.0),
            CameraKeyframe(duration * 0.5, 1.05, -15.0, 10.0, -1.0),
            CameraKeyframe(duration * 0.75, 1.08, 10.0, 15.0, 0.5),
            CameraKeyframe(duration, 1.0, 0.0, 0.0, 0.0)
        ]
        return CameraTrajectory(motion_type="subwoofer_shake", keyframes=keyframes)

    @staticmethod
    def generate_dutch_roll(duration: float, max_deg: float = 8.0) -> CameraTrajectory:
        kf1 = CameraKeyframe(0.0, 1.05, 0.0, 0.0, -max_deg)
        kf2 = CameraKeyframe(duration * 0.5, 1.08, 0.0, 0.0, 0.0)
        kf3 = CameraKeyframe(duration, 1.05, 0.0, 0.0, max_deg)
        return CameraTrajectory(motion_type="dutch_roll", keyframes=[kf1, kf2, kf3])
