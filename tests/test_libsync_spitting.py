"""
tests/test_libsync_spitting.py — Tests für LibSync MC Rapper Spitting, Flow Cadence Tracking & Lip-Sync
"""
import pytest
import numpy as np

from audio_analysis import _detect_spitting_bursts, AudioAnalysis
from clip_pool import _spitting_score, get_clip_spitting_score
from config import (
    LIBSYNC_SPITTING_ENABLED,
    LIBSYNC_CADENCE_RATE_THRESHOLD,
    LIBSYNC_PERFORMANCE_BOOST,
    LIBSYNC_CADENCE_ZOOM_PULSE,
)
from timeline_builder import (
    PrecomputedClip,
    precompute_candidates,
    build_timeline,
    TimelineSegment,
)
from renderer import _apply_cut_sync_zoom_modifiers


class TestLibSyncSpittingScoring:
    def test_spitting_score_with_spitting_tags_and_face(self):
        tags = ["rapper", "spit", "microphone", "performance"]
        score = _spitting_score(tags, face_score=0.8, motion_score=0.5, path="rap_mc_flow.mp4")
        assert score >= 0.75
        assert score <= 1.0

    def test_spitting_score_with_face_only(self):
        tags = ["nature", "forest"]
        score = _spitting_score(tags, face_score=0.9, motion_score=0.5, path="woods.mp4")
        assert score > 0.0
        assert score <= 0.70

    def test_spitting_score_with_tags_only(self):
        tags = ["spit", "bars", "freestyle"]
        score = _spitting_score(tags, face_score=0.0, motion_score=0.5, path="audio_bars.mp4")
        assert score > 0.0

    def test_spitting_score_empty(self):
        score = _spitting_score([], face_score=0.0, motion_score=0.5, path="landscape.mp4")
        assert score == 0.0

    def test_get_clip_spitting_score_from_meta(self):
        meta_with_field = {"spitting_score": 0.88}
        assert get_clip_spitting_score(meta_with_field) == 0.88

        meta_computed = {
            "tags": ["rapper", "mic"],
            "face_score": 0.75,
            "motion_score": 0.45,
            "path": "mc_stage.mp4",
        }
        score = get_clip_spitting_score(meta_computed)
        assert score > 0.60


class TestLibSyncCadenceDetection:
    def test_detect_spitting_bursts_high_cadence(self):
        # 10 onsets within 2 seconds -> 5 onsets/sec >= threshold (3.2)
        onsets = np.linspace(2.0, 4.0, 11)
        duration_sec = 10.0
        bursts, cadence_hz = _detect_spitting_bursts(onsets, duration_sec, window_sec=1.2, rate_threshold=3.2)
        assert len(bursts) >= 1
        start, end, rate = bursts[0]
        assert start <= 2.5
        assert end >= 3.5
        assert rate >= 3.2
        assert cadence_hz > 0.0

    def test_detect_spitting_bursts_low_cadence(self):
        # 2 onsets in 10 seconds -> low cadence
        onsets = np.array([2.0, 7.0])
        duration_sec = 10.0
        bursts, cadence_hz = _detect_spitting_bursts(onsets, duration_sec, window_sec=1.2, rate_threshold=3.2)
        assert len(bursts) == 0

    def test_detect_spitting_bursts_empty(self):
        bursts, cadence_hz = _detect_spitting_bursts([], 10.0)
        assert bursts == []
        assert cadence_hz == 0.0


class TestLibSyncTimelineIntegration:
    def test_precompute_candidates_includes_spitting_score(self):
        globe = {
            "clip_rap.mp4": {
                "duration": 5.0,
                "motion_score": 0.5,
                "face_score": 0.8,
                "tags": ["rapper", "mic", "spit"],
                "playback_ok": True,
            },
            "clip_bg.mp4": {
                "duration": 5.0,
                "motion_score": 0.5,
                "face_score": 0.0,
                "tags": ["ambient"],
                "playback_ok": True,
            },
        }
        pool, _ = precompute_candidates(globe, song_vector=[1.0, 0.0])
        spit_clip = next(c for c in pool if c.path == "clip_rap.mp4")
        bg_clip = next(c for c in pool if c.path == "clip_bg.mp4")
        assert spit_clip.spitting_score > 0.7
        assert bg_clip.spitting_score == 0.0

    def test_build_timeline_assigns_lip_sync_in_spitting_burst(self):
        audio = AudioAnalysis(
            bpm=120.0,
            duration_sec=6.0,
            beat_times=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5],
            energy=[0.6] * 12,
            sections=[(0.0, 6.0, "mid")],
            downbeats=[0.0, 2.0, 4.0],
            loudness_db=-10.0,
            groove=0.5,
            spectral_flux=0.5,
            harmonic_change=0.5,
            vocal_activity=0.8,
            drop_times=[],
            music_dna={},
            mc_gender="male",
            vocal_pitch_hz=130.0,
            repetition_windows=[],
            structure=[(0.0, 6.0, "verse")],
            stems={},
            scratch_events=[],
            drum_accents=[],
            drum_onsets=[],
            vocal_onsets=[1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4],
            spitting_burst_windows=[(1.0, 2.6, 4.5)],
            vocal_cadence_hz=4.5,
        )

        globe = {
            "clip_spit.mp4": {
                "duration": 10.0,
                "motion_score": 0.5,
                "face_score": 0.85,
                "tags": ["rapper", "spit", "mic", "performance"],
                "gender_vector": {"male": ["rapper"], "female": [], "unknown": False},
                "playback_ok": True,
            },
            "clip_city.mp4": {
                "duration": 10.0,
                "motion_score": 0.5,
                "face_score": 0.0,
                "tags": ["urban", "street", "building"],
                "playback_ok": True,
            },
        }

        timeline = build_timeline(
            song_vector=[0.5] * 24,
            audio=audio,
            globe=globe,
            recent_used=[],
        )

        assert len(timeline) >= 2
        spitting_segs = [seg for seg in timeline if 1.0 <= seg.start_sec < 2.6]
        assert len(spitting_segs) > 0
        for s in spitting_segs:
            assert s.sync_type == "lip_sync"
            assert s.camera == "focus_zoom"
            assert s.cut_style == "whip"


class TestLibSyncRendererZoomModifier:
    def test_apply_cut_sync_zoom_modifiers_lip_sync(self):
        plan = {
            "movement": "focus_zoom",
            "start_zoom": 1.0,
            "end_zoom": 1.2,
            "pan_x": 0.10,
            "pan_y": 0.06,
        }
        seg = TimelineSegment(
            start_sec=1.0,
            end_sec=2.5,
            clip_path="clip.mp4",
            clip_in_point=0.0,
            sync_type="lip_sync",
        )
        mod_plan = _apply_cut_sync_zoom_modifiers(plan, seg)
        assert mod_plan is not None
        # hub was 0.2, with LIBSYNC_CADENCE_ZOOM_PULSE (1.18) -> 0.236
        expected_hub = min(0.5, 0.2 * LIBSYNC_CADENCE_ZOOM_PULSE)
        assert abs((mod_plan["end_zoom"] - mod_plan["start_zoom"]) - expected_hub) < 1e-4
        # pan_x and pan_y are centered / dampened by 0.5 for face stability
        assert abs(mod_plan["pan_x"] - 0.05) < 1e-4
        assert abs(mod_plan["pan_y"] - 0.03) < 1e-4
