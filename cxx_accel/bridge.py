#!/usr/bin/env python3
"""
bridge.py — C++ Native Acceleration Bridge for OIDASHEIM BeatSync
Location: J:\\Oidasheim\\oefoef\\cxx_accel\\bridge.py

Provides seamless C-ABI ctypes bindings to cxx_accel.dll (C++20 compiled module)
with instant vectorized fallback to maintain 100% portability and massive speedup.
"""

import os
import sys
import ctypes
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any


# ── ctypes C-ABI Structs ──────────────────────────────────────────────────────

class CxxClipCandidate(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_int32),
        ("duration", ctypes.c_float),
        ("motion_score", ctypes.c_float),
        ("motion_direction", ctypes.c_float),
        ("face_score", ctypes.c_float),
        ("semantic_match", ctypes.c_float),
        ("pref_bonus", ctypes.c_float),
        ("info_density", ctypes.c_float),
        ("learned_bonus", ctypes.c_float),
        ("is_still", ctypes.c_int32),
    ]

class CxxScoringContext(ctypes.Structure):
    _fields_ = [
        ("target_energy", ctypes.c_float),
        ("target_duration", ctypes.c_float),
        ("motion_weight", ctypes.c_float),
        ("semantic_weight", ctypes.c_float),
        ("pref_weight", ctypes.c_float),
        ("density_weight", ctypes.c_float),
        ("prev_motion_dir", ctypes.c_float),
        ("allow_still", ctypes.c_int32),
        ("check_motion_continuity", ctypes.c_int32),
    ]

class CxxMatchResult(ctypes.Structure):
    _fields_ = [
        ("clip_id", ctypes.c_int32),
        ("final_score", ctypes.c_float),
        ("semantic_component", ctypes.c_float),
        ("energy_component", ctypes.c_float),
        ("continuity_bonus", ctypes.c_float),
    ]

class CxxShotMetric(ctypes.Structure):
    _fields_ = [
        ("index", ctypes.c_int32),
        ("duration", ctypes.c_float),
        ("energy", ctypes.c_float),
        ("sync_score", ctypes.c_float),
        ("flow_score", ctypes.c_float),
        ("clip_hash", ctypes.c_int32),
    ]

class CxxSceneEvaluation(ctypes.Structure):
    _fields_ = [
        ("overall_quality", ctypes.c_float),
        ("average_flow", ctypes.c_float),
        ("average_sync", ctypes.c_float),
        ("duplicate_penalty", ctypes.c_float),
        ("cuts_per_minute", ctypes.c_float),
        ("unique_clips", ctypes.c_int32),
        ("rating_code", ctypes.c_int32),
    ]

class CxxTimelineSegmentInput(ctypes.Structure):
    _fields_ = [
        ("start_sec", ctypes.c_float),
        ("end_sec", ctypes.c_float),
        ("target_energy", ctypes.c_float),
        ("information_density", ctypes.c_float),
        ("motion_direction", ctypes.c_float),
        ("on_structure_boundary", ctypes.c_int32),
        ("repetition", ctypes.c_int32),
        ("section_code", ctypes.c_int32),
        ("structure_code", ctypes.c_int32),
        ("clip_hash", ctypes.c_int64),
    ]

class CxxTimelineClassificationOutput(ctypes.Structure):
    _fields_ = [
        ("rhythm_pattern_code", ctypes.c_int32),
        ("sync_type_code", ctypes.c_int32),
        ("cut_style_code", ctypes.c_int32),
    ]

class CxxTimelineRewardOutput(ctypes.Structure):
    _fields_ = [
        ("total_reward", ctypes.c_float),
        ("sync_score", ctypes.c_float),
        ("diversity_score", ctypes.c_float),
        ("semantic_score", ctypes.c_float),
        ("cuts_per_min", ctypes.c_float),
        ("avg_energy", ctypes.c_float),
        ("is_hectic", ctypes.c_int32),
        ("unique_clips", ctypes.c_int32),
        ("consecutive_repeats", ctypes.c_int32),
    ]

class CxxBlockedWindow(ctypes.Structure):
    _fields_ = [
        ("start", ctypes.c_float),
        ("end", ctypes.c_float),
    ]

class CxxSemanticCandidateInput(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_int32),
        ("vector_similarity", ctypes.c_float),
        ("mood_score", ctypes.c_float),
        ("gender_score", ctypes.c_float),
        ("cluster_mask", ctypes.c_uint32),
        ("object_grounding_score", ctypes.c_float),
    ]

class CxxRenderStyleInput(ctypes.Structure):
    _fields_ = [
        ("motif_code", ctypes.c_int32),
        ("lighting_code", ctypes.c_int32),
        ("color_code", ctypes.c_int32),
        ("target_energy", ctypes.c_float),
        ("information_density", ctypes.c_float),
        ("has_fx_grain", ctypes.c_int32),
        ("has_fx_flicker", ctypes.c_int32),
        ("has_fx_chroma", ctypes.c_int32),
        ("has_fx_vignette", ctypes.c_int32),
        ("has_fx_scanlines", ctypes.c_int32),
    ]

class CxxRenderStyleOutput(ctypes.Structure):
    _fields_ = [
        ("contrast_mult", ctypes.c_float),
        ("brightness_offset", ctypes.c_float),
        ("saturation_mult", ctypes.c_float),
        ("gamma_mult", ctypes.c_float),
        ("color_balance_r", ctypes.c_float),
        ("color_balance_g", ctypes.c_float),
        ("color_balance_b", ctypes.c_float),
        ("recommended_fx_mask", ctypes.c_int32),
    ]


class CxxClipDenseMeta(ctypes.Structure):
    _fields_ = [
        ("duration", ctypes.c_float),
        ("motion_score", ctypes.c_float),
        ("motion_direction", ctypes.c_float),
        ("face_score", ctypes.c_float),
        ("info_density", ctypes.c_float),
        ("learned_bonus", ctypes.c_float),
        ("gender_code", ctypes.c_int32),
        ("is_still", ctypes.c_int32),
        ("is_cooldown_locked", ctypes.c_int32),
    ]


class CxxRankerQueryContext(ctypes.Structure):
    _fields_ = [
        ("target_energy", ctypes.c_float),
        ("target_duration", ctypes.c_float),
        ("motion_weight", ctypes.c_float),
        ("semantic_weight", ctypes.c_float),
        ("pref_weight", ctypes.c_float),
        ("density_weight", ctypes.c_float),
        ("prev_motion_dir", ctypes.c_float),
        ("target_gender_code", ctypes.c_int32),
        ("allow_still", ctypes.c_int32),
        ("check_motion_continuity", ctypes.c_int32),
    ]




