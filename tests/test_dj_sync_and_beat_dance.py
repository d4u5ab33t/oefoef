"""
tests/test_dj_sync_and_beat_dance.py — Tests for DJ Sync Action Recognition, Smooth Stutter & Beat-Dancing Kinematics
"""
import pytest
import numpy as np

from audio_analysis import _detect_dj_sync_actions, AudioAnalysis
from clip_pool import _dj_action_score, get_clip_dj_action_score, analyze_clip
from config import (
    DJ_SYNC_ACTION_ENABLED,
    DJ_SYNC_ACTION_BOOST,
    SMOOTH_STUTTER_ENABLED,
    SMOOTH_STUTTER_HIGHLIGHT_ONLY,
    SMOOTH_STUTTER_ENERGY_THRESH,
    SMOOTH_STUTTER_OPACITY,
    BEAT_DANCE_ENABLED,
    BEAT_DANCE_AMPLITUDE,
    BEAT_DANCE_SWAY_AMPLITUDE,
    TAG_VOCAB,
)
from timeline_builder import (
    PrecomputedClip,
    precompute_candidates,
    build_timeline,
    TimelineSegment,
)
from renderer import (
    _smooth_stutter_filter,
    _zoompan_filter,
    _plan_segment_filter,
    _plan_camera,
)


class TestDJSyncActionAudioDetection:
    def test_detect_dj_scratch_actions(self):
        duration_sec = 10.0
        sr = 22050
        # Synthetic audio
        y = np.sin(2 * np.pi * 440 * np.linspace(0, duration_sec, sr * int(duration_sec)))
        onset_times = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        structure = [
            (0.0, 2.0, "intro"),
            (2.0, 5.0, "hook"),
            (5.0, 8.0, "verse"),
            (8.0, 10.0, "outro"),
        ]
        drop_times = [2.0]
        drum_accents = [{"time": 4.0, "strength": 0.85, "kind": "roll", "duration": 0.3}]
        scratch_events = [{"time": 1.0, "strength": 0.9, "kind": "detected"}]

        actions = _detect_dj_sync_actions(
            y=y,
            sr=sr,
            onset_times=onset_times,
            duration_sec=duration_sec,
            structure=structure,
            drop_times=drop_times,
            drum_accents=drum_accents,
            scratch_events=scratch_events,
        )

        assert isinstance(actions, list)
        action_types = [a["action"] for a in actions]
        assert "scratch" in action_types
        assert "drop_impact" in action_types
        assert "beat_juggle" in action_types

    def test_detect_dj_actions_empty_audio(self):
        actions = _detect_dj_sync_actions(
            y=np.array([]),
            sr=22050,
            onset_times=np.array([]),
            duration_sec=0.0,
            structure=[],
            drop_times=[],
            drum_accents=[],
            scratch_events=[],
        )
        assert actions == []


class TestDJClipPoolScoring:
    def test_dj_action_score_with_dj_tags(self):
        tags = ["turntable", "vinyl", "scratching", "club"]
        score = _dj_action_score(tags, motion_score=0.7, face_score=0.5, path="dj_deck_scratch.mp4")
        assert score >= 0.70
        assert score <= 1.0

    def test_dj_action_score_with_motion_only(self):
        tags = ["car", "road"]
        score = _dj_action_score(tags, motion_score=0.8, face_score=0.0, path="highway.mp4")
        assert score >= 0.0
        assert score <= 0.35

    def test_dj_action_score_empty(self):
        score = _dj_action_score([], motion_score=0.0, face_score=0.0, path="still.mp4")
        assert score == 0.0

    def test_get_clip_dj_action_score_from_meta(self):
        meta_precalc = {"dj_action_score": 0.85}
        assert get_clip_dj_action_score(meta_precalc) == 0.85

        meta_computed = {
            "tags": ["mixer", "crossfader", "dj"],
            "motion_score": 0.6,
            "face_score": 0.4,
            "path": "live_performance.mp4",
        }
        score = get_clip_dj_action_score(meta_computed)
        assert score > 0.60


