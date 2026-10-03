"""
clip_highlight.py — Dual-Frame Highlight-Erkennung & 140-BPM Beat-Sync-Quantisierung

Speziell optimiert für ClipPools mit vielen 6-Sekunden-Videos und Start-/Endbild-Paaren:
  1. Dual-Frame-Analyse (Startframe + Endframe):
     - Komposition: Symmetrie, Rule of Thirds, Kontrast, Bildschärfe
     - Visuelle Differenz Delta(C_start, C_end): Dynamik & Bewegung
     - Emotionale Reise: Valence-Arousal, Emotional Trip
     - H = 0.25*C_start + 0.25*C_end + 0.20*DeltaC + 0.15*E_start + 0.15*E_end
     - Recommendation: USE (> 0.8), MAYBE (0.6 - 0.8), SKIP (< 0.6)
  2. 140 BPM Beat-Sync Mathematik:
     - 1 Beat = 60 / 140 = 0.42857 s (428.57 ms)
     - 1 Bar = 4 Beats = 1.71428 s
     - 6 Sekunden = 14 Beats = 3.5 Bars
     - Quantisierung nach Highlight-Score:
       * H > 0.9 -> 4 Bars (6.857 s) + Hold/Freeze ("FULL_HOLD")
       * H > 0.8 -> 4 Bars (6.857 s) ("FULL")
       * 0.6 <= H <= 0.8 -> 3.5 Bars (6.000 s) ("CROSSFADE")
       * H < 0.6 -> 3 Bars (5.143 s) ("SHORT")
  3. Frame-genaue Platzierung:
     - Startframe = round(beat_time * fps)
     - Endframe = round((start_time + duration) * fps)
"""

import math
from typing import Any

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


