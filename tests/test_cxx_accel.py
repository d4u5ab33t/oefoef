import numpy as np
import pytest
from cxx_accel.bridge import get_cxx_engine


def test_cxx_engine_initialization():
    engine = get_cxx_engine()
    info = engine.get_status_info()
    assert "engine_label" in info
    assert "version" in info


def test_score_candidates_batch():
    engine = get_cxx_engine()
    # [id, duration, motion_score, motion_direction, face_score, sem_match, pref_bonus, info_density, learned_bonus]
    matrix = np.array([
        [0, 5.0, 0.8, 0.5, 0.0, 0.9, 0.1, 0.8, 0.05],
        [1, 1.0, 0.2, -0.5, 0.0, 0.3, 0.0, 0.2, 0.0],
        [2, 4.0, 0.5, 0.0, 0.0, 0.5, 0.0, 0.5, 0.0],
    ], dtype=np.float32)

    scores = engine.score_candidates_batch(
        matrix,
        target_energy=0.85,
        target_duration=3.0,
        motion_weight=0.5,
        semantic_weight=0.5,
    )

    assert len(scores) == 3
    # Candidate 1 has duration 1.0 < 3.0 -> should be penalized (-1000)
    assert scores[1] < -500.0
    # Candidate 0 matches high energy (0.8 vs 0.85) and high semantic (0.9)
    assert scores[0] > scores[2]


def test_snap_beats_batch():
    engine = get_cxx_engine()
    cuts = [1.02, 2.45, 5.01]
    beats = [0.0, 1.0, 2.0, 2.5, 3.0, 4.0, 5.0]

    snapped = engine.snap_beats_batch(cuts, beats, tolerance_sec=0.15)
    assert snapped[0] == 1.0  # 1.02 snapped to 1.0
    assert snapped[1] == 2.5  # 2.45 snapped to 2.5
    assert snapped[2] == 5.0  # 5.01 snapped to 5.0


def test_evaluate_scene_metrics():
    engine = get_cxx_engine()
    shots = [
        {"clip": "c1.mp4", "duration": 2.0, "energy": 0.8, "sync_score": 0.9, "flow_score": 0.9},
        {"clip": "c2.mp4", "duration": 2.0, "energy": 0.8, "sync_score": 0.9, "flow_score": 0.85},
        {"clip": "c3.mp4", "duration": 2.0, "energy": 0.7, "sync_score": 0.85, "flow_score": 0.9},
    ]
    res = engine.evaluate_scene_metrics(shots, total_duration_sec=6.0, target_energy_avg=0.75)
    assert res["quality_score"] > 0.7
    assert res["unique_clips"] == 3
    assert res["duplicate_penalty"] == 0.0
    assert res["rating"] in ("EXCELLENT", "BALANCED")


def test_snap_transients_batch():
    engine = get_cxx_engine()
    targets = [1.02, 2.48, 5.04]
    transients = [1.00, 2.50, 4.20, 5.00]

    snapped = engine.snap_transients_batch(targets, transients, tolerance_sec=0.06)
    assert snapped[0] == 1.00  # 1.02 snapped to 1.00 (delta 0.02 <= 0.06)
    assert snapped[1] == 2.50  # 2.48 snapped to 2.50 (delta 0.02 <= 0.06)
    assert snapped[2] == 5.00  # 5.04 snapped to 5.00 (delta 0.04 <= 0.06)


def test_detect_accent_repetitions():
    engine = get_cxx_engine()
    # High-density drum onsets (e.g. 1/16 rolls around 2.0s)
    onsets = [0.0, 0.5, 1.0, 1.5, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5, 3.0, 4.0]
    bursts = engine.detect_accent_repetitions(onsets, window_sec=0.8, rate_threshold=5.0)
    assert len(bursts) >= 1
    # Check that the burst zone encompasses the 2.0-2.5s roll
    assert bursts[0][0] <= 2.0
    assert bursts[0][1] >= 2.4


def test_slice_drum_roll():
    engine = get_cxx_engine()
    # Segment from 1.0 to 2.0 with rapid drum onsets
    onsets = [0.5, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5]
    slices = engine.slice_drum_roll(1.0, 2.0, onsets, min_slice_sec=0.18, max_slices=4)
    assert len(slices) >= 2
    assert 1.25 in slices
    assert 1.5 in slices


