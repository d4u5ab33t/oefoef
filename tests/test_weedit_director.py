"""
tests/test_weedit_director.py — Unit & Integration tests for WE.ED.IT 1-Click Director Engine
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

from weedit_director import WeEditDirector
from audio_analysis import AudioAnalysis
from config import TAG_VOCAB


def test_weedit_director_initialization():
    logs = []
    director = WeEditDirector(platform="full", log_fn=logs.append)
    assert director.platform == "full"
    assert director.cxx is not None
    assert any("C++ Accel" in msg for msg in logs)


def test_weedit_director_mock_single_song(tmp_path):
    logs = []
    director = WeEditDirector(platform="full", log_fn=logs.append)

    # Create dummy song file
    fake_song = tmp_path / "test_track.mp3"
    fake_song.write_bytes(b"dummy mp3 data")

    # Mock audio analysis
    mock_audio = AudioAnalysis(
        bpm=130.0,
        duration_sec=6.0,
        beat_times=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        energy=[0.5, 0.6, 0.8, 0.9, 0.7, 0.5, 0.4],
        sections=[(0.0, 3.0, "low"), (3.0, 6.0, "high")],
        downbeats=[0.0, 2.0, 4.0],
        structure=[(0.0, 3.0, "verse"), (3.0, 6.0, "hook")],
        dj_actions=[{"time": 3.0, "action": "drop_impact", "strength": 0.9, "kind": "detected", "duration": 0.3}],
        spitting_burst_windows=[(1.0, 3.0, 6.0)],
        vocal_cadence_hz=4.5,
    )

    globe = {
        "clip1.mp4": {
            "duration": 5.0,
            "motion_score": 0.7,
            "face_score": 0.6,
            "tags": ["rapper", "spit", "dj", "turntable"],
            "vector": [0.1] * len(TAG_VOCAB),
            "playback_ok": True,
        },
        "clip2.mp4": {
            "duration": 5.0,
            "motion_score": 0.4,
            "face_score": 0.0,
            "tags": ["city", "night"],
            "vector": [0.0] * len(TAG_VOCAB),
            "playback_ok": True,
        },
    }

    out_file = tmp_path / "test_track.mp4"

    with patch("audio_analysis.analyze_song", return_value=mock_audio), \
         patch("renderer.render_music_video", return_value=str(out_file)):
        
        # Simulate render file creation
        out_file.write_bytes(b"video mp4 data")
        
        res = director.process_single_song(
            song_path=fake_song,
            globe=globe,
            output_dir=tmp_path,
        )

        assert res == str(out_file)
        assert any("[1/6]" in msg for msg in logs)
        assert any("[2/6]" in msg for msg in logs)
        assert any("[3/6]" in msg for msg in logs)
        assert any("FERTIG" in msg for msg in logs)


def test_weedit_director_batch_processing(tmp_path):
    logs = []
    director = WeEditDirector(platform="full", log_fn=logs.append)

    # Create multiple fake songs
    for i in range(3):
        p = tmp_path / f"song_{i}.mp3"
        p.write_bytes(b"dummy mp3 data")

    with patch.object(director, "load_clip_globe", return_value={}), \
         patch.object(director, "process_single_song", side_effect=lambda s, globe, **kw: str(tmp_path / f"{Path(s).stem}.mp4")):
        
        results = director.process_batch(tmp_path, limit=2)
        assert len(results) == 2
        assert any("BATCH ABGESCHLOSSEN: 2/2" in msg for msg in logs)