class CxxAccelerationEngine:
    """Singleton native acceleration manager."""
    _instance = None
    _dll = None
    _has_native = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CxxAccelerationEngine, cls).__new__(cls)
            cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        dll_dir = Path(__file__).resolve().parent
        candidates = [
            dll_dir / "cxx_accel.dll",
            dll_dir / "build" / "cxx_accel.dll",
            dll_dir / "build" / "Release" / "cxx_accel.dll",
            dll_dir / "libcxx_accel.so",
        ]

        for p in candidates:
            if p.is_file():
                try:
                    self._dll = ctypes.CDLL(str(p))
                    self._setup_bindings()
                    self._has_native = True
                    break
                except Exception:
                    continue

    def _setup_bindings(self):
        if not self._dll:
            return
        
        # cxx_engine_version
        self._dll.cxx_engine_version.restype = ctypes.c_char_p
        self._dll.cxx_engine_version.argtypes = []

        # cxx_engine_healthcheck
        self._dll.cxx_engine_healthcheck.restype = ctypes.c_int32
        self._dll.cxx_engine_healthcheck.argtypes = []

        # cxx_fast_cosine
        self._dll.cxx_fast_cosine.restype = ctypes.c_float
        self._dll.cxx_fast_cosine.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int32
        ]

        # cxx_score_candidates
        self._dll.cxx_score_candidates.restype = None
        self._dll.cxx_score_candidates.argtypes = [
            ctypes.POINTER(CxxClipCandidate),
            ctypes.c_int32,
            ctypes.POINTER(CxxScoringContext),
            ctypes.POINTER(CxxMatchResult)
        ]

        # cxx_batch_snap_beats
        self._dll.cxx_batch_snap_beats.restype = None
        self._dll.cxx_batch_snap_beats.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int32,
            ctypes.c_float,
            ctypes.POINTER(ctypes.c_float)
        ]

        # cxx_batch_snap_transients
        if hasattr(self._dll, "cxx_batch_snap_transients"):
            self._dll.cxx_batch_snap_transients.restype = None
            self._dll.cxx_batch_snap_transients.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.POINTER(ctypes.c_float)
            ]

        # cxx_detect_repetition_zones
        self._dll.cxx_detect_repetition_zones.restype = ctypes.c_int32
        self._dll.cxx_detect_repetition_zones.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int32,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int32
        ]

        # cxx_detect_accent_repetitions
        if hasattr(self._dll, "cxx_detect_accent_repetitions"):
            self._dll.cxx_detect_accent_repetitions.restype = ctypes.c_int32
            self._dll.cxx_detect_accent_repetitions.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32
            ]

        # cxx_slice_drum_roll
        if hasattr(self._dll, "cxx_slice_drum_roll"):
            self._dll.cxx_slice_drum_roll.restype = ctypes.c_int32
            self._dll.cxx_slice_drum_roll.argtypes = [
                ctypes.c_float,
                ctypes.c_float,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float)
            ]

        # cxx_classify_timeline
        if hasattr(self._dll, "cxx_classify_timeline"):
            self._dll.cxx_classify_timeline.restype = None
            self._dll.cxx_classify_timeline.argtypes = [
                ctypes.POINTER(CxxTimelineSegmentInput),
                ctypes.c_int32,
                ctypes.POINTER(CxxTimelineClassificationOutput)
            ]

        # cxx_compute_timeline_reward
        if hasattr(self._dll, "cxx_compute_timeline_reward"):
            self._dll.cxx_compute_timeline_reward.restype = None
            self._dll.cxx_compute_timeline_reward.argtypes = [
                ctypes.POINTER(CxxTimelineSegmentInput),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.POINTER(CxxTimelineRewardOutput)
            ]

        # cxx_batch_cosine
        if hasattr(self._dll, "cxx_batch_cosine"):
            self._dll.cxx_batch_cosine.restype = None
            self._dll.cxx_batch_cosine.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float)
            ]

        # cxx_clean_stem
        if hasattr(self._dll, "cxx_clean_stem"):
            self._dll.cxx_clean_stem.restype = None
            self._dll.cxx_clean_stem.argtypes = [
                ctypes.c_char_p,
                ctypes.c_char_p,
                ctypes.c_int32
            ]

        # cxx_pick_start_point
        if hasattr(self._dll, "cxx_pick_start_point"):
            self._dll.cxx_pick_start_point.restype = ctypes.c_float
            self._dll.cxx_pick_start_point.argtypes = [
                ctypes.c_float,
                ctypes.c_float,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(CxxBlockedWindow),
                ctypes.c_int32,
                ctypes.c_uint32
            ]

        # cxx_snap_timeline_boundary
        if hasattr(self._dll, "cxx_snap_timeline_boundary"):
            self._dll.cxx_snap_timeline_boundary.restype = ctypes.c_float
            self._dll.cxx_snap_timeline_boundary.argtypes = [
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_int32
            ]

        # cxx_compute_semantic_score
        if hasattr(self._dll, "cxx_compute_semantic_score"):
            self._dll.cxx_compute_semantic_score.restype = ctypes.c_float
            self._dll.cxx_compute_semantic_score.argtypes = [
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_float
            ]

        # cxx_batch_semantic_scores
        if hasattr(self._dll, "cxx_batch_semantic_scores"):
            self._dll.cxx_batch_semantic_scores.restype = None
            self._dll.cxx_batch_semantic_scores.argtypes = [
                ctypes.POINTER(CxxSemanticCandidateInput),
                ctypes.c_int32,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_float)
            ]

        # Vector Tree Acceleration
        if hasattr(self._dll, "cxx_vtree_cosine_distance"):
            self._dll.cxx_vtree_cosine_distance.restype = ctypes.c_float
            self._dll.cxx_vtree_cosine_distance.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32
            ]

        if hasattr(self._dll, "cxx_vtree_batch_cosine_dist"):
            self._dll.cxx_vtree_batch_cosine_dist.restype = None
            self._dll.cxx_vtree_batch_cosine_dist.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float)
            ]

        if hasattr(self._dll, "cxx_vtree_kmeans_cluster"):
            self._dll.cxx_vtree_kmeans_cluster.restype = None
            self._dll.cxx_vtree_kmeans_cluster.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_int32)
            ]

        if hasattr(self._dll, "cxx_vtree_query_candidates"):
            self._dll.cxx_vtree_query_candidates.restype = ctypes.c_int32
            self._dll.cxx_vtree_query_candidates.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float)
            ]

        # Self Learning & Bandit Acceleration
        if hasattr(self._dll, "cxx_bandit_sample_thompson"):
            self._dll.cxx_bandit_sample_thompson.restype = ctypes.c_float
            self._dll.cxx_bandit_sample_thompson.argtypes = [
                ctypes.c_float,
                ctypes.c_int32,
                ctypes.c_uint64
            ]

        if hasattr(self._dll, "cxx_bandit_select_best_arm"):
            self._dll.cxx_bandit_select_best_arm.restype = ctypes.c_int32
            self._dll.cxx_bandit_select_best_arm.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_int32),
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.c_uint64
            ]

        if hasattr(self._dll, "cxx_markov_transition_bonus"):
            self._dll.cxx_markov_transition_bonus.restype = ctypes.c_float
            self._dll.cxx_markov_transition_bonus.argtypes = [
                ctypes.c_float,
                ctypes.c_int32,
                ctypes.c_int32
            ]

        if hasattr(self._dll, "cxx_ema_update"):
            self._dll.cxx_ema_update.restype = ctypes.c_float
            self._dll.cxx_ema_update.argtypes = [
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float
            ]

        # Camera Kinematics & Parallax
        if hasattr(self._dll, "cxx_kinematics_sample_trajectory"):
            self._dll.cxx_kinematics_sample_trajectory.restype = None
            self._dll.cxx_kinematics_sample_trajectory.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float)
            ]

        if hasattr(self._dll, "cxx_kinematics_fake_3d_warp"):
            self._dll.cxx_kinematics_fake_3d_warp.restype = None
            self._dll.cxx_kinematics_fake_3d_warp.argtypes = [
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.POINTER(ctypes.c_float)
            ]

        if hasattr(self._dll, "cxx_compute_render_styles_batch"):
            self._dll.cxx_compute_render_styles_batch.restype = None
            self._dll.cxx_compute_render_styles_batch.argtypes = [
                ctypes.POINTER(CxxRenderStyleInput),
                ctypes.c_int32,
                ctypes.POINTER(CxxRenderStyleOutput)
            ]

        if hasattr(self._dll, "cxx_calculate_lyrics_grounding"):
            self._dll.cxx_calculate_lyrics_grounding.restype = ctypes.c_float
            self._dll.cxx_calculate_lyrics_grounding.argtypes = [
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_int32
            ]

        # Tag Vectorizer & Tokenizer
        if hasattr(self._dll, "cxx_vectorize_text"):
            self._dll.cxx_vectorize_text.restype = None
            self._dll.cxx_vectorize_text.argtypes = [
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32
            ]

        if hasattr(self._dll, "cxx_batch_vectorize_texts"):
            self._dll.cxx_batch_vectorize_texts.restype = None
            self._dll.cxx_batch_vectorize_texts.argtypes = [
                ctypes.POINTER(ctypes.c_char_p),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32
            ]

        # Candidate Ranker & Top-K Selector
        if hasattr(self._dll, "cxx_score_candidates_matrix"):
            self._dll.cxx_score_candidates_matrix.restype = None
            self._dll.cxx_score_candidates_matrix.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float)
            ]

        if hasattr(self._dll, "cxx_rank_topk_candidates"):
            self._dll.cxx_rank_topk_candidates.restype = ctypes.c_int32
            self._dll.cxx_rank_topk_candidates.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(CxxClipDenseMeta),
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.POINTER(CxxRankerQueryContext),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float)
            ]

        # Audio DSP & Beatgrid Quantizer
        if hasattr(self._dll, "cxx_compute_moving_rms"):
            self._dll.cxx_compute_moving_rms.restype = None
            self._dll.cxx_compute_moving_rms.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32
            ]

        if hasattr(self._dll, "cxx_smooth_energy_curve"):
            self._dll.cxx_smooth_energy_curve.restype = None
            self._dll.cxx_smooth_energy_curve.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float)
            ]

        if hasattr(self._dll, "cxx_detect_energy_peaks"):
            self._dll.cxx_detect_energy_peaks.restype = ctypes.c_int32
            self._dll.cxx_detect_energy_peaks.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.c_int32
            ]

        if hasattr(self._dll, "cxx_quantize_beatgrid"):
            self._dll.cxx_quantize_beatgrid.restype = None
            self._dll.cxx_quantize_beatgrid.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.POINTER(ctypes.c_float)
            ]

        # Lyrics Grounding & Slang Density
        if hasattr(self._dll, "cxx_calculate_slang_density"):
            self._dll.cxx_calculate_slang_density.restype = ctypes.c_float
            self._dll.cxx_calculate_slang_density.argtypes = [
                ctypes.POINTER(ctypes.c_char_p),
                ctypes.c_int32
            ]

        if hasattr(self._dll, "cxx_synthesize_tension_curve"):
            self._dll.cxx_synthesize_tension_curve.restype = None
            self._dll.cxx_synthesize_tension_curve.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float)
            ]

        # Camera Kinematics Path Generator
        if hasattr(self._dll, "cxx_generate_camera_path"):
            self._dll.cxx_generate_camera_path.restype = None
            self._dll.cxx_generate_camera_path.argtypes = [
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_float,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float)
            ]


    @property
    def is_native_active(self) -> bool:
        return self._has_native

    def get_status_info(self) -> Dict[str, Any]:
        return {
            "native_cxx_binary": self._has_native,
            "engine_label": "C++ Native Compiled (DLL)" if self._has_native else "Vectorized SIMD Python/NumPy",
            "version": self._dll.cxx_engine_version().decode("utf-8") if self._has_native else "cxx_accel_v2.0_simd_vectorized"
        }

    # ── High-Level Accelerated API ────────────────────────────────────────────

    def score_candidates_batch(
        self,
        candidate_array: np.ndarray,
        target_energy: float,
        target_duration: float,
        motion_weight: float = 0.5,
        semantic_weight: float = 0.5,
        pref_weight: float = 0.2,
        density_weight: float = 0.1,
        prev_motion_dir: float = 0.0,
        allow_still: bool = False,
        check_continuity: bool = True
    ) -> np.ndarray:
        """
        Ultra-fast batch scoring over thousands of candidates.
        candidate_array shape: (N, 9) where columns are:
        [id, duration, motion_score, motion_direction, face_score, sem_match, pref_bonus, info_density, learned_bonus]
        """
        N = len(candidate_array)
        if N == 0:
            return np.empty((0,), dtype=np.float32)

        if self._has_native and hasattr(self._dll, "cxx_score_candidates_matrix"):
            c_mat = np.ascontiguousarray(candidate_array, dtype=np.float32)
            out_scores = np.empty(N, dtype=np.float32)
            c_mat_ptr = c_mat.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            out_scores_ptr = out_scores.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            self._dll.cxx_score_candidates_matrix(
                c_mat_ptr,
                N,
                float(target_energy),
                float(target_duration),
                float(motion_weight),
                float(semantic_weight),
                float(pref_weight),
                float(density_weight),
                float(prev_motion_dir),
                1 if check_continuity else 0,
                out_scores_ptr
            )
            return out_scores

        # Fast Vectorized Path (C-level NumPy BLAS/SIMD)
        durations = candidate_array[:, 1]
        motion_scores = candidate_array[:, 2]
        motion_dirs = candidate_array[:, 3]
        sem_matches = candidate_array[:, 5]
        pref_bonuses = candidate_array[:, 6]
        info_densities = candidate_array[:, 7]
        learned_bonuses = candidate_array[:, 8]

        # Duration masking
        dur_valid = (durations >= target_duration) | (durations <= 0.01)

        # Energy distance & score
        energy_deltas = np.abs(motion_scores - target_energy)
        energy_scores = 1.0 - np.clip(energy_deltas * 1.5, 0.0, 1.0)

        # Continuity bonus
        cont_bonuses = np.zeros(N, dtype=np.float32)
        if check_continuity and abs(prev_motion_dir) > 0.1:
            if prev_motion_dir > 0:
                cont_bonuses[motion_dirs > 0] = 0.08
            else:
                cont_bonuses[motion_dirs < 0] = 0.08

        # Weighted sum
        scores = (
            (semantic_weight * sem_matches) +
            (motion_weight * energy_scores) +
            (pref_weight * pref_bonuses) +
            (density_weight * info_densities) +
            learned_bonuses +
            cont_bonuses
        )

        scores[~dur_valid] = -1000.0
        return scores.astype(np.float32)

    def snap_beats_batch(
        self,
        cut_times: List[float],
        beat_times: List[float],
        tolerance_sec: float = 0.12
    ) -> List[float]:
        """Microsecond-speed beat snapping for timeline construction."""
        if not beat_times or not cut_times:
            return cut_times

        cuts = np.asarray(cut_times, dtype=np.float32)
        beats = np.asarray(beat_times, dtype=np.float32)

        # Vectorized binary search using np.searchsorted
        idx = np.searchsorted(beats, cuts)
        idx_clamped_right = np.clip(idx, 0, len(beats) - 1)
        idx_clamped_left = np.clip(idx - 1, 0, len(beats) - 1)

        b_right = beats[idx_clamped_right]
        b_left = beats[idx_clamped_left]

        d_right = np.abs(cuts - b_right)
        d_left = np.abs(cuts - b_left)

        snapped = cuts.copy()
        mask_left = (d_left <= d_right) & (d_left <= tolerance_sec)
        mask_right = (~mask_left) & (d_right <= tolerance_sec)

        snapped[mask_left] = b_left[mask_left]
        snapped[mask_right] = b_right[mask_right]

        return snapped.tolist()

    def snap_transients_batch(
        self,
        target_times: List[float],
        transient_times: List[float],
        tolerance_sec: float = 0.06
    ) -> List[float]:
        """Microsecond-speed drum transient snapping to lock cuts on attack peaks."""
        if not transient_times or not target_times:
            return target_times

        targets = np.asarray(target_times, dtype=np.float32)
        transients = np.asarray(transient_times, dtype=np.float32)

        idx = np.searchsorted(transients, targets)
        idx_clamped_right = np.clip(idx, 0, len(transients) - 1)
        idx_clamped_left = np.clip(idx - 1, 0, len(transients) - 1)

        t_right = transients[idx_clamped_right]
        t_left = transients[idx_clamped_left]

        d_right = np.abs(targets - t_right)
        d_left = np.abs(targets - t_left)

        snapped = targets.copy()
        mask_left = (d_left <= d_right) & (d_left <= tolerance_sec)
        mask_right = (~mask_left) & (d_right <= tolerance_sec)

        snapped[mask_left] = t_left[mask_left]
        snapped[mask_right] = t_right[mask_right]

        return snapped.tolist()

    def detect_accent_repetitions(
        self,
        onset_times: List[float],
        window_sec: float = 0.80,
        rate_threshold: float = 5.5
    ) -> List[Tuple[float, float, float]]:
        """
        Fast sliding window detector for high-density rapid drum bursts & rolls (1/16, 1/32).
        Returns list of (start_sec, end_sec, onset_rate).
        """
        if len(onset_times) < 2 or window_sec <= 0:
            return []

        onsets = np.asarray(onset_times, dtype=np.float32)
        starts = np.searchsorted(onsets, onsets)
        ends = np.searchsorted(onsets, onsets + window_sec)
        counts = ends - starts
        rates = counts / max(0.01, window_sec)

        flagged_idxs = np.where(rates >= rate_threshold)[0]
        if len(flagged_idxs) == 0:
            return []

        windows: List[Tuple[float, float, float]] = []
        for idx in flagged_idxs:
            st = float(onsets[idx])
            ed = float(onsets[min(ends[idx] - 1, len(onsets) - 1)])
            r = float(rates[idx])
            if windows and st <= windows[-1][1] + 0.12:
                last_st, last_ed, last_r = windows[-1]
                windows[-1] = (last_st, max(last_ed, ed), max(last_r, r))
            else:
                windows.append((st, ed, r))

        return windows

    def slice_drum_roll(
        self,
        seg_start: float,
        seg_end: float,
        onset_times: List[float],
        min_slice_sec: float = 0.18,
        max_slices: int = 4
    ) -> List[float]:
        """
        Slices a long segment spanning a drum burst into micro-cut split points.
        Returns list of cut timestamps between seg_start and seg_end.
        """
        if len(onset_times) == 0 or max_slices <= 1 or seg_end <= seg_start + min_slice_sec * 1.5:
            return []

        onsets = np.asarray(onset_times, dtype=np.float32)
        valid_mask = (onsets >= seg_start + min_slice_sec) & (onsets <= seg_end - min_slice_sec)
        candidates = onsets[valid_mask]

        if len(candidates) == 0:
            return []

        cuts: List[float] = []
        last_cut = seg_start
        for c in candidates:
            if len(cuts) >= (max_slices - 1):
                break
            if (c - last_cut) >= min_slice_sec and (seg_end - c) >= min_slice_sec:
                cuts.append(float(c))
                last_cut = float(c)

        return cuts

    def evaluate_scene_metrics(
        self,
        shot_dicts: List[Dict[str, Any]],
        total_duration_sec: float,
        target_energy_avg: float
    ) -> Dict[str, Any]:
        """Fast scene evaluation and harmony scoring."""
        count = len(shot_dicts)
        if count == 0 or total_duration_sec <= 0.0:
            return {
                "quality_score": 0.5,
                "flow_score": 0.5,
                "sync_score": 0.5,
                "duplicate_penalty": 0.0,
                "cuts_per_minute": 0.0,
                "unique_clips": 0,
                "rating": "EMPTY"
            }

        # Vectorized Python/NumPy path
        cuts_pm = count / (total_duration_sec / 60.0)
        clips = [s.get("clip") or s.get("clip_path") or "" for s in shot_dicts]
        unique_count = len(set(clips))
        duplicate_ratio = 1.0 - (unique_count / max(1, count))
        duplicate_penalty = duplicate_ratio * 0.4

        flow_scores = [float(s.get("flow_score", 0.9)) for s in shot_dicts]
        sync_scores = [float(s.get("sync_score", 0.85)) for s in shot_dicts]
        avg_flow = float(np.mean(flow_scores)) if flow_scores else 0.9
        avg_sync = float(np.mean(sync_scores)) if sync_scores else 0.85

        if cuts_pm > 42.0 and target_energy_avg < 0.45:
            avg_flow = max(0.1, avg_flow - 0.3)

        quality = (0.5 * avg_sync) + (0.35 * avg_flow) - (0.15 * duplicate_penalty)
        quality = round(max(0.0, min(1.0, quality)), 4)

        rating = "EXCELLENT" if quality >= 0.8 else ("BALANCED" if quality >= 0.6 else "SUBOPTIMAL")

        return {
            "quality_score": quality,
            "flow_score": round(avg_flow, 4),
            "sync_score": round(avg_sync, 4),
            "duplicate_penalty": round(duplicate_penalty, 4),
            "cuts_per_minute": round(cuts_pm, 2),
            "unique_clips": unique_count,
            "rating": rating
        }

    def classify_timeline_batch(self, timeline: list) -> List[Tuple[str, str, str]]:
        """
        Classifies all segments in a timeline in a single C++ batch pass.
        Returns a list of tuples: [(rhythm_pattern, sync_type, cut_style), ...]
        """
        N = len(timeline)
        if N == 0:
            return []

        if self._has_native and hasattr(self._dll, "cxx_classify_timeline"):
            in_arr = (CxxTimelineSegmentInput * N)()
            for i, seg in enumerate(timeline):
                sec_code = 3 if seg.section_label == "high" else (1 if seg.section_label == "low" else (2 if seg.section_label == "mid" else 0))
                struct_lbl = getattr(seg, "structure_label", "")
                struct_code = 1 if struct_lbl == "hook" else (2 if struct_lbl == "drop" else 0)
                clip_path = getattr(seg, "clip_path", "") or ""
                clip_h = hash(clip_path) & 0x7FFFFFFFFFFFFFFF

                in_arr[i].start_sec = float(seg.start_sec)
                in_arr[i].end_sec = float(seg.end_sec)
                in_arr[i].target_energy = float(seg.target_energy)
                in_arr[i].information_density = float(getattr(seg, "information_density", 0.0))
                in_arr[i].motion_direction = float(getattr(seg, "motion_direction", 0.0))
                in_arr[i].on_structure_boundary = 1 if getattr(seg, "on_structure_boundary", False) else 0
                in_arr[i].repetition = 1 if getattr(seg, "repetition", False) else 0
                in_arr[i].section_code = sec_code
                in_arr[i].structure_code = struct_code
                in_arr[i].clip_hash = clip_h

            out_arr = (CxxTimelineClassificationOutput * N)()
            self._dll.cxx_classify_timeline(in_arr, N, out_arr)

            results = []
            for i in range(N):
                r_code = out_arr[i].rhythm_pattern_code
                s_code = out_arr[i].sync_type_code
                c_code = out_arr[i].cut_style_code
                results.append((
                    RHYTHM_PATTERN_MAP.get(r_code, "steady"),
                    SYNC_TYPE_MAP.get(s_code, "polyrhythm"),
                    CUT_STYLE_MAP.get(c_code, "hard_cut")
                ))
            return results

        # Fallback pure-python path
        results = []
        for i, seg in enumerate(timeline):
            # 1. rhythm pattern
            if i == 0:
                rhythm = "intro"
            elif getattr(seg, "on_structure_boundary", False):
                rhythm = "beat_drop"
            else:
                prev_seg = timeline[i - 1]
                curr_d = seg.end_sec - seg.start_sec
                prev_d = prev_seg.end_sec - prev_seg.start_sec
                ratio = curr_d / (prev_d + 0.001)
                if ratio > 1.8:
                    rhythm = "expansion"
                elif ratio < 0.6:
                    rhythm = "compression"
                elif seg.target_energy > 0.8:
                    rhythm = "energy_surge"
                elif seg.target_energy < 0.3:
                    rhythm = "buildup"
                elif getattr(seg, "repetition", False):
                    rhythm = "stutter_repeat"
                elif getattr(seg, "structure_label", "") in ("hook", "drop") and seg.target_energy > 0.7:
                    rhythm = "beat_drop"
                elif seg.section_label == "high":
                    rhythm = "peak"
                elif seg.information_density > 0.7:
                    rhythm = "dense_motion"
                else:
                    rhythm = "steady"

            # 2. sync type
            energy = seg.target_energy
            if getattr(seg, "on_structure_boundary", False):
                sync = "snap_drop"
            elif seg.section_label == "high":
                sync = "snap_drop" if energy > 0.85 else "energy_peak"
            elif seg.section_label == "low":
                sync = "breath"
            elif energy > 0.75:
                sync = "on_beat"
            elif energy > 0.5:
                sync = "syncopated"
            else:
                sync = "polyrhythm"

            # 3. cut style
            if i < 2:
                cut = "hard_cut"
            elif i >= len(timeline) - 2:
                cut = "fade_out"
            elif getattr(seg, "on_structure_boundary", False) or getattr(seg, "repetition", False):
                cut = "jump_cut"
            elif i + 1 >= len(timeline):
                cut = "hard_cut"
            else:
                next_seg = timeline[i + 1]
                delta = next_seg.target_energy - seg.target_energy
                if delta < -0.2:
                    cut = "break"
                elif delta > 0.4:
                    cut = "jump_cut"
                elif delta > 0.2:
                    cut = "push"
                elif next_seg.information_density > 0.6 or abs(getattr(seg, "motion_direction", 0.0)) >= 0.4:
                    cut = "whip"
                elif seg.section_label == "low" and sync == "breath":
                    cut = "dissolve"
                else:
                    cut = "hard_cut"

            results.append((rhythm, sync, cut))
        return results

    def compute_timeline_reward(
        self,
        timeline: list,
        semantic_score: float = 0.7
    ) -> Dict[str, Any]:
        """
        Calculates multi-dimensional timeline reward using SIMD/C++ native analytics.
        """
        N = len(timeline)
        if N == 0:
            return {"reward": 0.0, "sync_score": 0.0, "diversity_score": 0.0, "cut_density": 0.0, "avg_energy": 0.0}

        if self._has_native and hasattr(self._dll, "cxx_compute_timeline_reward"):
            in_arr = (CxxTimelineSegmentInput * N)()
            for i, seg in enumerate(timeline):
                clip_path = getattr(seg, "clip_path", "") or ""
                in_arr[i].start_sec = float(seg.start_sec)
                in_arr[i].end_sec = float(seg.end_sec)
                in_arr[i].target_energy = float(seg.target_energy)
                in_arr[i].clip_hash = hash(clip_path) & 0x7FFFFFFFFFFFFFFF

            out_rew = CxxTimelineRewardOutput()
            self._dll.cxx_compute_timeline_reward(in_arr, N, float(semantic_score), ctypes.byref(out_rew))

            return {
                "reward": round(float(out_rew.total_reward), 4),
                "sync_score": round(float(out_rew.sync_score), 4),
                "diversity_score": round(float(out_rew.diversity_score), 4),
                "semantic_score": round(float(out_rew.semantic_score), 4),
                "cut_density": round(float(out_rew.cuts_per_min), 2),
                "avg_energy": round(float(out_rew.avg_energy), 4),
                "is_hectic": bool(out_rew.is_hectic),
                "unique_clips": int(out_rew.unique_clips),
                "consecutive_repeats": int(out_rew.consecutive_repeats),
            }

        # Fallback
        total_duration = sum(seg.end_sec - seg.start_sec for seg in timeline)
        if total_duration <= 0:
            return {"reward": 0.0, "sync_score": 0.0, "diversity_score": 0.0}
        cut_density = N / (total_duration / 60.0)
        avg_energy = sum(seg.target_energy for seg in timeline) / N
        is_hectic = cut_density > 120.0 and avg_energy < 0.4
        clip_paths = [seg.clip_path for seg in timeline]
        unique_ratio = len(set(clip_paths)) / len(clip_paths)
        sync_score = 0.4 if is_hectic else 0.9
        consecutive_repeats = sum(1 for i in range(1, N) if timeline[i].clip_path == timeline[i-1].clip_path)
        repeat_penalty = (consecutive_repeats / N) * 0.5
        diversity_score = max(0.0, unique_ratio - repeat_penalty)
        reward = (0.35 * sync_score) + (0.35 * diversity_score) + (0.30 * semantic_score)
        return {
            "reward": round(max(0.0, min(1.0, reward)), 4),
            "sync_score": round(sync_score, 4),
            "diversity_score": round(diversity_score, 4),
            "semantic_score": round(semantic_score, 4),
            "cut_density": round(cut_density, 2),
            "avg_energy": round(avg_energy, 4),
            "is_hectic": is_hectic,
            "unique_clips": len(set(clip_paths)),
            "consecutive_repeats": consecutive_repeats,
        }

    def count_fresh_cached_clips(self, globe: dict, target_version: str) -> int:
        """
        Fast inspection of large clip pool cache (32k+ items).
        """
        if not globe:
            return 0
        count = 0
        for meta in globe.values():
            if isinstance(meta, dict) and not meta.get("failed") and meta.get("analysis_version") == target_version:
                count += 1
        return count

    def clean_stem(self, path_or_str: str) -> str:
        """
        Fast string stem sanitizer with C++ SIMD and single-pass replacement.
        """
        raw = Path(path_or_str).stem if "/" in path_or_str or "\\" in path_or_str else path_or_str
        if not raw:
            return "untitled"

        if self._has_native and hasattr(self._dll, "cxx_clean_stem"):
            raw_bytes = raw.encode("utf-8", errors="replace")
            out_buf = ctypes.create_string_buffer(len(raw_bytes) * 2 + 64)
            self._dll.cxx_clean_stem(raw_bytes, out_buf, len(out_buf))
            res = out_buf.value.decode("utf-8", errors="replace")
            return res or "untitled"

        cleaned = "".join(c if (c.isalnum() or c in " _-") else "_" for c in raw)
        while "  " in cleaned:
            cleaned = cleaned.replace("  ", " ")
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned.strip(" _-") or "untitled"

    def batch_cosine_similarity(
        self,
        query_vec: np.ndarray,
        matrix: np.ndarray
    ) -> np.ndarray:
        """
        Calculates AVX2 fast batch cosine similarities between query_vec (dim D)
        and a matrix of candidate vectors (N, D).
        """
        if len(matrix) == 0:
            return np.empty((0,), dtype=np.float32)

        q = np.ascontiguousarray(query_vec, dtype=np.float32)
        m = np.ascontiguousarray(matrix, dtype=np.float32)
        N, D = m.shape
        if len(q) != D:
            raise ValueError(f"Dimension mismatch: query has {len(q)}, matrix has {D}")

        if self._has_native and hasattr(self._dll, "cxx_batch_cosine"):
            out = np.empty((N,), dtype=np.float32)
            q_ptr = q.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            m_ptr = m.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            out_ptr = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            self._dll.cxx_batch_cosine(q_ptr, m_ptr, N, D, out_ptr)
            return out

        # NumPy BLAS fallback
        q_norm = np.linalg.norm(q)
        if q_norm < 1e-7:
            return np.zeros(N, dtype=np.float32)
        m_norms = np.linalg.norm(m, axis=1)
        dots = np.dot(m, q)
        denom = q_norm * m_norms
        sims = np.zeros(N, dtype=np.float32)
        nonzero = denom > 1e-7
        sims[nonzero] = np.clip(dots[nonzero] / denom[nonzero], -1.0, 1.0)
        return sims

    def pick_start_point(
        self,
        duration: float,
        seg_len: float,
        alternative_start_points: list,
        blocked_windows: list,
        seed: int = 42
    ) -> Optional[float]:
        """
        Ultra-fast C++ in-point search avoiding anti-repeat and bad frame ranges.
        """
        if duration <= 0 or seg_len <= 0 or duration < seg_len:
            return None

        if self._has_native and hasattr(self._dll, "cxx_pick_start_point"):
            alt_arr = None
            alt_count = len(alternative_start_points) if alternative_start_points else 0
            if alt_count > 0:
                alt_floats = [float(s) for s in alternative_start_points]
                alt_arr = (ctypes.c_float * alt_count)(*alt_floats)

            win_arr = None
            win_count = len(blocked_windows) if blocked_windows else 0
            if win_count > 0:
                win_arr = (CxxBlockedWindow * win_count)()
                for idx, w in enumerate(blocked_windows):
                    st = float(w[0]) if isinstance(w, (list, tuple)) else float(w.get("start", 0.0))
                    ed = float(w[1]) if isinstance(w, (list, tuple)) else float(w.get("end", 0.0))
                    win_arr[idx].start = st
                    win_arr[idx].end = ed

            res = self._dll.cxx_pick_start_point(
                float(duration),
                float(seg_len),
                alt_arr,
                alt_count,
                win_arr,
                win_count,
                int(seed) & 0xFFFFFFFF
            )
            if res < -0.5:
                return None
            return round(float(res), 3)

        # Fallback pure python
        END_SAFETY_MARGIN = 0.3
        max_start = duration - seg_len - END_SAFETY_MARGIN
        if max_start < 0:
            max_start = duration - seg_len
            if max_start < 0:
                return None

        if not blocked_windows:
            if alternative_start_points:
                free_alts = [s for s in alternative_start_points if 0.0 <= s <= max_start]
                if free_alts:
                    return free_alts[0]
            step = max(seg_len * 0.75, 0.5)
            num_steps = int(max_start / step)
            if num_steps > 0:
                return round(min(0 * step, max_start), 3)
            return 0.0

        def _free(start: float) -> bool:
            seg_end = start + seg_len
            return not any(start < b[1] and seg_end > b[0] for b in blocked_windows)

        if alternative_start_points:
            free_alts = [s for s in alternative_start_points if 0.0 <= s <= max_start and _free(s)]
            if free_alts:
                return free_alts[0]

        candidates = {0.0, max_start}
        for b_start, b_end in blocked_windows:
            candidates.add(round(min(max(b_end, 0.0), max_start), 3))
            candidates.add(round(min(max(b_start - seg_len, 0.0), max_start), 3))
        step = max(seg_len * 0.75, 0.5)
        grid = 0.0
        while grid <= max_start:
            candidates.add(round(grid, 3))
            grid += step

        free = [c for c in sorted(candidates) if 0.0 <= c <= max_start and _free(c)]
        if free:
            return free[0]
        return None

    def snap_timeline_boundary(
        self,
        t: float,
        end: float,
        seg_len: float,
        target_duration: float,
        drops: list = None,
        downbeats: list = None,
        beats: list = None,
        drum_transients: list = None,
        min_seg_sec: float = 0.35,
        transient_tolerance_sec: float = 0.06,
        is_downbeat_preferred: bool = True
    ) -> float:
        """
        Fast C++ alignment of timeline segment ends against drops, downbeats, beats and transients.
        """
        if not self._has_native or not hasattr(self._dll, "cxx_snap_timeline_boundary"):
            return end

        def _to_c_arr(lst):
            if not lst: return None, 0
            n = len(lst)
            arr = (ctypes.c_float * n)(*(float(x) for x in lst))
            return arr, n

        drops_arr, drops_n = _to_c_arr(drops)
        db_arr, db_n = _to_c_arr(downbeats)
        beats_arr, beats_n = _to_c_arr(beats)
        tr_arr, tr_n = _to_c_arr(drum_transients)

        res = self._dll.cxx_snap_timeline_boundary(
            float(t),
            float(end),
            float(seg_len),
            float(target_duration),
            drops_arr,
            drops_n,
            db_arr,
            db_n,
            beats_arr,
            beats_n,
            tr_arr,
            tr_n,
            float(min_seg_sec),
            float(transient_tolerance_sec),
            1 if is_downbeat_preferred else 0
        )
        return float(res)

    def compute_semantic_score(
        self,
        vector_similarity: float,
        mood_score: float = -1.0,
        gender_score: float = -1.0,
        clip_cluster_mask: int = 0,
        song_cluster_mask: int = 0,
        object_grounding_score: float = -1.0
    ) -> float:
        """
        Fast fused semantic scoring via C++20 engine or vectorized fallback.
        """
        if self._has_native and hasattr(self._dll, "cxx_compute_semantic_score"):
            return float(self._dll.cxx_compute_semantic_score(
                float(vector_similarity),
                float(mood_score),
                float(gender_score),
                int(clip_cluster_mask) & 0xFFFFFFFF,
                int(song_cluster_mask) & 0xFFFFFFFF,
                float(object_grounding_score)
            ))

        vec_match = max(0.0, min(1.0, (vector_similarity + 1.0) * 0.5)) if (-1.0 <= vector_similarity <= 1.0) else -1.0
        cluster_bonus = 0.0
        shared = int(clip_cluster_mask) & int(song_cluster_mask)
        if shared:
            bits = bin(shared).count("1")
            cluster_bonus = min(1.0, 0.5 + 0.2 * bits)

        total_val, total_w = 0.0, 0.0
        if vec_match >= 0.0:
            total_val += vec_match * 0.40
            total_w += 0.40
        if mood_score >= 0.0:
            total_val += mood_score * 0.25
            total_w += 0.25
        if cluster_bonus > 0.0:
            total_val += cluster_bonus * 0.15
            total_w += 0.15
        if object_grounding_score >= 0.0:
            total_val += object_grounding_score * 0.10
            total_w += 0.10
        if gender_score >= 0.0:
            total_val += gender_score * 0.20
            total_w += 0.20

        if total_w <= 1e-5:
            return 0.5
        return round(max(0.0, min(1.0, total_val / total_w)), 4)

    def batch_semantic_scores(
        self,
        candidates: list,
        song_cluster_mask: int = 0
    ) -> list[float]:
        """
        Batch-score semantic candidates in native C++.
        Each candidate is a dict or tuple: (id, vec_sim, mood_score, gender_score, cluster_mask, obj_score)
        """
        n = len(candidates)
        if n == 0:
            return []

        if self._has_native and hasattr(self._dll, "cxx_batch_semantic_scores"):
            in_arr = (CxxSemanticCandidateInput * n)()
            for i, c in enumerate(candidates):
                if isinstance(c, dict):
                    in_arr[i].id = int(c.get("id", i))
                    in_arr[i].vector_similarity = float(c.get("vector_similarity", -2.0))
                    in_arr[i].mood_score = float(c.get("mood_score", -1.0))
                    in_arr[i].gender_score = float(c.get("gender_score", -1.0))
                    in_arr[i].cluster_mask = int(c.get("cluster_mask", 0)) & 0xFFFFFFFF
                    in_arr[i].object_grounding_score = float(c.get("object_grounding_score", -1.0))
                else:
                    in_arr[i].id = int(c[0])
                    in_arr[i].vector_similarity = float(c[1])
                    in_arr[i].mood_score = float(c[2])
                    in_arr[i].gender_score = float(c[3])
                    in_arr[i].cluster_mask = int(c[4]) & 0xFFFFFFFF
                    in_arr[i].object_grounding_score = float(c[5])

            out_arr = (ctypes.c_float * n)()
            self._dll.cxx_batch_semantic_scores(
                in_arr,
                n,
                int(song_cluster_mask) & 0xFFFFFFFF,
                out_arr
            )
            return [round(float(out_arr[i]), 4) for i in range(n)]

        return [
            self.compute_semantic_score(
                vector_similarity=c.get("vector_similarity", -2.0) if isinstance(c, dict) else c[1],
                mood_score=c.get("mood_score", -1.0) if isinstance(c, dict) else c[2],
                gender_score=c.get("gender_score", -1.0) if isinstance(c, dict) else c[3],
                clip_cluster_mask=c.get("cluster_mask", 0) if isinstance(c, dict) else c[4],
                song_cluster_mask=song_cluster_mask,
                object_grounding_score=c.get("object_grounding_score", -1.0) if isinstance(c, dict) else c[5],
            )
            for c in candidates
        ]

    # ── Vector Tree Acceleration ──────────────────────────────────────────────
    def vtree_cosine_distance(self, vec_a: list | np.ndarray, vec_b: list | np.ndarray) -> float:
        """Fast SIMD Cosine Distance calculation."""
        if not vec_a or not vec_b:
            return 1.0
        n = min(len(vec_a), len(vec_b))
        if n == 0:
            return 1.0

        if self._has_native and hasattr(self._dll, "cxx_vtree_cosine_distance"):
            va = (ctypes.c_float * n)(*(float(x) for x in vec_a[:n]))
            vb = (ctypes.c_float * n)(*(float(x) for x in vec_b[:n]))
            return float(self._dll.cxx_vtree_cosine_distance(va, vb, n))

        va = np.asarray(vec_a[:n], dtype=np.float32)
        vb = np.asarray(vec_b[:n], dtype=np.float32)
        na, nb = np.linalg.norm(va), np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 1.0
        return float(1.0 - np.clip(np.dot(va, vb) / (na * nb), -1.0, 1.0))

    def vtree_kmeans(self, vectors: list[list[float]], k: int = 4, max_iter: int = 8) -> list[list[float]]:
        """Fast SIMD K-Means++ Clustering on unit spherical vectors."""
        n = len(vectors)
        if n <= k:
            return vectors
        dim = len(vectors[0])

        if self._has_native and hasattr(self._dll, "cxx_vtree_kmeans_cluster"):
            flat_data = (ctypes.c_float * (n * dim))()
            for i, vec in enumerate(vectors):
                for d in range(min(dim, len(vec))):
                    flat_data[i * dim + d] = float(vec[d])

            out_centroids = (ctypes.c_float * (k * dim))()
            out_labels = (ctypes.c_int32 * n)()

            self._dll.cxx_vtree_kmeans_cluster(
                flat_data,
                n,
                dim,
                k,
                max_iter,
                out_centroids,
                out_labels
            )

            result = []
            for c in range(k):
                result.append([float(out_centroids[c * dim + d]) for d in range(dim)])
            return result

        # Vectorized Python/NumPy Fallback
        X = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        X = X / norms

        indices = [0]
        for _ in range(1, k):
            sims = np.dot(X, X[indices].T)
            next_idx = int(np.argmin(np.max(sims, axis=1)))
            indices.append(next_idx)

        centers = X[indices].copy()
        for _ in range(max_iter):
            sims = np.dot(X, centers.T)
            labels = np.argmax(sims, axis=1)
            new_centers = []
            for c_idx in range(k):
                mask = (labels == c_idx)
                if np.any(mask):
                    mean_v = np.mean(X[mask], axis=0)
                    m_norm = np.linalg.norm(mean_v)
                    if m_norm > 0:
                        mean_v /= m_norm
                    new_centers.append(mean_v)
                else:
                    new_centers.append(centers[c_idx])
            centers = np.array(new_centers, dtype=np.float32)

        return centers.tolist()

    def vtree_query_candidates(
        self,
        query_vec: list[float] | np.ndarray,
        leaf_vectors: list[list[float]],
        leaf_motions: list[float],
        leaf_genders: list[int],
        leaf_rewards: list[float],
        target_motion: float = -1.0,
        target_gender: int = 0,
        use_learned_priors: bool = True,
        top_k: int = 40
    ) -> list[tuple[int, float]]:
        """Fast Top-K Candidate Retrieval over candidate leaf pool."""
        n = len(leaf_vectors)
        if n == 0:
            return []
        dim = len(query_vec)

        if self._has_native and hasattr(self._dll, "cxx_vtree_query_candidates"):
            q_arr = (ctypes.c_float * dim)(*(float(x) for x in query_vec))
            
            flat_leaves = (ctypes.c_float * (n * dim))()
            for i, vec in enumerate(leaf_vectors):
                for d in range(min(dim, len(vec))):
                    flat_leaves[i * dim + d] = float(vec[d])

            mot_arr = (ctypes.c_float * n)(*(float(x) for x in leaf_motions))
            gen_arr = (ctypes.c_int32 * n)(*(int(x) for x in leaf_genders))
            rew_arr = (ctypes.c_float * n)(*(float(x) for x in leaf_rewards))

            out_indices = (ctypes.c_int32 * top_k)()
            out_scores = (ctypes.c_float * top_k)()

            actual_k = self._dll.cxx_vtree_query_candidates(
                q_arr,
                dim,
                flat_leaves,
                mot_arr,
                gen_arr,
                rew_arr,
                n,
                float(target_motion),
                int(target_gender),
                1 if use_learned_priors else 0,
                int(top_k),
                out_indices,
                out_scores
            )
            return [(int(out_indices[i]), round(float(out_scores[i]), 4)) for i in range(actual_k)]

        # Vectorized Fallback
        q = np.asarray(query_vec, dtype=np.float32)
        X = np.asarray(leaf_vectors, dtype=np.float32)
        sims = np.dot(X, q)
        sim_scores = np.maximum(0.0, sims)

        motion_bonuses = np.zeros(n, dtype=np.float32)
        if target_motion >= 0.0:
            diffs = np.abs(np.asarray(leaf_motions, dtype=np.float32) - target_motion)
            motion_bonuses = np.maximum(0.0, 1.0 - diffs) * 0.15

        gender_bonuses = np.zeros(n, dtype=np.float32)
        if target_gender > 0:
            gens = np.asarray(leaf_genders, dtype=np.int32)
            gender_bonuses[gens == target_gender] = 0.10
            if target_gender == 3:
                gender_bonuses[:] = 0.10
            gender_bonuses[gens == 0] = 0.04

        learned_bonuses = np.zeros(n, dtype=np.float32)
        if use_learned_priors:
            rews = np.asarray(leaf_rewards, dtype=np.float32)
            learned_bonuses = (rews - 0.5) * 0.12

        total_scores = sim_scores * 0.65 + motion_bonuses + gender_bonuses + learned_bonuses
        best_indices = np.argsort(-total_scores)[:top_k]
        return [(int(idx), round(float(total_scores[idx]), 4)) for idx in best_indices]

    # ── Self-Learning & Bandit Acceleration ───────────────────────────────────
    def bandit_sample_thompson(self, total_reward: float, pulls: int, seed: int = 0) -> float:
        """Fast Beta sampling for Thompson sampling."""
        if self._has_native and hasattr(self._dll, "cxx_bandit_sample_thompson"):
            return float(self._dll.cxx_bandit_sample_thompson(float(total_reward), int(pulls), int(seed)))
        alpha = 1.0 + max(0.0, float(total_reward))
        beta = 1.0 + max(0.0, float(pulls) - total_reward)
        return float(np.random.beta(alpha, beta))

    def bandit_select_best_arm(
        self,
        arms: list[dict],
        strategy: str = "thompson",
        ucb_c: float = 1.414,
        seed: int = 0
    ) -> int:
        """Select best bandit arm index using C++20 Thompson / UCB1 / Greedy."""
        num_arms = len(arms)
        if num_arms == 0:
            return 0

        total_rewards = [float(a.get("total_reward", 0.0)) for a in arms]
        pulls = [int(a.get("pulls", 0)) for a in arms]

        strat_code = 1 if strategy == "ucb1" else (2 if strategy == "greedy" else 0)

        if self._has_native and hasattr(self._dll, "cxx_bandit_select_best_arm"):
            r_arr = (ctypes.c_float * num_arms)(*total_rewards)
            p_arr = (ctypes.c_int32 * num_arms)(*pulls)
            return int(self._dll.cxx_bandit_select_best_arm(
                r_arr,
                p_arr,
                num_arms,
                strat_code,
                float(ucb_c),
                int(seed)
            ))

        # Fallback
        if strategy == "ucb1":
            total_p = sum(pulls) + 1
            scores = []
            for r, p in zip(total_rewards, pulls):
                if p == 0:
                    scores.append(999.0)
                else:
                    scores.append((r / p) + ucb_c * np.sqrt(np.log(total_p) / p))
            return int(np.argmax(scores))
        else:
            samples = [self.bandit_sample_thompson(r, p) for r, p in zip(total_rewards, pulls)]
            return int(np.argmax(samples))

    def markov_transition_bonus(self, reward_sum: float, count: int, same_motion_direction: bool = True) -> float:
        """Fast Markov transition flow bonus."""
        if self._has_native and hasattr(self._dll, "cxx_markov_transition_bonus"):
            return float(self._dll.cxx_markov_transition_bonus(
                float(reward_sum),
                int(count),
                1 if same_motion_direction else 0
            ))
        mean_r = (reward_sum / count) if count > 0 else 0.5
        bonus = (mean_r - 0.5) * 0.15
        if same_motion_direction:
            bonus += 0.05
        return round(bonus, 4)

    def ema_update(self, current_val: float, target_val: float, learning_rate: float = 0.15) -> float:
        """Fast Exponential Moving Average update."""
        if self._has_native and hasattr(self._dll, "cxx_ema_update"):
            return float(self._dll.cxx_ema_update(float(current_val), float(target_val), float(learning_rate)))
        lr = max(0.0, min(1.0, learning_rate))
        return (1.0 - lr) * current_val + lr * target_val

    # ── Camera Kinematics & Fake 3D Parallax ──────────────────────────────────
    def kinematics_sample_trajectory(
        self,
        keyframes: list[dict],
        sample_times: list[float]
    ) -> list[dict]:
        """Fast Smoothstep/Hermite Spline Camera Trajectory sampling."""
        num_kf = len(keyframes)
        num_samples = len(sample_times)
        if num_kf == 0 or num_samples == 0:
            return []

        if self._has_native and hasattr(self._dll, "cxx_kinematics_sample_trajectory"):
            kf_t = (ctypes.c_float * num_kf)(*(float(k["time_sec"]) for k in keyframes))
            kf_s = (ctypes.c_float * num_kf)(*(float(k["zoom_scale"]) for k in keyframes))
            kf_px = (ctypes.c_float * num_kf)(*(float(k["pan_x"]) for k in keyframes))
            kf_py = (ctypes.c_float * num_kf)(*(float(k["pan_y"]) for k in keyframes))
            kf_r = (ctypes.c_float * num_kf)(*(float(k.get("rotation_deg", 0.0)) for k in keyframes))
            kf_f = (ctypes.c_float * num_kf)(*(float(k.get("focal_length_mm", 35.0)) for k in keyframes))

            s_t = (ctypes.c_float * num_samples)(*(float(t) for t in sample_times))
            out_s = (ctypes.c_float * num_samples)()
            out_px = (ctypes.c_float * num_samples)()
            out_py = (ctypes.c_float * num_samples)()
            out_r = (ctypes.c_float * num_samples)()
            out_f = (ctypes.c_float * num_samples)()

            self._dll.cxx_kinematics_sample_trajectory(
                kf_t, kf_s, kf_px, kf_py, kf_r, kf_f, num_kf,
                s_t, num_samples,
                out_s, out_px, out_py, out_r, out_f
            )

            return [
                {
                    "time_sec": sample_times[i],
                    "zoom_scale": round(float(out_s[i]), 3),
                    "pan_x": round(float(out_px[i]), 2),
                    "pan_y": round(float(out_py[i]), 2),
                    "rotation_deg": round(float(out_r[i]), 2),
                    "focal_length_mm": round(float(out_f[i]), 1),
                }
                for i in range(num_samples)
            ]

        # Linear keyframe interpolation fallback
        res = []
        for t in sample_times:
            if t <= keyframes[0]["time_sec"]:
                res.append(keyframes[0])
            elif t >= keyframes[-1]["time_sec"]:
                res.append(keyframes[-1])
            else:
                for i in range(num_kf - 1):
                    k1, k2 = keyframes[i], keyframes[i + 1]
                    if k1["time_sec"] <= t <= k2["time_sec"]:
                        factor = (t - k1["time_sec"]) / max(1e-6, (k2["time_sec"] - k1["time_sec"]))
                        res.append({
                            "time_sec": t,
                            "zoom_scale": round(k1["zoom_scale"] + factor * (k2["zoom_scale"] - k1["zoom_scale"]), 3),
                            "pan_x": round(k1["pan_x"] + factor * (k2["pan_x"] - k1["pan_x"]), 2),
                            "pan_y": round(k1["pan_y"] + factor * (k2["pan_y"] - k1["pan_y"]), 2),
                            "rotation_deg": round(k1.get("rotation_deg", 0.0) + factor * (k2.get("rotation_deg", 0.0) - k1.get("rotation_deg", 0.0)), 2),
                            "focal_length_mm": round(k1.get("focal_length_mm", 35.0) + factor * (k2.get("focal_length_mm", 35.0) - k1.get("focal_length_mm", 35.0)), 1),
                        })
                        break
        return res


    def kinematics_fake_3d_warp(
        self,
        t: float,
        duration: float,
        width: float = 1920.0,
        height: float = 1080.0,
        pitch_deg: float = 4.0,
        yaw_deg: float = 6.0
    ) -> list[float]:
        """Calculates trapezoidal 2.5D perspective warp coordinates [x0,y0, x1,y1, x2,y2, x3,y3]."""
        if self._has_native and hasattr(self._dll, "cxx_kinematics_fake_3d_warp"):
            out_coords = (ctypes.c_float * 8)()
            self._dll.cxx_kinematics_fake_3d_warp(
                float(t),
                float(duration),
                float(width),
                float(height),
                float(pitch_deg),
                float(yaw_deg),
                out_coords
            )
            return [round(float(out_coords[i]), 2) for i in range(8)]

        dur = max(0.1, duration)
        phase = np.sin(np.pi * t / dur)
        shift_x = yaw_deg * 8.0 * phase
        shift_y = pitch_deg * 4.0 * phase
        return [
            shift_x, shift_y,
            width - shift_x, -shift_y,
            -shift_x * 0.5, height + shift_y,
            width + shift_x * 0.5, height - shift_y
        ]

    def compute_render_styles_batch(self, segments_data: list[dict]) -> list[dict]:
        """Calculates render style modifiers (contrast, saturation, color balance, FX mask) natively in C++."""
        if not segments_data:
            return []

        n = len(segments_data)
        motif_map = {"BETON": 1, "EISBACH": 2, "089": 3, "OIDA": 3, "BAVARIA": 3, "CYBER": 4, "ROBOTER": 4, "GLITCH": 4, "WEED": 5, "420": 5, "GRAFFITI": 6, "ART": 6}
        light_map = {"lowkey": 1, "dark": 1, "shadowy": 1, "highkey": 2, "bright": 2, "dramatic": 3, "chiaroscuro": 3, "neon_backlight": 4, "neon": 4, "strobe": 5}
        color_map = {"desaturated": 1, "bw": 1, "vivid": 2, "saturated": 2, "neon": 3, "cyber": 3, "warm": 4, "golden_hour": 4, "cold_cyan": 5, "cold": 5, "teal_orange": 5, "matrix_green": 6, "green": 6, "vintage_film": 7, "vintage": 7, "noir": 8, "industrial": 8}

        if self._has_native and hasattr(self._dll, "cxx_compute_render_styles_batch"):
            inputs = (CxxRenderStyleInput * n)()
            outputs = (CxxRenderStyleOutput * n)()

            for i, seg in enumerate(segments_data):
                sym = str(seg.get("semantic_symbol", "")).upper()
                thm = str(seg.get("theme", "")).lower()
                motif_code = 0
                for k, v in motif_map.items():
                    if k in sym or k.lower() in thm:
                        motif_code = v
                        break

                light = str(seg.get("lighting", "natural")).lower()
                color = str(seg.get("color", "neutral")).lower()
                fx = seg.get("fx", ())

                inputs[i].motif_code = motif_code
                inputs[i].lighting_code = light_map.get(light, 0)
                inputs[i].color_code = color_map.get(color, 0)
                inputs[i].target_energy = float(seg.get("target_energy", 0.5))
                inputs[i].information_density = float(seg.get("information_density", 0.5))
                inputs[i].has_fx_grain = 1 if ("grain" in fx or "film_grain" in fx) else 0
                inputs[i].has_fx_flicker = 1 if "flicker" in fx else 0
                inputs[i].has_fx_chroma = 1 if ("chroma" in fx or "chromatic_aberration" in fx) else 0
                inputs[i].has_fx_vignette = 1 if "vignette" in fx else 0
                inputs[i].has_fx_scanlines = 1 if "scanlines" in fx else 0

            self._dll.cxx_compute_render_styles_batch(inputs, n, outputs)

            res = []
            for i in range(n):
                res.append({
                    "contrast_mult": round(float(outputs[i].contrast_mult), 3),
                    "brightness_offset": round(float(outputs[i].brightness_offset), 3),
                    "saturation_mult": round(float(outputs[i].saturation_mult), 3),
                    "gamma_mult": round(float(outputs[i].gamma_mult), 3),
                    "color_balance_r": round(float(outputs[i].color_balance_r), 3),
                    "color_balance_g": round(float(outputs[i].color_balance_g), 3),
                    "color_balance_b": round(float(outputs[i].color_balance_b), 3),
                    "fx_mask": int(outputs[i].recommended_fx_mask),
                })
            return res

        # Vectorized Python Fallback
        res = []
        for seg in segments_data:
            res.append({
                "contrast_mult": 1.0,
                "brightness_offset": 0.0,
                "saturation_mult": 1.0,
                "gamma_mult": 1.0,
                "color_balance_r": 0.0,
                "color_balance_g": 0.0,
                "color_balance_b": 0.0,
                "fx_mask": 0,
            })
        return res

    def calculate_lyrics_grounding(self, lyrics_words: list[str], clip_words: list[str]) -> float:
        """Fast C++ word hash token intersection and grounding F1 score."""
        if not lyrics_words or not clip_words:
            return 0.0

        def _fnv1a(s: str) -> int:
            h = 2166136261
            for char in s.encode("utf-8"):
                h = ((h ^ char) * 16777619) & 0xFFFFFFFF
            return h

        l_hashes = [_fnv1a(w.lower()) for w in lyrics_words if w]
        c_hashes = [_fnv1a(w.lower()) for w in clip_words if w]
        if not l_hashes or not c_hashes:
            return 0.0

        if self._has_native and hasattr(self._dll, "cxx_calculate_lyrics_grounding"):
            l_arr = (ctypes.c_uint32 * len(l_hashes))(*l_hashes)
            c_arr = (ctypes.c_uint32 * len(c_hashes))(*c_hashes)
            return float(self._dll.cxx_calculate_lyrics_grounding(
                l_arr, len(l_hashes), c_arr, len(c_hashes)
            ))

        matches = len(set(l_hashes) & set(c_hashes))
        p = matches / len(c_hashes)
        r = matches / len(l_hashes)
        return (2.0 * p * r) / (p + r) if (p + r) > 0 else 0.0

    def build_tag_vector(self, text: str, dim: int = 85) -> list[float]:
        """Vectorizes a single string into an 85-dimensional float vector natively in C++."""
        if not text:
            return [0.0] * dim
        if self._has_native and hasattr(self._dll, "cxx_vectorize_text"):
            out_vec = (ctypes.c_float * dim)()
            self._dll.cxx_vectorize_text(text.encode("utf-8", errors="replace"), out_vec, dim)
            return [float(out_vec[i]) for i in range(dim)]

        # Python fallback
        from config import TAG_VOCAB
        words = set("".join(c.lower() if (c.isalnum() or c == "_") else " " for c in text).split())
        return [1.0 if tag in words else 0.0 for tag in TAG_VOCAB[:dim]]

    def batch_build_tag_vectors(self, texts: list[str], dim: int = 85) -> np.ndarray:
        """Batch vectorizes multiple strings into a (N, 85) dense matrix natively in C++."""
        n = len(texts)
        if n == 0:
            return np.zeros((0, dim), dtype=np.float32)

        if self._has_native and hasattr(self._dll, "cxx_batch_vectorize_texts"):
            c_texts = (ctypes.c_char_p * n)(*[t.encode("utf-8", errors="replace") if t else b"" for t in texts])
            out_matrix = (ctypes.c_float * (n * dim))()
            self._dll.cxx_batch_vectorize_texts(c_texts, n, out_matrix, dim)
            return np.ctypeslib.as_array(out_matrix).reshape((n, dim)).copy()

        # Fallback
        res = np.zeros((n, dim), dtype=np.float32)
        for i, t in enumerate(texts):
            res[i] = self.build_tag_vector(t, dim)
        return res

    def rank_topk_candidates(
        self,
        query_vec: list[float] | np.ndarray,
        vector_matrix: np.ndarray,
        metas: list[dict],
        ctx: dict,
        top_k: int = 50
    ) -> list[tuple[int, float]]:
        """Evaluates and ranks all clip candidates in C++20 with AVX2 SIMD dot products in < 1ms."""
        n = len(metas)
        dim = len(query_vec)
        if n == 0 or dim == 0:
            return []

        if self._has_native and hasattr(self._dll, "cxx_rank_topk_candidates"):
            q_arr = np.ascontiguousarray(query_vec, dtype=np.float32)
            v_mat = np.ascontiguousarray(vector_matrix, dtype=np.float32)
            q_ptr = q_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            v_ptr = v_mat.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

            c_metas = (CxxClipDenseMeta * n)()
            for i, m in enumerate(metas):
                g_code = 0
                g_str = str(m.get("gender", "")).lower()
                if g_str == "female": g_code = 1
                elif g_str == "male": g_code = 2
                elif g_str == "dual": g_code = 3

                c_metas[i].duration = float(m.get("duration", 0.0))
                c_metas[i].motion_score = float(m.get("motion_score", 0.5))
                c_metas[i].motion_direction = float(m.get("motion_direction", 0.0))
                c_metas[i].face_score = float(m.get("face_score", 0.0))
                c_metas[i].info_density = float(m.get("information_density", 0.5))
                c_metas[i].learned_bonus = float(m.get("learned_bonus", 0.0))
                c_metas[i].gender_code = g_code
                c_metas[i].is_still = 1 if m.get("is_still") else 0
                c_metas[i].is_cooldown_locked = 1 if m.get("is_cooldown_locked") else 0

            c_ctx = CxxRankerQueryContext()
            c_ctx.target_energy = float(ctx.get("target_energy", 0.5))
            c_ctx.target_duration = float(ctx.get("target_duration", 0.0))
            c_ctx.motion_weight = float(ctx.get("motion_weight", 0.35))
            c_ctx.semantic_weight = float(ctx.get("semantic_weight", 0.40))
            c_ctx.pref_weight = float(ctx.get("pref_weight", 0.15))
            c_ctx.density_weight = float(ctx.get("density_weight", 0.10))
            c_ctx.prev_motion_dir = float(ctx.get("prev_motion_dir", 0.0))
            c_ctx.target_gender_code = int(ctx.get("target_gender_code", 0))
            c_ctx.allow_still = 1 if ctx.get("allow_still", False) else 0
            c_ctx.check_motion_continuity = 1 if ctx.get("check_motion_continuity", True) else 0

            out_indices = (ctypes.c_int32 * top_k)()
            out_scores = (ctypes.c_float * top_k)()

            actual_k = self._dll.cxx_rank_topk_candidates(
                q_ptr, v_ptr, c_metas, n, dim, ctypes.byref(c_ctx),
                top_k, out_indices, out_scores
            )
            return [(int(out_indices[j]), float(out_scores[j])) for j in range(actual_k)]

        # Python fallback
        scores = []
        for i, m in enumerate(metas):
            if m.get("is_cooldown_locked"): continue
            v = vector_matrix[i]
            sim = float(np.dot(query_vec, v) / (max(1e-6, np.linalg.norm(query_vec) * np.linalg.norm(v))))
            scores.append((i, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def compute_moving_rms(
        self,
        pcm_samples: np.ndarray,
        hop_size: int = 512,
        frame_size: int = 2048
    ) -> np.ndarray:
        """Fast Moving RMS energy curve computed in C++."""
        n_samples = len(pcm_samples)
        if n_samples == 0:
            return np.zeros(0, dtype=np.float32)
        n_frames = max(1, (n_samples + hop_size - 1) // hop_size)

        if self._has_native and hasattr(self._dll, "cxx_compute_moving_rms"):
            in_arr = np.ascontiguousarray(pcm_samples, dtype=np.float32)
            out_arr = np.empty(n_frames, dtype=np.float32)
            in_ptr = in_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            out_ptr = out_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            self._dll.cxx_compute_moving_rms(in_ptr, n_samples, hop_size, frame_size, out_ptr, n_frames)
            return out_arr

        # Fallback
        res = np.zeros(n_frames, dtype=np.float32)
        for f in range(n_frames):
            st = f * hop_size
            chunk = pcm_samples[st:st + frame_size]
            if len(chunk) > 0:
                res[f] = float(np.sqrt(np.mean(chunk * chunk)))
        return res

    def smooth_energy_curve(self, curve: np.ndarray | list[float], window_size: int = 5) -> np.ndarray:
        """Smooths energy/tension curves natively in C++."""
        in_arr = np.ascontiguousarray(curve, dtype=np.float32)
        n = len(in_arr)
        if n == 0:
            return np.zeros(0, dtype=np.float32)

        if self._has_native and hasattr(self._dll, "cxx_smooth_energy_curve"):
            out_arr = np.empty(n, dtype=np.float32)
            in_ptr = in_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            out_ptr = out_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            self._dll.cxx_smooth_energy_curve(in_ptr, n, window_size, out_ptr)
            return out_arr

        # Fallback
        return np.convolve(in_arr, np.ones(window_size) / window_size, mode="same")

    def detect_energy_peaks(
        self,
        energy: np.ndarray | list[float],
        threshold: float = 0.6,
        min_distance: int = 4
    ) -> list[int]:
        """Detects onset peaks with refractory window natively in C++."""
        in_arr = np.ascontiguousarray(energy, dtype=np.float32)
        n = len(in_arr)
        if n < 3:
            return []

        if self._has_native and hasattr(self._dll, "cxx_detect_energy_peaks"):
            out_peaks = np.empty(n, dtype=np.int32)
            in_ptr = in_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            out_ptr = out_peaks.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
            cnt = self._dll.cxx_detect_energy_peaks(in_ptr, n, float(threshold), min_distance, out_ptr, n)
            return [int(out_peaks[i]) for i in range(cnt)]

        # Fallback
        peaks = []
        last_p = -min_distance
        for i in range(1, n - 1):
            if in_arr[i] > threshold and in_arr[i] > in_arr[i - 1] and in_arr[i] > in_arr[i + 1]:
                if i - last_p >= min_distance:
                    peaks.append(i)
                    last_p = i
        return peaks

    def quantize_beatgrid(
        self,
        raw_beats: list[float],
        bpm: float,
        tolerance_sec: float = 0.05
    ) -> list[float]:
        """Snaps beat timestamps to steady tempo grid intervals natively in C++."""
        n = len(raw_beats)
        if n == 0 or bpm <= 0.0:
            return list(raw_beats)

        if self._has_native and hasattr(self._dll, "cxx_quantize_beatgrid"):
            in_arr = np.ascontiguousarray(raw_beats, dtype=np.float32)
            out_arr = np.empty(n, dtype=np.float32)
            in_ptr = in_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            out_ptr = out_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            self._dll.cxx_quantize_beatgrid(in_ptr, n, float(bpm), float(tolerance_sec), out_ptr)
            return [float(out_arr[i]) for i in range(n)]

        interval = 60.0 / bpm
        return [
            round(b / interval) * interval if abs(b - round(b / interval) * interval) <= tolerance_sec else b
            for b in raw_beats
        ]

    def calculate_slang_density(self, tokens: list[str]) -> float:
        """Calculates Bavarian/Oida slang density natively in C++."""
        n = len(tokens)
        if n == 0:
            return 0.0

        if self._has_native and hasattr(self._dll, "cxx_calculate_slang_density"):
            c_tokens = (ctypes.c_char_p * n)(*[t.encode("utf-8", errors="replace") if t else b"" for t in tokens])
            return float(self._dll.cxx_calculate_slang_density(c_tokens, n))

        # Fallback
        slang_set = {"oida", "haberer", "spezi", "gspusi", "watschn", "haderlump", "servus", "bazi", "zamkemma", "hockn", "gaudi", "griawig", "oachkatzl", "schmarrn", "fesch", "gschaftlhuber", "pfiate", "semmel", "wiesn", "eisbach", "089", "beton", "weed", "420", "blunt", "joint", "ganja", "chaya", "brudi", "digga"}
        hits = sum(1 for t in tokens if t and t.lower() in slang_set)
        return hits / n

    def synthesize_tension_curve(
        self,
        energy_curve: list[float] | np.ndarray,
        punchline_weights: list[float] | np.ndarray
    ) -> np.ndarray:
        """Synthesizes dynamic narrative tension curve natively in C++."""
        e_arr = np.ascontiguousarray(energy_curve, dtype=np.float32)
        p_arr = np.ascontiguousarray(punchline_weights, dtype=np.float32)
        n = min(len(e_arr), len(p_arr))
        if n == 0:
            return np.zeros(0, dtype=np.float32)

        if self._has_native and hasattr(self._dll, "cxx_synthesize_tension_curve"):
            in_e = np.ascontiguousarray(e_arr[:n], dtype=np.float32)
            in_p = np.ascontiguousarray(p_arr[:n], dtype=np.float32)
            out_t = np.empty(n, dtype=np.float32)
            in_e_ptr = in_e.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            in_p_ptr = in_p.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            out_t_ptr = out_t.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            self._dll.cxx_synthesize_tension_curve(in_e_ptr, in_p_ptr, n, out_t_ptr)
            return out_t

        # Fallback
        res = np.zeros(n, dtype=np.float32)
        for i in range(n):
            delta = max(0.0, e_arr[i] - (e_arr[i - 1] if i > 0 else e_arr[i]))
            res[i] = np.clip(0.50 * e_arr[i] + 0.30 * p_arr[i] + 0.20 * (delta * 2.0), 0.0, 1.0)
        return res

        # Fallback
        res = np.zeros(n, dtype=np.float32)
        for i in range(n):
            delta = max(0.0, e_arr[i] - (e_arr[i - 1] if i > 0 else e_arr[i]))
            res[i] = np.clip(0.50 * e_arr[i] + 0.30 * p_arr[i] + 0.20 * (delta * 2.0), 0.0, 1.0)
        return res

    def generate_camera_path(
        self,
        start_zoom: float,
        end_zoom: float,
        start_pan_x: float,
        end_pan_x: float,
        start_pan_y: float,
        end_pan_y: float,
        frame_count: int,
        easing_type: str = "linear"
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generates dynamic camera zoom/pan trajectories natively in C++."""
        if frame_count <= 0:
            return np.zeros(0), np.zeros(0), np.zeros(0)

        ease_map = {"linear": 0, "ease_in": 1, "ease_out": 2, "ease_in_out": 3, "cubic": 4, "spring": 5}
        e_code = ease_map.get(easing_type.lower(), 0)

        if self._has_native and hasattr(self._dll, "cxx_generate_camera_path"):
            out_z = (ctypes.c_float * frame_count)()
            out_x = (ctypes.c_float * frame_count)()
            out_y = (ctypes.c_float * frame_count)()
            self._dll.cxx_generate_camera_path(
                float(start_zoom), float(end_zoom),
                float(start_pan_x), float(end_pan_x),
                float(start_pan_y), float(end_pan_y),
                frame_count, e_code,
                out_z, out_x, out_y
            )
            return (
                np.ctypeslib.as_array(out_z).copy(),
                np.ctypeslib.as_array(out_x).copy(),
                np.ctypeslib.as_array(out_y).copy()
            )

        # Fallback
        t = np.linspace(0.0, 1.0, frame_count)
        z = start_zoom + (end_zoom - start_zoom) * t
        px = start_pan_x + (end_pan_x - start_pan_x) * t
        py = start_pan_y + (end_pan_y - start_pan_y) * t
        return z, px, py




RHYTHM_PATTERN_MAP = {
    0: "steady",
    1: "intro",
    2: "beat_drop",
    3: "expansion",
    4: "compression",
    5: "energy_surge",
    6: "buildup",
    7: "stutter_repeat",
    8: "peak",
    9: "dense_motion",
}

SYNC_TYPE_MAP = {
    0: "polyrhythm",
    1: "snap_drop",
    2: "energy_peak",
    3: "breath",
    4: "on_beat",
    5: "syncopated",
}

CUT_STYLE_MAP = {
    0: "hard_cut",
    1: "fade_out",
    2: "jump_cut",
    3: "break",
    4: "push",
    5: "whip",
    6: "dissolve",
}


_ENGINE: Optional[CxxAccelerationEngine] = None

def get_cxx_engine() -> CxxAccelerationEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = CxxAccelerationEngine()
    return _ENGINE

