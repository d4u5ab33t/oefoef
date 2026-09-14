"""
unreal_bridge.py — Exporter for Unreal Engine CineCamera sequences.
"""
import json
from typing import Dict, Any
from genome_engine.camera.kinematics import CameraTrajectory


class UnrealCameraExporter:
    """Converts CameraTrajectory data into JSON for Unreal Engine python automation."""

    @staticmethod
    def export_to_unreal_json(trajectory: CameraTrajectory) -> str:
        data: Dict[str, Any] = {
            "cine_camera_name": f"GenomeCamera_{trajectory.motion_type}",
            "aspect_ratio": trajectory.letterbox_aspect,
            "motion_type": trajectory.motion_type,
            "keyframes": [
                {
                    "time": kf.time_sec,
                    "transform": {
                        "location": [kf.pan_x, 0.0, kf.pan_y],
                        "rotation": [0.0, kf.rotation_deg, 0.0]
                    },
                    "focal_length": kf.focal_length_mm,
                    "zoom_scale": kf.zoom_scale
                }
                for kf in trajectory.keyframes
            ]
        }
        return json.dumps(data, indent=2)
