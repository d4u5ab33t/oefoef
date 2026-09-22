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

    ffmpeg_filter = traj.to_ffmpeg_filter(1920, 1080, 30.0)
    assert "zoompan" in ffmpeg_filter


def test_subwoofer_shake_and_dutch_roll():
    shake = KinematicsEngine.generate_subwoofer_shake(duration=2.0)
    assert shake.motion_type == "subwoofer_shake"
    filter_str = shake.to_ffmpeg_filter(1920, 1080)
    assert "crop=" in filter_str

    roll = KinematicsEngine.generate_dutch_roll(duration=3.0, max_deg=10.0)
    assert roll.motion_type == "dutch_roll"
    roll_filter = roll.to_ffmpeg_filter(1920, 1080)
    assert "rotate=" in roll_filter


def test_unreal_export():
    traj = KinematicsEngine.generate_push_zoom(duration=2.0)
    json_str = UnrealCameraExporter.export_to_unreal_json(traj)
    
    parsed = json.loads(json_str)
    assert parsed["cine_camera_name"].startswith("GenomeCamera_")
    assert parsed["aspect_ratio"] == 2.39
    assert len(parsed["keyframes"]) == 2
