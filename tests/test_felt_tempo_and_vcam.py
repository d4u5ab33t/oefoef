"""
test_felt_tempo_and_vcam.py — Tests for Felt Tempo (70 vs 140 BPM), Eyecannndy VCAM and Stem Doubling.
"""
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from audio_analysis import _detect_felt_tempo_and_rhythm_feel, AudioAnalysis
from renderer import _fx_filter, _plan_camera_raw
from stem_separator import create_stem_doubles, verify_stem_phase
from timeline_builder import TimelineSegment


def test_felt_tempo_half_time_and_double_time():
    sr = 22050
    duration = 8.0
    bpm = 140.0
    # 140 BPM = 0.42857 s per beat
    beat_step = 60.0 / bpm
    beat_times = [round(i * beat_step, 3) for i in range(16)]

    # Test dummy audio
    y = np.zeros(int(sr * duration), dtype=np.float32)

    felt_bpm, tempo_feel, time_sig, snares, kicks = _detect_felt_tempo_and_rhythm_feel(
        y, sr, beat_times, bpm, np.array([])
    )

    assert felt_bpm in (70.0, 140.0)
    assert tempo_feel in ("half_time", "double_time")
    assert time_sig == "4/4"


def test_eyecannndy_vcam_fx_filters():
    flt = _fx_filter(("snorricam_strobe", "void_slitscan", "coffin_crop", "tableau_hold"), duration=3.0)
    assert "contrast=1.6" in flt
    assert "rgbashift=" in flt
    assert "vignette=" in flt
    assert "contrast=1.28" in flt


def test_eyecannndy_camera_plan_movements():
    seg = TimelineSegment(
        start_sec=0.0, end_sec=2.0,
        clip_path="clip.mp4", clip_in_point=0.0,
        camera="whip_pan_dolly", motion_score=0.4, motion_direction=0.5
    )
    plan_whip = _plan_camera_raw(seg, 2.0, (1920, 1080), 1920, 1080)
    assert plan_whip["movement"] == "whip_pan_dolly"
    assert plan_whip["end_zoom"] == 1.25

    seg.camera = "snorricam"
    plan_snorri = _plan_camera_raw(seg, 2.0, (1920, 1080), 1920, 1080)
    assert plan_snorri["movement"] == "snorricam"

    seg.camera = "overhead"
    plan_overhead = _plan_camera_raw(seg, 2.0, (1920, 1080), 1920, 1080)
    assert plan_overhead["movement"] == "overhead"


def test_stem_doubles_generation(monkeypatch, tmp_path):
    import subprocess

    def mock_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        out_file = Path(cmd[-1])
        out_file.touch()
        return res

    monkeypatch.setattr(subprocess, "run", mock_run)

    dummy_voc = tmp_path / "song__vocals.mp3"
    dummy_bass = tmp_path / "song__bass.mp3"
    dummy_voc.touch()
    dummy_bass.touch()

    stems = {"vocals": str(dummy_voc), "bass": str(dummy_bass)}
    doubles = create_stem_doubles(stems, tmp_path)

    assert "vocals_double" in doubles
    assert "bass_double" in doubles
    assert Path(doubles["vocals_double"]).is_file()
    assert Path(doubles["bass_double"]).is_file()


def test_verify_stem_phase():
    corr = verify_stem_phase("nonexistent_a.mp3", "nonexistent_b.mp3")
    assert corr == 1.0
