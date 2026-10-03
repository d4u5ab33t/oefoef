"""
test_story_clustering.py — Tests for Clip Content Grouping, Story Clustering & Video Quality Preservation.
"""
import pytest
from audio_analysis import AudioAnalysis
import config
from timeline_builder import build_timeline, _pick_clip, PrecomputedClip
from renderer import _color_grade_filter, _semantic_motif_grade_filter, _plan_segment_filter, TimelineSegment


def test_story_clustering_constants():
    """Verify that color filters are disabled and story clustering parameters are active."""
    assert config.STYLE_COLOR_GRADE_ENABLED is False
    assert config.CLIP_CLUSTER_SIM_THRESHOLD >= 0.70
    assert config.STORY_CLUSTER_STICKINESS >= 0.70
    assert config.STORY_CLUSTER_BONUS >= 0.20
    assert config.STORY_SWITCH_ON_STRUCTURE_CHANGE is True


def test_pristine_quality_filterchain_no_color_filter():
    """Verify that _plan_segment_filter uses Lanczos scaling and produces clean, unpolluted output without color balance/eq filters."""
    seg = TimelineSegment(
        start_sec=0.0,
        end_sec=2.0,
        clip_path="sample.mp4",
        clip_in_point=0.0,
        lighting="lowkey",
        color="vivid",
        semantic_symbol="BETON",
        theme="urban"
    )
    vf = _plan_segment_filter(seg, duration=2.0, src_dims=(1920, 1080), w=1920, h=1080)
    
    # Check that high-quality Lanczos scaling is enforced
    assert "flags=lanczos" in vf
    # Check that color grading and motif grading are omitted when STYLE_COLOR_GRADE_ENABLED is False
    assert "colorbalance" not in vf
    assert "saturation=1.35" not in vf
    assert "contrast=1.20" not in vf


def test_pick_clip_story_clustering_bonus():
    """Verify that clips matching active story tags receive the clustering bonus."""
    clip_a = PrecomputedClip(
        path="clip_a.mp4",
        meta={"duration": 5.0, "tags": ["street", "graffiti", "urban"]},
        duration=5.0,
        motion_score=0.5,
        motion_direction=0.0,
        face_score=0.0,
        semantic_match=0.7,
        pref_bonus=0.0,
        info_density=0.5,
        tags_set=frozenset(["street", "graffiti", "urban"]),
        vector_sim_raw=0.7,
        alt_starts=[],
        bad_windows=(),
        effect_allow_still=False,
        domain="URBAN_STREET",
    )
    clip_b = PrecomputedClip(
        path="clip_b.mp4",
        meta={"duration": 5.0, "tags": ["nature", "forest", "mountain"]},
        duration=5.0,
        motion_score=0.5,
        motion_direction=0.0,
        face_score=0.0,
        semantic_match=0.7,
        pref_bonus=0.0,
        info_density=0.5,
        tags_set=frozenset(["nature", "forest", "mountain"]),
        vector_sim_raw=0.7,
        alt_starts=[],
        bad_windows=(),
        effect_allow_still=False,
        domain="NATURE",
    )

    globe = {
        "clip_a.mp4": {"duration": 5.0, "playback_ok": True, "tags": ["street", "graffiti", "urban"], "motion_direction": 0.0},
        "clip_b.mp4": {"duration": 5.0, "playback_ok": True, "tags": ["nature", "forest", "mountain"], "motion_direction": 0.0},
    }

    # When active story tags are ['street', 'graffiti'], clip_a should be chosen over clip_b
    chosen_path, _, chosen_domain = _pick_clip(
        song_vector=[0.5] * 24,
        globe=globe,
        section_label="mid",
        seg_len=2.0,
        blocked_ranges={},
        precomputed_pool=[clip_a, clip_b],
        active_story_tags=frozenset(["street", "graffiti", "urban"]),
        active_story_domain="URBAN_STREET"
    )

    assert chosen_path == "clip_a.mp4"
    assert chosen_domain == "URBAN_STREET"
