"""
test_cinematic_camera.py — Tests for v0.7 Cinematic Camera components.
"""
import pytest
import json
from genome_engine.camera.kinematics import KinematicsEngine, CameraTrajectory
from genome_engine.camera.unreal_bridge import UnrealCameraExporter


def test_push_zoom_kinematics():
    traj = KinematicsEngine.generate_push_zoom(duration=4.0, start_scale=1.0, end_scale=1.2)
    assert traj.motion_type == "push_zoom"
    assert len(traj.keyframes) == 2

    kf_mid = traj.sample_at(2.0)
    assert kf_mid.zoom_scale == pytest.approx(1.1)
    assert kf_mid.focal_length_mm == pytest.approx(42.5)


def test_unreal_export():
    traj = KinematicsEngine.generate_push_zoom(duration=2.0)
    json_str = UnrealCameraExporter.export_to_unreal_json(traj)
    
    parsed = json.loads(json_str)
    assert parsed["cine_camera_name"].startswith("GenomeCamera_")
    assert parsed["aspect_ratio"] == 2.39
    assert len(parsed["keyframes"]) == 2