def test_classify_timeline_batch():
    class DummySeg:
        def __init__(self, s, e, energy, sec='mid', struct='', density=0.0, motion=0.0, boundary=False, rep=False, clip='test.mp4'):
            self.start_sec = s
            self.end_sec = e
            self.target_energy = energy
            self.section_label = sec
            self.structure_label = struct
            self.information_density = density
            self.motion_direction = motion
            self.on_structure_boundary = boundary
            self.repetition = rep
            self.clip_path = clip

    tl = [
        DummySeg(0.0, 2.0, 0.2, 'low', 'intro'),
        DummySeg(2.0, 3.5, 0.8, 'high', 'hook', density=0.8, boundary=True),
        DummySeg(3.5, 4.0, 0.9, 'high', 'drop', rep=True),
        DummySeg(4.0, 6.0, 0.5, 'mid', ''),
        DummySeg(6.0, 8.0, 0.2, 'low', '')
    ]

    engine = get_cxx_engine()
    results = engine.classify_timeline_batch(tl)
    assert len(results) == 5
    assert results[0][0] == "intro"
    assert results[1][0] == "beat_drop"
    assert results[0][2] == "hard_cut"
    assert results[-1][2] == "fade_out"


def test_compute_timeline_reward():
    class DummySeg:
        def __init__(self, s, e, energy, clip='test.mp4'):
            self.start_sec = s
            self.end_sec = e
            self.target_energy = energy
            self.clip_path = clip

    tl = [
        DummySeg(0.0, 2.0, 0.6, 'clip1.mp4'),
        DummySeg(2.0, 4.0, 0.7, 'clip2.mp4'),
        DummySeg(4.0, 6.0, 0.8, 'clip3.mp4'),
    ]

    engine = get_cxx_engine()
    res = engine.compute_timeline_reward(tl, semantic_score=0.9)
    assert "reward" in res
    assert 0.0 <= res["reward"] <= 1.0
    assert res["unique_clips"] == 3
    assert res["consecutive_repeats"] == 0
    assert res["diversity_score"] == 1.0


def test_clean_stem():
    engine = get_cxx_engine()
    stem = engine.clean_stem("01 - Awesome Track (Remix) [feat. Artist].mp3")
    assert "Awesome" in stem
    assert "Track" in stem
    assert "  " not in stem
    assert "__" not in stem


def test_batch_cosine_similarity():
    engine = get_cxx_engine()
    q = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    m = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.7071, 0.7071, 0.0],
    ], dtype=np.float32)
    sims = engine.batch_cosine_similarity(q, m)
    assert len(sims) == 3
    assert abs(sims[0] - 1.0) < 1e-4
    assert abs(sims[1] - 0.0) < 1e-4
    assert abs(sims[2] - 0.7071) < 1e-3


def test_pick_start_point():
    engine = get_cxx_engine()
    # 10s clip, 2s segment, blocked in [1.0, 4.0]
    st = engine.pick_start_point(
        duration=10.0,
        seg_len=2.0,
        alternative_start_points=[2.0, 5.0],
        blocked_windows=[(1.0, 4.0)],
        seed=123
    )
    assert st is not None
    # 2.0 overlaps with [1.0, 4.0], so it must pick 5.0 or a free candidate >= 4.0
    assert st >= 4.0 or st + 2.0 <= 1.0


def test_snap_timeline_boundary():
    engine = get_cxx_engine()
    # Snapping with drop near 4.0
    snapped = engine.snap_timeline_boundary(
        t=1.0,
        end=3.8,
        seg_len=2.8,
        target_duration=10.0,
        drops=[4.0],
        downbeats=[2.0, 4.0, 6.0],
        beats=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    )
    assert abs(snapped - 4.0) < 1e-3


def test_compute_and_batch_semantic_scores():
    engine = get_cxx_engine()
    # Test single score
    score = engine.compute_semantic_score(
        vector_similarity=0.9,
        mood_score=0.8,
        gender_score=1.0,
        clip_cluster_mask=1 | 2,  # Weed | Urban
        song_cluster_mask=1,      # Weed
        object_grounding_score=0.8
    )
    assert score > 0.8

    # Test batch score
    candidates = [
        {"id": 0, "vector_similarity": 0.9, "mood_score": 0.8, "gender_score": 1.0, "cluster_mask": 1, "object_grounding_score": 0.8},
        {"id": 1, "vector_similarity": -0.5, "mood_score": 0.1, "gender_score": 0.0, "cluster_mask": 4, "object_grounding_score": -1.0},
    ]
    batch_res = engine.batch_semantic_scores(candidates, song_cluster_mask=1)
    assert len(batch_res) == 2
    assert batch_res[0] > 0.8
    assert batch_res[1] < 0.4


