"""
tests/test_clip_highlight.py — Unit-Tests für das Dual-Frame Highlight Modul

Testet:
  1. composition_score (Grauwert-Frame, leerer Frame, richtiger Frame)
  2. visual_difference (identische vs. sehr unterschiedliche Frames)
  3. emotion_score (mit und ohne Tags)
  4. score_clip_pair → Highlight-Formel H, recommendation (USE/MAYBE/SKIP)
  5. select_clip_duration → 140 BPM Bars-Quantisierung (FULL / CROSSFADE / SHORT / FULL_HOLD)
  6. beat_sync_clip → Frame-genaues Snapping
  7. get_clip_highlight_score → Fallback aus meta-Dict
  8. Integration: analyze_clip-Output-Format-Felder (highlight_score, sync_140bpm usw.)
"""
import math
import numpy as np
import pytest

from clip_highlight import (
    composition_score,
    visual_difference,
    emotion_score,
    score_clip_pair,
    select_clip_duration,
    beat_sync_clip,
    get_clip_highlight_score,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _solid_frame(r: int = 128, g: int = 128, b: int = 128, size=(36, 64)) -> np.ndarray:
    """Einfarbiger BGR-Frame für Tests."""
    h, w = size
    return np.full((h, w, 3), (b, g, r), dtype=np.uint8)


def _random_frame(seed: int = 42, size=(36, 64)) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (*size, 3), dtype=np.uint8)


# ── composition_score ─────────────────────────────────────────────────────────

class TestCompositionScore:
    def test_none_returns_neutral(self):
        assert composition_score(None) == 0.5

    def test_empty_array_returns_neutral(self):
        assert composition_score(np.array([])) == 0.5

    def test_solid_dark_frame_low_contrast(self):
        frame = _solid_frame(0, 0, 0)
        score = composition_score(frame)
        assert 0.0 <= score <= 1.0, f"Expected 0-1 but got {score}"
        # Vollständig schwarze Frames haben keinen Kontrast und kaum Schärfe
        assert score < 0.7

    def test_noise_frame_higher_sharpness(self):
        frame = _random_frame(42)
        score = composition_score(frame)
        assert 0.0 <= score <= 1.0
        # Rauschen hat maximale Schärfe und Kontrast
        assert score > 0.3

    def test_grayscale_frame(self):
        """2D Grauwertframe soll ebenfalls ohne Fehler ausgewertet werden."""
        gray = np.random.randint(0, 255, (36, 64), dtype=np.uint8)
        score = composition_score(gray)
        assert 0.0 <= score <= 1.0


# ── visual_difference ─────────────────────────────────────────────────────────

class TestVisualDifference:
    def test_identical_frames_near_zero(self):
        frame = _solid_frame(100, 100, 100)
        diff = visual_difference(frame, frame)
        assert diff < 0.05, f"Identische Frames sollten fast 0 Differenz haben, got {diff}"

    def test_opposite_frames_high_diff(self):
        black = _solid_frame(0, 0, 0)
        white = _solid_frame(255, 255, 255)
        diff = visual_difference(black, white)
        assert diff > 0.8, f"Schwarz vs. Weiß sollte hohe Differenz haben, got {diff}"

    def test_none_start_returns_neutral(self):
        frame = _solid_frame(128, 128, 128)
        assert visual_difference(None, frame) == 0.5

    def test_result_in_range(self):
        f1 = _random_frame(1)
        f2 = _random_frame(99)
        diff = visual_difference(f1, f2)
        assert 0.0 <= diff <= 1.0


# ── emotion_score ─────────────────────────────────────────────────────────────

class TestEmotionScore:
    def test_none_returns_half(self):
        assert emotion_score(None) == 0.5

    def test_in_range(self):
        frame = _random_frame(7)
        score = emotion_score(frame)
        assert 0.0 <= score <= 1.0

    def test_high_energy_tags_boost(self):
        frame = _solid_frame(200, 50, 50)  # Rotes Frame (saturiert)
        base = emotion_score(frame, tags=None)
        boosted = emotion_score(frame, tags=["energetic", "hype", "fire"])
        assert boosted >= base

    def test_tag_boost_capped(self):
        frame = _random_frame(11)
        score = emotion_score(frame, tags=["energetic", "intense", "aggressive", "party"])
        assert score <= 1.0


# ── score_clip_pair ────────────────────────────────────────────────────────────

class TestScoreClipPair:
    def test_returns_all_keys(self):
        f1 = _random_frame(1)
        f2 = _random_frame(2)
        result = score_clip_pair(f1, f2)
        assert "highlight_score" in result
        assert "recommendation" in result
        assert "composition" in result
        assert "delta" in result
        assert "emotion" in result
        assert "emotional_trip" in result

    def test_highlight_in_range(self):
        f1, f2 = _random_frame(3), _random_frame(4)
        res = score_clip_pair(f1, f2)
        assert 0.0 <= res["highlight_score"] <= 1.0

    def test_recommendation_use_maybe_skip(self):
        f1, f2 = _random_frame(5), _random_frame(6)
        res = score_clip_pair(f1, f2)
        assert res["recommendation"] in ("USE", "MAYBE", "SKIP")

    def test_none_frames_returns_valid(self):
        """Keine Frames → neutrale Fallback-Werte, kein Crash."""
        res = score_clip_pair(None, None)
        assert 0.0 <= res["highlight_score"] <= 1.0
        assert res["recommendation"] in ("USE", "MAYBE", "SKIP")

    def test_identical_frames_low_delta(self):
        frame = _solid_frame(180, 120, 60)
        res = score_clip_pair(frame, frame)
        # Identische Frames → Delta nahe 0 → niedrige Dynamik-Komponente
        assert res["delta"] < 0.1

    def test_high_contrast_pair_higher_score(self):
        black = _solid_frame(0, 0, 0)
        white = _solid_frame(255, 255, 255)
        res = score_clip_pair(black, white)
        res_same = score_clip_pair(black, black)
        assert res["highlight_score"] >= res_same["highlight_score"]

    def test_emotional_trip_keys(self):
        f1, f2 = _random_frame(10), _random_frame(11)
        res = score_clip_pair(f1, f2)
        trip = res["emotional_trip"]
        assert "score" in trip
        assert "journey" in trip
        assert trip["journey"] in ("rise", "fall", "stable")