def composition_score(frame: np.ndarray | None) -> float:
    """Berechnet einen Kompositions-Score (0.0 .. 1.0) für einen Frame.

    5 Signale, gewichtet kombiniert:
      1. Schärfe / Texture-Reichhaltigkeit (Laplacian Variance, 30%)
      2. Dynamikumfang / Histogramm-Spreizung (Histogram Spread, 25%)
      3. Farbtemperatur-Interesse: Warm/Kalt vs. Grau/Flat (20%)
      4. Rule-of-Thirds / Vordergrund-Hintergrund-Differenz (15%)
      5. Horizontale Balance (10%)

    Optimiert für Clips, die überwiegend aus definierten Start-/Endbildern
    bestehen (6s Showcase-Pools): statt bloßem RMS-Kontrast wird der
    Histogramm-Interquartilabstand (P10→P90) als robuster Dynamikumfang-Proxy
    verwendet — unempfindlich gegen weiße/schwarze Überblendungsränder.
    """
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return 0.5

    try:
        if len(frame.shape) == 3 and frame.shape[2] >= 3:
            is_color = True
            if cv2 is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = np.mean(frame[:, :, :3], axis=2).astype(np.uint8)
        else:
            is_color = False
            gray = frame.astype(np.uint8) if frame.dtype != np.uint8 else frame

        h, w = gray.shape[:2]
        if h < 4 or w < 4:
            return 0.5

        norm = gray.astype(np.float32) / 255.0

        # ── 1. Schärfe (Laplacian Variance) ──────────────────────────────────
        if cv2 is not None:
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            sharpness = min(1.0, math.log1p(max(0.0, lap_var)) / 8.5)
        else:
            grad_x = np.diff(norm, axis=1)
            grad_y = np.diff(norm, axis=0)
            sharpness = min(1.0, (np.mean(np.abs(grad_x)) + np.mean(np.abs(grad_y))) * 9.0)

        # ── 2. Dynamikumfang (P10→P90 Histogramm-Spreizung) ─────────────────
        p10, p90 = float(np.percentile(norm, 10)), float(np.percentile(norm, 90))
        hist_spread = min(1.0, (p90 - p10) * 1.35)

        # ── 3. Farbtemperatur-Interesse ───────────────────────────────────────
        if is_color and cv2 is not None:
            b = frame[:, :, 0].astype(np.float32)
            g = frame[:, :, 1].astype(np.float32)
            r = frame[:, :, 2].astype(np.float32)
            # Warm = hoher R/G-Anteil, Kalt = hoher B-Anteil — beide sind interessant
            warm_signal = float(np.mean(r - b)) / 255.0       # pos = warm, neg = kalt
            sat_proxy = float(np.mean(np.abs(r - g) + np.abs(g - b))) / 255.0
            color_temp_score = min(1.0, abs(warm_signal) * 1.4 + sat_proxy * 0.6)
        else:
            color_temp_score = 0.4  # Graustufen-Fallback

        # ── 4. Rule-of-Thirds / Vordergrund-Hintergrund-Differenz ───────────
        h3, w3 = h // 3, w // 3
        center = norm[h3 : 2 * h3, w3 : 2 * w3]
        outer_mean = float(np.mean(norm))
        center_mean = float(np.mean(center)) if center.size > 0 else outer_mean
        focus_score = min(1.0, 0.5 + abs(center_mean - outer_mean) * 2.0)

        # ── 5. Horizontale Balance ────────────────────────────────────────────
        left = norm[:, : w // 2]
        right = np.fliplr(norm[:, w - (w // 2) :])
        min_w = min(left.shape[1], right.shape[1])
        if min_w > 0:
            balance = max(0.0, 1.0 - float(np.mean(np.abs(left[:, :min_w] - right[:, :min_w]))) * 2.5)
        else:
            balance = 0.5

        total = (
            0.30 * sharpness
            + 0.25 * hist_spread
            + 0.20 * color_temp_score
            + 0.15 * focus_score
            + 0.10 * balance
        )
        return float(round(max(0.0, min(1.0, total)), 4))

    except Exception:
        return 0.5


def visual_difference(start_frame: np.ndarray | None, end_frame: np.ndarray | None) -> float:
    """Berechnet die visuelle Differenz Delta(C_start, C_end) zwischen Start- und Endframe (0.0 .. 1.0).
    Hohe Differenz deutet auf signifikante Szenenbewegung, Motivwechsel oder Dynamik hin.
    """
    if start_frame is None or end_frame is None:
        return 0.5

    try:
        if cv2 is not None and len(start_frame.shape) == 3:
            g1 = cv2.cvtColor(start_frame, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(end_frame, cv2.COLOR_BGR2GRAY)
            s1 = cv2.resize(g1, (64, 36)).astype(np.float32) / 255.0
            s2 = cv2.resize(g2, (64, 36)).astype(np.float32) / 255.0
        elif len(start_frame.shape) == 3:
            g1 = np.mean(start_frame, axis=2)
            g2 = np.mean(end_frame, axis=2)
            s1 = g1[:36, :64].astype(np.float32) / 255.0
            s2 = g2[:36, :64].astype(np.float32) / 255.0
        else:
            s1 = start_frame[:36, :64].astype(np.float32) / 255.0
            s2 = end_frame[:36, :64].astype(np.float32) / 255.0

        # Signal 1: Globaler Helligkeit-MAD (robust gegen einfarbige Fades)
        lum_diff = float(np.mean(np.abs(s1 - s2)))

        # Signal 2: Lokaler Block-Diff (3x3 Grid) — erkennt partielle Bildveränderungen
        bh, bw = max(1, s1.shape[0] // 3), max(1, s1.shape[1] // 3)
        block_diffs = []
        for br in range(3):
            for bc in range(3):
                b1 = s1[br * bh:(br + 1) * bh, bc * bw:(bc + 1) * bw]
                b2 = s2[br * bh:(br + 1) * bh, bc * bw:(bc + 1) * bw]
                if b1.size > 0 and b2.size > 0:
                    block_diffs.append(float(np.mean(np.abs(b1 - b2))))
        block_diff = float(np.max(block_diffs)) if block_diffs else lum_diff

        # Signal 3: Hue-Shift (Farbton-Veränderung = Szene ändert sich tatsächlich)
        if cv2 is not None and len(start_frame.shape) == 3:
            try:
                hsv1 = cv2.cvtColor(cv2.resize(start_frame, (32, 18)), cv2.COLOR_BGR2HSV)
                hsv2 = cv2.cvtColor(cv2.resize(end_frame, (32, 18)), cv2.COLOR_BGR2HSV)
                hue_diff = float(np.mean(np.abs(
                    hsv1[:, :, 0].astype(np.float32) - hsv2[:, :, 0].astype(np.float32)
                ))) / 180.0
            except Exception:
                hue_diff = 0.0
        else:
            hue_diff = 0.0

        # Kombination: MAD + Block-Max + Hue-Shift
        combined = 0.40 * lum_diff + 0.35 * block_diff + 0.25 * hue_diff
        # * 2.8 skaliert auf typische Szenenübergänge (0.15→0.42 → nach Skalierung ~0.4..>0.9)
        return float(round(max(0.0, min(1.0, combined * 2.8)), 4))
    except Exception:
        return 0.5


def emotion_score(frame: np.ndarray | None, tags: list | None = None) -> float:
    """Berechnet einen Emotions-Score (Valence-Arousal & visuelle Intensität, 0.0 .. 1.0).
    Kombiniert Farbsättigung, Helligkeitskontrast und Sentiment-Tags.
    """
    base_emo = 0.5
    if frame is not None and isinstance(frame, np.ndarray) and frame.size > 0:
        try:
            if cv2 is not None and len(frame.shape) == 3:
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                sat = float(np.mean(hsv[:, :, 1])) / 255.0
                val = float(np.mean(hsv[:, :, 2])) / 255.0
                val_std = float(np.std(hsv[:, :, 2])) / 255.0
                # Hohe Sättigung + starker Kontrast = hohes emotionales Arousal
                vis_emo = 0.4 * sat + 0.3 * val + 0.3 * min(1.0, val_std * 3.0)
            else:
                vis_emo = float(np.std(frame) / 128.0) if frame.size > 0 else 0.5
            base_emo = max(0.0, min(1.0, vis_emo))
        except Exception:
            base_emo = 0.5

    # Sentiment / Tag Alignment
    if tags:
        tag_set = {t.lower() for t in tags}
        high_energy_tags = {
            "energetic", "intense", "aggressive", "party", "action",
            "epic", "hype", "fire", "drop", "spit", "rage", "joy", "pride"
        }
        emotional_tags = {
            "dark", "sad", "romantic", "melancholic", "dreamy", "love", "passion"
        }
        if tag_set & high_energy_tags:
            base_emo = min(1.0, base_emo + 0.25)
        elif tag_set & emotional_tags:
            base_emo = min(1.0, base_emo + 0.15)

    return float(round(base_emo, 4))


def score_clip_pair(
    start_frame: np.ndarray | None,
    end_frame: np.ndarray | None,
    tags: list | None = None,
    w1: float = 0.25,
    w2: float = 0.25,
    w3: float = 0.20,
    w4: float = 0.15,
    w5: float = 0.15,
) -> dict[str, Any]:
    """Dual-Frame Highlight-Scoring nach der Formel:
    H = w_1 * C_start + w_2 * C_end + w_3 * Delta(C_start, C_end) + w_4 * E_start + w_5 * E_end

    Gibt ein detailliertes Analyse-Dictionary zurück:
    - highlight_score: Gesamtwert H (0..1)
    - recommendation: "USE" (H > 0.8), "MAYBE" (0.6..0.8), "SKIP" (H < 0.6)
    - composition: (c_start, c_end)
    - delta: delta_c
    - emotion: (e_start, e_end)
    - emotional_trip: H_emotional = max(E_start, E_end) + |E_start - E_end|
    """
    c_start = composition_score(start_frame)
    c_end = composition_score(end_frame)
    delta_c = visual_difference(start_frame, end_frame)
    e_start = emotion_score(start_frame, tags)
    e_end = emotion_score(end_frame, tags)

    h = (
        w1 * c_start
        + w2 * c_end
        + w3 * delta_c
        + w4 * e_start
        + w5 * e_end
    )
    h = max(0.0, min(1.0, h))

    # Emotionale Reise
    e_diff = abs(e_start - e_end)
    h_emotional = min(1.0, (max(e_start, e_end) + e_diff) * 0.7)
    journey = "rise" if e_end > e_start + 0.1 else ("fall" if e_start > e_end + 0.1 else "stable")

    if h >= 0.80:
        recommendation = "USE"
    elif h >= 0.60:
        recommendation = "MAYBE"
    else:
        recommendation = "SKIP"

    return {
        "highlight_score": round(h, 4),
        "recommendation": recommendation,
        "composition": (round(c_start, 4), round(c_end, 4)),
        "delta": round(delta_c, 4),
        "emotion": (round(e_start, 4), round(e_end, 4)),
        "emotional_trip": {
            "score": round(h_emotional, 4),
            "journey": journey,
            "diff": round(e_diff, 4),
        },
    }


def select_clip_duration(
    highlight_score: float,
    bpm: float = 140.0,
    base_clip_duration: float = 6.0,
) -> dict[str, Any]:
    """Wählt die beat-synchrone Zieldauer (Bars, Sekunden, Beats, Frames)
    für einen Clip basierend auf seinem Highlight-Score.

    Mathematik bei 140 BPM:
      - 1 Beat = 60 / 140 = 0.42857 s
      - 1 Bar  = 4 Beats  = 1.71428 s
      - 6.0 s  = 14 Beats = 3.5 Bars

    Entscheidungsmatrix:
      - H >= 0.90 -> 4 Bars (6.857 s, 16 Beats) + Hold/Freeze ("FULL_HOLD")
      - H >= 0.80 -> 4 Bars (6.857 s, 16 Beats) Beat-genau ("FULL")
      - 0.60 <= H < 0.80 -> 3.5 Bars (6.000 s, 14 Beats) Standard 6s ("CROSSFADE")
      - H < 0.60 -> 3 Bars (5.143 s, 12 Beats) Schnelle Schnitte ("SHORT")
    """
    effective_bpm = max(20.0, float(bpm or 140.0))
    beat_duration = 60.0 / effective_bpm
    bar_duration = 4.0 * beat_duration

    if highlight_score >= 0.90:
        bars = 4.0
        strategy = "FULL_HOLD"
        on_beat = True
        action = "freeze_hold"
    elif highlight_score >= 0.80:
        bars = 4.0
        strategy = "FULL"
        on_beat = True
        action = "full_cut"
    elif highlight_score >= 0.60:
        bars = 3.5
        strategy = "CROSSFADE"
        on_beat = False
        action = "crossfade"
    else:
        bars = 3.0
        strategy = "SHORT"
        on_beat = True
        action = "fast_cut"

    duration_sec = bars * bar_duration
    beats = round(bars * 4.0)
    frames_24fps = round(duration_sec * 24.0)

    return {
        "highlight_score": round(highlight_score, 4),
        "bpm": round(effective_bpm, 2),
        "bars": bars,
        "duration": round(duration_sec, 4),
        "beats": beats,
        "frames_24fps": frames_24fps,
        "strategy": strategy,
        "on_beat": on_beat,
        "action": action,
        "beat_duration_ms": round(beat_duration * 1000.0, 2),
        "bar_duration_ms": round(bar_duration * 1000.0, 2),
    }


def beat_sync_clip(
    clip_start_time: float,
    clip_duration: float = 6.0,
    bpm: float = 140.0,
    fps: int = 24,
) -> dict[str, Any]:
    """Führt ein präzises Beat-Grid-Snapping für Start- und Endframe bei gegebener BPM durch.
    Startframe = round(beat_time * fps)
    Endframe   = round((start_time + duration) * fps)
    """
    effective_bpm = max(20.0, float(bpm or 140.0))
    beat_dur = 60.0 / effective_bpm
    bar_dur = 4.0 * beat_dur

    # Auf nächsten Beat quantisieren
    start_beat_idx = round(clip_start_time / beat_dur)
    snapped_start_time = start_beat_idx * beat_dur

    # Bars quantisieren
    bars = round((clip_duration / bar_dur) * 2.0) / 2.0  # Erlaubt halbe Bars wie 3.5
    corrected_duration = bars * bar_dur

    start_frame = round(snapped_start_time * fps)
    end_frame = round((snapped_start_time + corrected_duration) * fps)
    total_frames = max(1, end_frame - start_frame)

    return {
        "start_time": round(snapped_start_time, 4),
        "duration": round(corrected_duration, 4),
        "bars": bars,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "total_frames": total_frames,
        "beat_index": start_beat_idx,
        "bpm": round(effective_bpm, 2),
        "fps": fps,
    }


def get_clip_highlight_score(meta: dict | None) -> float:
    """Holt den Highlight-Score eines Clips aus seinen Metadaten oder berechnet einen Standardwert."""
    if not meta or not isinstance(meta, dict):
        return 0.5
    if "highlight_score" in meta:
        return float(meta["highlight_score"] or 0.5)
    # Fallback-Berechnung aus motion_score, face_score, information_density
    m = float(meta.get("motion_score", 0.5))
    f = float(meta.get("face_score", 0.0))
    d = float(meta.get("information_density", 0.5))
    score = 0.4 * m + 0.3 * min(1.0, f * 1.5) + 0.3 * d
    return round(max(0.0, min(1.0, score)), 4)