def test_vtree_acceleration():
    engine = get_cxx_engine()
    # Test cosine distance
    v1 = [1.0, 0.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0, 0.0]
    assert abs(engine.vtree_cosine_distance(v1, v2)) < 1e-4
    assert abs(engine.vtree_cosine_distance(v1, v3) - 1.0) < 1e-4

    # Test K-Means
    vectors = [
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.9, 0.1],
    ]
    centroids = engine.vtree_kmeans(vectors, k=2, max_iter=5)
    assert len(centroids) == 2

    # Test query candidates
    query_vec = [1.0, 0.0, 0.0]
    leaf_vecs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.8, 0.2, 0.0]]
    leaf_mots = [0.8, 0.2, 0.7]
    leaf_gens = [1, 0, 1]
    leaf_rews = [0.9, 0.3, 0.8]
    results = engine.vtree_query_candidates(
        query_vec=query_vec,
        leaf_vectors=leaf_vecs,
        leaf_motions=leaf_mots,
        leaf_genders=leaf_gens,
        leaf_rewards=leaf_rews,
        target_motion=0.8,
        target_gender=1,
        use_learned_priors=True,
        top_k=2
    )
    assert len(results) == 2
    assert results[0][0] == 0  # First leaf is best match


def test_self_learning_bandit_acceleration():
    engine = get_cxx_engine()
    # Test Thompson Beta sampling
    sample = engine.bandit_sample_thompson(total_reward=10.0, pulls=15, seed=42)
    assert 0.0 <= sample <= 1.0

    # Test Best Arm selection
    arms = [
        {"total_reward": 1.0, "pulls": 10},
        {"total_reward": 9.0, "pulls": 10},
        {"total_reward": 4.0, "pulls": 10},
    ]
    best_arm_ucb = engine.bandit_select_best_arm(arms, strategy="ucb1")
    assert best_arm_ucb == 1  # Arm 1 has highest reward

    # Test Markov transition bonus
    bonus = engine.markov_transition_bonus(reward_sum=8.0, count=10, same_motion_direction=True)
    assert bonus > 0.05

    # Test EMA update
    ema = engine.ema_update(current_val=0.5, target_val=1.0, learning_rate=0.2)
    assert abs(ema - 0.6) < 1e-4


def test_camera_kinematics_and_fake_3d():
    engine = get_cxx_engine()
    # Test trajectory sampling
    keyframes = [
        {"time_sec": 0.0, "zoom_scale": 1.0, "pan_x": 0.0, "pan_y": 0.0, "rotation_deg": 0.0, "focal_length_mm": 35.0},
        {"time_sec": 2.0, "zoom_scale": 1.2, "pan_x": 100.0, "pan_y": 50.0, "rotation_deg": 5.0, "focal_length_mm": 50.0},
    ]
    samples = engine.kinematics_sample_trajectory(keyframes, [1.0])
    assert len(samples) == 1
    assert abs(samples[0]["zoom_scale"] - 1.1) < 1e-2
    assert abs(samples[0]["pan_x"] - 50.0) < 1e-2
    assert abs(samples[0]["focal_length_mm"] - 42.5) < 1e-2

    # Test Fake 3D Trapezoid Warp
    coords = engine.kinematics_fake_3d_warp(t=1.0, duration=2.0, width=1920.0, height=1080.0, pitch_deg=4.0, yaw_deg=6.0)
    assert len(coords) == 8
    # Top-right corner X should be shifted left
    assert coords[2] < 1920.0


def test_compute_render_styles_batch():
    engine = get_cxx_engine()
    segs = [
        {"semantic_symbol": "BETON", "theme": "urban", "lighting": "lowkey", "color": "desaturated", "fx": ("grain",)},
        {"semantic_symbol": "CYBER", "theme": "glitch", "lighting": "neon_backlight", "color": "neon", "fx": ("chroma", "scanlines")},
        {"semantic_symbol": "WEED", "theme": "chill", "lighting": "dramatic", "color": "matrix_green", "fx": ("vignette",)},
    ]
    res = engine.compute_render_styles_batch(segs)
    assert len(res) == 3

    # Segment 0 (Beton): Desaturated and lowkey contrast
    assert res[0]["saturation_mult"] < 0.5
    assert res[0]["contrast_mult"] > 1.1
    assert res[0]["fx_mask"] & (1 << 0)  # grain bit

    # Segment 1 (Cyber): High saturation, neon color balance
    assert res[1]["saturation_mult"] > 1.3
    assert res[1]["color_balance_b"] > 0.05
    assert res[1]["fx_mask"] & (1 << 2)  # chroma bit
    assert res[1]["fx_mask"] & (1 << 4)  # scanlines bit

    # Segment 2 (Weed): Emerald green balance, dramatic contrast
    assert res[2]["color_balance_g"] > 0.05
    assert res[2]["fx_mask"] & (1 << 3)  # vignette bit


def test_calculate_lyrics_grounding():
    engine = get_cxx_engine()
    lyrics = ["oida", "rap", "münchen", "beat", "bass", "street"]
    clip_match = ["street", "night", "münchen", "lights", "crew", "rap"]
    clip_unrelated = ["forest", "river", "mountain", "cloud"]

    score_match = engine.calculate_lyrics_grounding(lyrics, clip_match)
    score_unrelated = engine.calculate_lyrics_grounding(lyrics, clip_unrelated)

    assert score_match > 0.4
    assert score_unrelated == 0.0