# ── select_clip_duration (140 BPM Quantisierung) ─────────────────────────────

class TestSelectClipDuration:
    BPM = 140.0

    def _beat_dur(self):
        return 60.0 / self.BPM

    def _bar_dur(self):
        return 4.0 * self._beat_dur()

    def test_full_hold_on_very_high_score(self):
        res = select_clip_duration(0.95, bpm=self.BPM)
        assert res["strategy"] == "FULL_HOLD"
        assert res["bars"] == 4.0
        assert res["action"] == "freeze_hold"

    def test_full_cut_on_high_score(self):
        res = select_clip_duration(0.82, bpm=self.BPM)
        assert res["strategy"] == "FULL"
        assert res["bars"] == 4.0
        assert res["on_beat"] is True

    def test_crossfade_on_mid_score(self):
        res = select_clip_duration(0.70, bpm=self.BPM)
        assert res["strategy"] == "CROSSFADE"
        assert res["bars"] == 3.5
        # 3.5 Bars bei 140 BPM = exakt 6.000 s
        expected = pytest.approx(6.0, abs=0.01)
        assert res["duration"] == expected

    def test_short_on_low_score(self):
        res = select_clip_duration(0.40, bpm=self.BPM)
        assert res["strategy"] == "SHORT"
        assert res["bars"] == 3.0

    def test_140bpm_math(self):
        """Beat-Mathematik: 1 Beat = 60/140 ≈ 428.57 ms, 1 Bar = 1714.28 ms."""
        res = select_clip_duration(0.82, bpm=self.BPM)
        assert res["beat_duration_ms"] == pytest.approx(428.57, abs=1.0)
        assert res["bar_duration_ms"] == pytest.approx(1714.29, abs=2.0)

    def test_crossfade_6_seconds(self):
        """3.5 Bars = 14 Beats = genau 6.000 s bei 140 BPM."""
        res = select_clip_duration(0.70, bpm=self.BPM)
        assert res["beats"] == 14
        # 6.000 s * 24 fps = 144 Frames
        assert res["frames_24fps"] == 144

    def test_result_keys_present(self):
        res = select_clip_duration(0.70, bpm=self.BPM)
        for key in ("highlight_score", "bpm", "bars", "duration", "beats",
                    "frames_24fps", "strategy", "on_beat", "action",
                    "beat_duration_ms", "bar_duration_ms"):
            assert key in res, f"Fehlender Key: {key}"

    def test_invalid_bpm_fallback(self):
        """Ungültige BPM (0 oder None) → Fallback auf 140."""
        res1 = select_clip_duration(0.70, bpm=0.0)
        assert res1["bpm"] == pytest.approx(140.0, abs=1.0) or res1["bpm"] > 0


# ── beat_sync_clip ─────────────────────────────────────────────────────────────

class TestBeatSyncClip:
    def test_beat_snap_aligns_start(self):
        """Startzeit sollte auf nächsten Beat-Index gerundet werden."""
        res = beat_sync_clip(0.0, clip_duration=6.0, bpm=140.0, fps=24)
        assert res["start_time"] == pytest.approx(0.0, abs=0.001)
        assert res["start_frame"] == 0

    def test_bars_quantized_to_half_bar(self):
        """6 Sekunden → 3.5 Bars bei 140 BPM."""
        res = beat_sync_clip(0.0, clip_duration=6.0, bpm=140.0, fps=24)
        assert res["bars"] == pytest.approx(3.5, abs=0.1)

    def test_frame_counts_match(self):
        res = beat_sync_clip(0.0, clip_duration=6.857, bpm=140.0, fps=24)
        assert res["total_frames"] > 0
        assert res["end_frame"] > res["start_frame"]

    def test_result_keys(self):
        res = beat_sync_clip(0.0, bpm=140.0)
        for k in ("start_time", "duration", "bars", "start_frame",
                  "end_frame", "total_frames", "beat_index", "bpm", "fps"):
            assert k in res


# ── get_clip_highlight_score ───────────────────────────────────────────────────

class TestGetClipHighlightScore:
    def test_none_returns_half(self):
        assert get_clip_highlight_score(None) == 0.5

    def test_explicit_highlight_score(self):
        meta = {"highlight_score": 0.87}
        assert get_clip_highlight_score(meta) == pytest.approx(0.87, abs=0.001)

    def test_fallback_from_motion_face_density(self):
        meta = {
            "motion_score": 0.8,
            "face_score": 0.6,
            "information_density": 0.7,
        }
        score = get_clip_highlight_score(meta)
        assert 0.0 <= score <= 1.0
        # Hohe motion + face → sollte gut sein
        assert score > 0.4

    def test_zero_meta_returns_low(self):
        meta = {"motion_score": 0.0, "face_score": 0.0, "information_density": 0.0}
        assert get_clip_highlight_score(meta) < 0.5
