"""
test_cxx_extended_stacks.py — Unit & Integration tests for extended C++20 AVX2 Native Acceleration Stacks.
"""
import pytest
import numpy as np
from cxx_accel import get_cxx_engine
import mp3_scanner


def test_cxx_engine_v3_version_and_health():
    engine = get_cxx_engine()
    status = engine.get_status_info()
    assert "Native Engine" in status["version"] or "v4.0" in status["version"] or "v3.0" in status["version"] or "SIMD" in status["engine_label"]
    assert engine.is_native_active


def test_cxx_tag_vectorizer():
    engine = get_cxx_engine()
    # Test single text vectorization
    text = "oida 089 munich graffiti weed 420 action drift"
    vec = engine.build_tag_vector(text, dim=85)
    assert len(vec) == 85
    assert vec[0] == 1.0  # action
    assert sum(vec) >= 5.0

    # Test batch vectorization
    texts = [
        "oidaheim beton 089",
        "cyber synth matrix",
        "weed blunt joint 420",
    ]
    mat = engine.batch_build_tag_vectors(texts, dim=85)
    assert mat.shape == (3, 85)
    assert mat[0, 85 - 11] == 1.0 or sum(mat[0]) >= 1.0
    assert sum(mat[2]) >= 3.0

    # Test integration in mp3_scanner
    from config import TAG_VOCAB
    mp3_vec = mp3_scanner.build_tag_vector(["oida", "089", "drift", "bmw"])
    assert len(mp3_vec) == len(TAG_VOCAB)
    assert sum(mp3_vec) >= 2.0


def test_cxx_candidate_ranker():
    engine = get_cxx_engine()
    query_vec = [1.0, 0.0, 1.0, 0.0] + [0.0] * 81
    
    # 5 dummy candidates
    matrix = np.zeros((5, 85), dtype=np.float32)
    matrix[0, 0] = 1.0; matrix[0, 2] = 1.0  # Perfect match
    matrix[1, 0] = 1.0                      # Partial match
    matrix[2, 5] = 1.0                      # No match
    matrix[3, 0] = 1.0; matrix[3, 2] = 1.0  # Perfect match but locked
    matrix[4, 0] = 1.0; matrix[4, 2] = 1.0  # Perfect match with high density

    metas = [
        {"duration": 5.0, "motion_score": 0.8, "motion_direction": 0.5, "face_score": 0.0, "information_density": 0.5, "learned_bonus": 0.1, "gender": "neutral", "is_still": 0, "is_cooldown_locked": 0},
        {"duration": 5.0, "motion_score": 0.5, "motion_direction": 0.0, "face_score": 0.0, "information_density": 0.4, "learned_bonus": 0.0, "gender": "neutral", "is_still": 0, "is_cooldown_locked": 0},
        {"duration": 5.0, "motion_score": 0.2, "motion_direction": 0.0, "face_score": 0.0, "information_density": 0.2, "learned_bonus": 0.0, "gender": "neutral", "is_still": 0, "is_cooldown_locked": 0},
        {"duration": 5.0, "motion_score": 0.8, "motion_direction": 0.5, "face_score": 0.0, "information_density": 0.5, "learned_bonus": 0.1, "gender": "neutral", "is_still": 0, "is_cooldown_locked": 1},
        {"duration": 5.0, "motion_score": 0.8, "motion_direction": 0.5, "face_score": 0.0, "information_density": 0.9, "learned_bonus": 0.2, "gender": "neutral", "is_still": 0, "is_cooldown_locked": 0},
    ]

    ctx = {
        "target_energy": 0.8,
        "target_duration": 3.0,
        "motion_weight": 0.35,
        "semantic_weight": 0.40,
        "pref_weight": 0.15,
        "density_weight": 0.10,
        "prev_motion_dir": 0.5,
        "target_gender_code": 0,
        "allow_still": False,
        "check_motion_continuity": True
    }

    ranked = engine.rank_topk_candidates(query_vec, matrix, metas, ctx, top_k=3)
    assert len(ranked) == 3
    # Candidate 3 is locked, so only 4, 0, 1, 2 remain
    indices = [r[0] for r in ranked]
    assert 3 not in indices
    assert indices[0] == 4  # Highest density and bonus

    # Test Native Candidate Matrix Scoring (N, 9)
    c_mat = np.zeros((3, 9), dtype=np.float32)
    c_mat[0, :] = [0, 5.0, 0.8, 0.5, 0.0, 0.9, 0.1, 0.5, 0.1]
    c_mat[1, :] = [1, 1.0, 0.8, 0.5, 0.0, 0.9, 0.1, 0.5, 0.1]  # Too short for target_duration 3.0
    c_mat[2, :] = [2, 5.0, 0.2, 0.0, 0.0, 0.3, 0.0, 0.2, 0.0]
    scores = engine.score_candidates_batch(c_mat, target_energy=0.8, target_duration=3.0)
    assert len(scores) == 3
    assert scores[0] > 0.5
    assert scores[1] == -1000.0  # masked
    assert scores[0] > scores[2]


def test_cxx_audio_dsp_routines():
    engine = get_cxx_engine()
    
    # Moving RMS
    pcm = np.sin(np.linspace(0, 100 * np.pi, 44100)).astype(np.float32)
    rms = engine.compute_moving_rms(pcm, hop_size=512, frame_size=2048)
    assert len(rms) > 0
    assert np.all(rms > 0.0)

    # Smooth Energy Curve
    noisy_curve = np.array([0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.2], dtype=np.float32)
    smoothed = engine.smooth_energy_curve(noisy_curve, window_size=3)
    assert len(smoothed) == len(noisy_curve)
    assert smoothed[1] < noisy_curve[1]  # peak smoothed out

    # Peak detection
    peaks = engine.detect_energy_peaks(noisy_curve, threshold=0.5, min_distance=1)
    assert len(peaks) >= 1
    assert 1 in peaks

    # Beatgrid quantization
    raw_beats = [0.0, 0.49, 1.02, 1.51, 1.99]
    quantized = engine.quantize_beatgrid(raw_beats, bpm=120.0, tolerance_sec=0.05)
    assert len(quantized) == len(raw_beats)
    assert quantized[1] == pytest.approx(0.50, abs=0.01)
    assert quantized[2] == pytest.approx(1.00, abs=0.01)


def test_cxx_lyrics_grounding_and_slang():
    engine = get_cxx_engine()
    tokens = ["oida", "servus", "der", "flow", "vom", "089", "beton", "weed"]
    density = engine.calculate_slang_density(tokens)
    assert density > 0.5

    energies = [0.2, 0.4, 0.8, 0.9, 0.3]
    punchlines = [0.0, 0.2, 1.0, 0.5, 0.1]
    tension = engine.synthesize_tension_curve(energies, punchlines)
    assert len(tension) == 5
    assert tension[2] > tension[0]


def test_cxx_camera_kinematics_path():
    engine = get_cxx_engine()
    zoom, px, py = engine.generate_camera_path(
        start_zoom=1.0, end_zoom=1.3,
        start_pan_x=0.0, end_pan_x=100.0,
        start_pan_y=0.0, end_pan_y=50.0,
        frame_count=30,
        easing_type="cubic"
    )
    assert len(zoom) == 30
    assert len(px) == 30
    assert len(py) == 30
    assert zoom[0] == pytest.approx(1.0)
    assert zoom[-1] == pytest.approx(1.3)
    assert px[-1] == pytest.approx(100.0)