class TestTimelineDJSyncAndStutter:
    def test_precompute_candidates_includes_dj_action_score(self):
        globe = {
            "dj_turntable.mp4": {
                "duration": 5.0,
                "motion_score": 0.65,
                "face_score": 0.4,
                "tags": ["dj", "turntable", "scratching"],
                "vector": [0.1] * len(TAG_VOCAB),
                "playback_ok": True,
            },
            "nature_calm.mp4": {
                "duration": 5.0,
                "motion_score": 0.1,
                "face_score": 0.0,
                "tags": ["forest", "trees"],
                "vector": [0.0] * len(TAG_VOCAB),
                "playback_ok": True,
            },
        }
        song_vec = [0.1] * len(TAG_VOCAB)
        pool, fallbacks = precompute_candidates(globe, song_vector=song_vec)
        assert len(pool) == 2
        c_dj = next(c for c in pool if "dj_turntable" in c.path)
        c_nat = next(c for c in pool if "nature_calm" in c.path)
        assert c_dj.dj_action_score > 0.60
        assert c_nat.dj_action_score < 0.20

    def test_build_timeline_dj_action_and_stutter_wiring(self):
        # Mock AudioAnalysis with DJ actions and high BPM
        audio = AudioAnalysis(
            bpm=135.0,
            duration_sec=8.0,
            beat_times=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
            energy=[0.4, 0.5, 0.85, 0.90, 0.88, 0.6, 0.5, 0.4, 0.3],
            sections=[
                (0.0, 2.0, "low"),
                (2.0, 4.0, "high"),
                (4.0, 6.0, "mid"),
                (6.0, 8.0, "low"),
            ],
            downbeats=[0.0, 2.0, 4.0, 6.0],
            structure=[
                (0.0, 2.0, "intro"),
                (2.0, 4.0, "hook"),
                (4.0, 6.0, "verse"),
                (6.0, 8.0, "outro"),
            ],
            dj_actions=[
                {"time": 2.0, "action": "backspin", "strength": 0.92, "kind": "detected", "duration": 0.3},
                {"time": 4.0, "action": "scratch", "strength": 0.88, "kind": "detected", "duration": 0.2},
            ],
        )

        globe = {
            "clip_dj.mp4": {
                "duration": 10.0,
                "motion_score": 0.7,
                "face_score": 0.5,
                "tags": ["dj", "turntable", "scratching"],
                "vector": [0.1] * len(TAG_VOCAB),
                "playback_ok": True,
            },
            "clip_general.mp4": {
                "duration": 10.0,
                "motion_score": 0.4,
                "face_score": 0.0,
                "tags": ["city"],
                "vector": [0.05] * len(TAG_VOCAB),
                "playback_ok": True,
            },
        }

        song_vec = [0.1] * len(TAG_VOCAB)
        timeline = build_timeline(song_vec, audio, globe, recent_used=[])
        assert len(timeline) >= 2

        # Check audio_bpm propagation
        for seg in timeline:
            assert seg.audio_bpm == 135.0

        # Segments near t=2.0 and t=4.0 should have dj_action and smooth_stutter flagged
        dj_segs = [seg for seg in timeline if seg.dj_action != "none"]
        assert len(dj_segs) > 0

        stutter_segs = [seg for seg in timeline if seg.smooth_stutter]
        assert len(stutter_segs) > 0


class TestRendererBeatDancingAndSmoothStutter:
    def test_smooth_stutter_filter_active(self):
        flt = _smooth_stutter_filter(smooth_stutter=True, duration=2.5)
        assert flt != ""
        assert "contrast='1+" in flt
        assert "brightness='0.02*" in flt

    def test_smooth_stutter_filter_inactive(self):
        flt_disabled = _smooth_stutter_filter(smooth_stutter=False, duration=2.5)
        assert flt_disabled == ""

        flt_zero_dur = _smooth_stutter_filter(smooth_stutter=True, duration=0.0)
        assert flt_zero_dur == ""

    def test_zoompan_beat_dancing_kinematics(self):
        cam_plan = {
            "movement": "drift",
            "start_zoom": 1.0,
            "end_zoom": 1.08,
            "punch_fraction": None,
            "pan_x": 0.05,
            "pan_y": 0.0,
            "direction": 1,
            "bpm": 140.0,
        }
        flt = _zoompan_filter(cam_plan, duration=2.0, fps=30, w=1920, h=1080)
        assert "zoompan=" in flt
        if BEAT_DANCE_ENABLED:
            assert "cos(2*PI*" in flt
            assert "sin(2*PI*" in flt

    def test_plan_segment_filter_smooth_stutter_integration(self):
        seg = TimelineSegment(
            start_sec=0.0,
            end_sec=2.5,
            clip_path="sample.mp4",
            clip_in_point=0.0,
            transition="cut",
            motion_score=0.6,
            dj_action="scratch",
            smooth_stutter=True,
            audio_bpm=128.0,
        )
        src_dims = (1920, 1080)
        vf = _plan_segment_filter(seg, duration=2.5, src_dims=src_dims, w=1920, h=1080)
        assert "zoompan=" in vf
        assert "contrast=" in vf
