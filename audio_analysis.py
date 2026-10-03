"""
audio_analysis.py — reines Audio-DSP, offline, kein Cloud-Call.
Angelehnt an BeatSync-Engine Stage 1-3 (Beatgrid / Energie / Sektionen),
aber ohne CUDA-Pflicht: librosa läuft auf CPU (langsamer, aber portabel).

Ergebnis pro Song:
  bpm, beat_times[], energy_curve[](beat-synchron), sections[(start,end,label)]
"""
from dataclasses import dataclass, field

import numpy as np

try:
    import librosa
except ImportError:
    librosa = None

from config import (DJ_SYNC_ACTION_BOOST, DJ_SYNC_ACTION_ENABLED,
                     DJ_SYNC_BACKSPIN_THRESH_HZ, DJ_SYNC_VINYL_STOP_DUR_SEC,
                     DRUM_BURST_RATE_THRESHOLD, DRUM_BURST_WINDOW_SEC,
                     DRUM_MICRO_CUT_ENABLED, DRUM_STEM_SYNC_ENABLED,
                     DRUM_TRANSIENT_SNAP_TOLERANCE_SEC, GENDER_FEMALE_HZ_MIN,
                     GENDER_MALE_HZ_MAX, GENDER_MIN_VOICED_FRAMES,
                     LIBSYNC_CADENCE_RATE_THRESHOLD, LIBSYNC_CADENCE_WINDOW_SEC,
                     LIBSYNC_SPITTING_ENABLED,
                     MAX_SEGMENT_SEC, MC_GENDER_ENABLED, MIN_SEGMENT_SEC,
                     MIXMEISTER_BPM_FALLBACK_ENABLED, MIXMEISTER_TIMEOUT_SEC,
                     REPETITION_ONSET_WINDOW_SEC, REPETITION_RATE_THRESHOLD,
                     SCRATCH_AT_HOOK_ENTRY, SCRATCH_DETECT_MERGE_GAP_SEC,
                     SCRATCH_DETECT_WINDOW_SEC, SCRATCH_MAX_EVENTS_PER_SONG,
                     SCRATCH_MIN_DIRECTION_FLIPS, SCRATCH_ZCR_PERCENTILE,
                     SECTION_SMOOTH_SEC, STRUCTURE_BLOCK_SEC,
                     STRUCTURE_BRIDGE_ENERGY_DROP, STRUCTURE_HOOK_MIN_REPEATS,
                     STRUCTURE_INTRO_MAX_FRAC, STRUCTURE_OUTRO_MAX_FRAC,
                     STRUCTURE_SIM_THRESHOLD)
import stem_separator

try:
    import bpm_analyzer as _bpm_analyzer_mod
except ImportError:
    _bpm_analyzer_mod = None
import cxx_accel
import os as _os
import threading as _threading

# Prozessweiter Cache: verhindert, dass Stem-Separation (stem_separator.py,
# selbst schon disk-gecached, aber trotzdem ein voller librosa.load()+Demucs/
# HPSS-Durchlauf) und die komplette Analyse ein zweites Mal für denselben
# Song laufen, falls analyze_song() innerhalb EINES main.py-Prozesses mehr-
# fach für denselben Song aufgerufen wird.
_ANALYSIS_CACHE: dict = {}
_ANALYSIS_CACHE_LOCK = _threading.Lock()


def _cache_key(mp3_path: str) -> tuple:
    p = _os.path.abspath(mp3_path)
    try:
        st = _os.stat(p)
        return (p, st.st_size, st.st_mtime)
    except OSError:
        return (p, None, None)


def clear_analysis_cache() -> None:
    """Für Tests/Long-Running-Prozesse: leert den Prozess-Cache explizit."""
    with _ANALYSIS_CACHE_LOCK:
        _ANALYSIS_CACHE.clear()


@dataclass
class AudioAnalysis:
    bpm: float
    duration_sec: float
    beat_times: list          # Sekunden, absolut
    energy: list              # 0..1, ein Wert pro Beat
    sections: list = field(default_factory=list)  # [(start_sec, end_sec, "low"/"mid"/"high")]
    downbeats: list = field(default_factory=list)
    loudness_db: float = -60.0
    groove: float = 0.0
    spectral_flux: float = 0.0
    harmonic_change: float = 0.0
    vocal_activity: float = 0.0  # harmonischer Audio-Proxy, keine Vocal-Separation
    drop_times: list = field(default_factory=list)
    music_dna: dict = field(default_factory=dict)
    mc_gender: str = "unknown"          # "male" / "female" / "ambiguous" / "unknown"
    vocal_pitch_hz: float = 0.0         # Median-F0 der stimmhaften Frames (0 = keine Schätzung möglich)
    repetition_windows: list = field(default_factory=list)  # [(start_sec, end_sec)] schnelle Wiederholungs-/Stutter-Zonen
    structure: list = field(default_factory=list)  # [(start_sec, end_sec, "intro"/"verse"/"hook"/"bridge"/"breakdown"/"outro")]
    stems: dict = field(default_factory=dict)  # {"vocals"/"drums"/"bass"/"other": mp3_pfad}, siehe stem_separator.py
    scratch_events: list = field(default_factory=list)  # [{"time","strength","kind":"detected"/"structural"}], siehe _detect_scratch_dj_events
    dj_actions: list = field(default_factory=list)      # [{"time": float, "action": str, "strength": float, "kind": str, "duration": float}]
    drum_accents: list = field(default_factory=list)    # [{"time": float, "strength": float, "kind": "roll"/"burst"/"transient"}]
    drum_onsets: list = field(default_factory=list)     # [float] feine Drum-Transient-Timestamps (Sekunden)
    vocal_onsets: list = field(default_factory=list)    # [float] LibSync MC Spitting / Syllabic Onset Timestamps
    spitting_burst_windows: list = field(default_factory=list)  # [(start_sec, end_sec, syllabic_rate)] Rapid-fire Rap Bursts
    vocal_cadence_hz: float = 0.0                       # Mittlere Silben-/Flow-Frequenz (Hz / Onsets/s)
    felt_bpm: float = 0.0                               # Echtes gefühltes Tempo (z.B. 70 BPM bei Half-Time Trap trotz 140 BPM Grid)
    tempo_feel: str = "half_time"                       # "half_time" (Trap/Drill/Phonk) vs "double_time" (Boom Bap/Jersey)
    time_signature: str = "4/4"                         # "4/4", "3/4", "6/8"
    snare_onsets: list = field(default_factory=list)    # [float] Snare/Clap-Hit Timestamps (Sekunden)
    kick_onsets: list = field(default_factory=list)     # [float] Kick/808-Hit Timestamps (Sekunden)


def _cosine(a: list, b: list) -> float:
    try:
        return cxx_accel.get_cxx_engine().fast_cosine(a, b)
    except Exception:
        a_arr, b_arr = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        denom = (np.linalg.norm(a_arr) * np.linalg.norm(b_arr))
        return float(np.dot(a_arr, b_arr) / denom) if denom > 0 else 0.0



def _estimate_mc_gender(y: np.ndarray, sr: int) -> tuple[str, float]:
    """Schätzt die Stimmlage (MC-Gendern) über die mediane Grundfrequenz (F0)
    der stimmhaften Frames via librosa.pyin (probabilistisches YIN). Rein
    akustisch, keine Sprecher-ID, keine Cloud-API — dient nur dazu, vokal-nahe
    Segmente bevorzugt mit passend getaggten Clips (clip_pool.gender_vector)
    zu matchen (siehe timeline_builder.py::_pick_clip)."""
    if not MC_GENDER_ENABLED or librosa is None or not hasattr(librosa, "pyin"):
        return "unknown", 0.0
    try:
        target_y = y
        max_samples = sr * 45
        if len(y) > max_samples:
            start = max(0, (len(y) - max_samples) // 2)
            target_y = y[start:start + max_samples]
        f0, voiced_flag, _ = librosa.pyin(
            target_y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C6"), sr=sr,
            hop_length=1024,
        )
    except Exception:
        return "unknown", 0.0  # pyin ist rechenintensiv/instabil bei sehr kurzen oder stillen Dateien

    if f0 is None or voiced_flag is None:
        return "unknown", 0.0
    voiced = f0[voiced_flag.astype(bool) & ~np.isnan(f0)]
    if len(voiced) < max(10, GENDER_MIN_VOICED_FRAMES // 2):
        return "unknown", 0.0  # zu wenig stimmhaftes Material für eine verlässliche Schätzung

    median_hz = float(np.median(voiced))
    if median_hz <= 0:
        return "unknown", 0.0
    if median_hz < GENDER_MALE_HZ_MAX:
        return "male", median_hz
    if median_hz > GENDER_FEMALE_HZ_MIN:
        return "female", median_hz
    return "ambiguous", median_hz  # zwischen den Schwellwerten -> keine klare Zuordnung erzwingen


def _detect_repetition_windows(onset_times: np.ndarray, duration_sec: float) -> list:
    """Findet Zonen mit ungewöhnlich hoher Onset-Dichte (schnelle Wiederholungen:
    Hihat-Rolls, Ad-lib-Stakkato, gestotterte Flows) über ein gleitendes
    Zeitfenster. Rein onset-basiert (kein Beat-Grid nötig), damit auch
    Off-Grid-Stutter erfasst werden. Angrenzende Zonen werden zusammengeführt."""
    if len(onset_times) < 3 or duration_sec <= 0:
        return []

    window = REPETITION_ONSET_WINDOW_SEC
    starts = np.searchsorted(onset_times, onset_times)
    ends = np.searchsorted(onset_times, onset_times + window)
    counts = ends - starts
    rates = counts / window
    flagged_indices = np.where(rates >= REPETITION_RATE_THRESHOLD)[0]
    flagged = [(float(onset_times[idx]), float(min(onset_times[idx] + window, duration_sec))) for idx in flagged_indices]

    if not flagged:
        return []

    return _merge_repetition_windows(flagged)


def _merge_repetition_windows(windows: list) -> list:
    """Führt überlappende oder angrenzende Wiederholungszonen zusammen."""
    if not windows:
        return []
    windows = sorted(windows, key=lambda w: w[0])
    merged = [windows[0]]
    for start, end in windows[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 0.10:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _detect_drum_accents_and_rolls(
    drum_onset_times: np.ndarray,
    drum_onset_strength: np.ndarray,
    duration_sec: float,
    sr: int = 22050
) -> tuple[list, list]:
    """Erkennt hochfrequente Drum-Rolls (Hi-Hat 1/16, 1/32, Snare-Fills, Trap-Stutter)
    und markiert transiente Akzent-Hits auf Basis der isolierten Drum-Stem."""
    if len(drum_onset_times) < 2 or duration_sec <= 0:
        return [], []

    cxx_engine = cxx_accel.get_cxx_engine()
    roll_zones = cxx_engine.detect_accent_repetitions(
        drum_onset_times.tolist(),
        window_sec=DRUM_BURST_WINDOW_SEC,
        rate_threshold=DRUM_BURST_RATE_THRESHOLD
    )

    max_strength = float(np.max(drum_onset_strength)) if len(drum_onset_strength) else 1.0
    max_strength = max(1e-6, max_strength)

    drum_accents = []
    hop_length = 512
    for t in drum_onset_times:
        frame_idx = int(librosa.time_to_frames(t, sr=sr, hop_length=hop_length)) if librosa else 0
        frame_idx = min(max(0, frame_idx), len(drum_onset_strength) - 1) if len(drum_onset_strength) else 0
        st = float(drum_onset_strength[frame_idx] / max_strength) if len(drum_onset_strength) else 0.5

        in_roll = any(rz[0] <= t <= rz[1] for rz in roll_zones)
        kind = "roll" if in_roll else ("hit" if st > 0.65 else "transient")

        drum_accents.append({
            "time": round(float(t), 4),
            "strength": round(st, 3),
            "kind": kind
        })

    rep_windows = [(round(rz[0], 3), round(rz[1], 3)) for rz in roll_zones]
    return drum_accents, rep_windows


def _detect_spitting_bursts(
    vocal_onset_times: np.ndarray,
    duration_sec: float,
    window_sec: float = 1.2,
    rate_threshold: float = 3.2
) -> tuple[list, float]:
    """Erkennt Zonen mit schneller Silben- & Rap-Kadenz (MC Rapper Spitting Flow / Bars / Stakkato).
    Gibt [(start, end, rate)] und die mittlere Kadenz-Frequenz zurück."""
    if len(vocal_onset_times) < 3 or duration_sec <= 0:
        return [], 0.0

    mean_cadence = float(len(vocal_onset_times) / duration_sec)

    try:
        cxx_engine = cxx_accel.get_cxx_engine()
        zones = cxx_engine.detect_accent_repetitions(
            vocal_onset_times.tolist(),
            window_sec=window_sec,
            rate_threshold=rate_threshold
        )
        bursts = []
        for start, end in zones:
            cnt = sum(1 for t in vocal_onset_times if start <= t <= end)
            span = max(1e-3, end - start)
            rate = round(cnt / span, 2)
            bursts.append((round(start, 3), round(end, 3), rate))
        return bursts, round(mean_cadence, 2)
    except Exception:
        pass

    starts = np.searchsorted(vocal_onset_times, vocal_onset_times)
    ends = np.searchsorted(vocal_onset_times, vocal_onset_times + window_sec)
    counts = ends - starts
    rates = counts / window_sec
    flagged_indices = np.where(rates >= rate_threshold)[0]
    flagged = [(float(vocal_onset_times[idx]), float(min(vocal_onset_times[idx] + window_sec, duration_sec))) for idx in flagged_indices]
    merged = _merge_repetition_windows(flagged)
    bursts = []
    for start, end in merged:
        cnt = sum(1 for t in vocal_onset_times if start <= t <= end)
        span = max(1e-3, end - start)
        bursts.append((round(start, 3), round(end, 3), round(cnt / span, 2)))
    return bursts, round(mean_cadence, 2)


def _detect_scratch_dj_events(y: np.ndarray, sr: int, onset_times: np.ndarray,
                               duration_sec: float, structure: list) -> list:
    """Erkennt echte DJ-Scratch-/Turntable-Signaturen im Audio UND ergänzt
    strukturelle Kandidaten für Songs ohne hörbares Scratch-Sample.

    Eine echte Scratch-Bewegung (Platte von Hand vor-zurück gerissen) erzeugt
    akustisch ZWEI gleichzeitige Signaturen in einem kurzen Fenster
    (SCRATCH_DETECT_WINDOW_SEC) um einen Onset:
      (a) einen breitbandigen Rausch-/Reibungs-Burst -> hohe Zero-Crossing-Rate
          (Nadel-/Fader-Rauschen hat viel mehr Nulldurchgänge als ein sauberer
          tonaler Hit).
      (b) mind. SCRATCH_MIN_DIRECTION_FLIPS schnelle Richtungswechsel im
          Spectral-Centroid innerhalb des Fensters -> die Tonhöhe springt
          hoch-runter-hoch, weil die Plattengeschwindigkeit hin- und
          herspringt (genau DAS unterscheidet einen Scratch von einem reinen
          lauten Transienten wie einer Snare, der (a) ohne (b) hat).
    Rein onset-getriggert (kein Beat-Grid nötig) -> auch Off-Grid-Scratches
    werden erfasst, analog zu _detect_repetition_windows.

    Ergänzend werden Hook-Einstiege (SCRATCH_AT_HOOK_ENTRY) als
    "structural"-Kandidaten markiert (aber nur, wenn dort noch KEIN echter
    Scratch erkannt wurde) — die meisten Suno-Songs haben kein echtes
    Turntable-Sample, sollen aber trotzdem eine sinnvolle, beat-synchrone
    Cutaway-Stelle für den Scratch-Effekt in timeline_builder.py bekommen."""
    events: list = []
    if librosa is not None and len(y) and len(onset_times):
        win = SCRATCH_DETECT_WINDOW_SEC
        try:
            zcr = librosa.feature.zero_crossing_rate(y, frame_length=1024, hop_length=256)[0]
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=256)[0]
            frame_times = librosa.frames_to_time(np.arange(len(zcr)), sr=sr, hop_length=256)
        except Exception:
            zcr, centroid, frame_times = (np.array([]), np.array([]), np.array([]))

        if len(zcr):
            zcr_threshold = float(np.percentile(zcr, SCRATCH_ZCR_PERCENTILE))
            start_idxs = np.searchsorted(frame_times, onset_times)
            end_idxs = np.searchsorted(frame_times, onset_times + win)

            for i, t in enumerate(onset_times):
                s_i, e_i = int(start_idxs[i]), int(end_idxs[i])
                if s_i >= e_i or s_i >= len(zcr):
                    continue
                win_zcr = zcr[s_i:e_i]
                if float(np.max(win_zcr)) < zcr_threshold:
                    continue  # kein ausreichender Rausch-/Reibungs-Burst -> kein Scratch-Kandidat
                win_centroid = centroid[s_i:e_i]
                if len(win_centroid) < 3:
                    continue
                signs = np.sign(np.diff(win_centroid))
                signs = signs[signs != 0]
                flips = int(np.sum(np.abs(np.diff(signs)) > 0)) if len(signs) > 1 else 0
                if flips < SCRATCH_MIN_DIRECTION_FLIPS:
                    continue  # Burst ohne Vor-Zurück-Bewegung -> vermutlich normaler Transient
                strength = float(np.clip((float(np.max(win_zcr)) / (zcr_threshold + 1e-6)) - 0.5, 0.3, 1.0))
                events.append({"time": float(t), "strength": strength, "kind": "detected"})

    # Angrenzende Treffer (mehrere Onsets im selben echten Scratch) zusammenführen.
    events.sort(key=lambda ev: ev["time"])
    merged: list = []
    for ev in events:
        if merged and ev["time"] - merged[-1]["time"] <= SCRATCH_DETECT_MERGE_GAP_SEC:
            merged[-1]["strength"] = max(merged[-1]["strength"], ev["strength"])
        else:
            merged.append(dict(ev))

    if SCRATCH_AT_HOOK_ENTRY and structure:
        for idx in range(1, len(structure)):
            start, _end, label = structure[idx]
            if label == "hook" and structure[idx - 1][2] != "hook":
                already_covered = any(
                    abs(start - ev["time"]) < SCRATCH_DETECT_MERGE_GAP_SEC for ev in merged
                )
                if not already_covered:
                    merged.append({"time": float(start), "strength": 0.5, "kind": "structural"})

    merged.sort(key=lambda ev: ev["time"])
    return merged[:SCRATCH_MAX_EVENTS_PER_SONG]


def _detect_dj_sync_actions(y: np.ndarray, sr: int, onset_times: np.ndarray,
                            duration_sec: float, structure: list,
                            drop_times: list, drum_accents: list,
                            scratch_events: list) -> list[dict]:
    """Erkennt vollwertige DJ-Sync-Actions im Audio:
      - 'scratch': Rausch-/Reibungs-Bursts mit schnellen Centroid-Flips (Turntablism / Baby Scratch / Chirp)
      - 'backspin': Schnelle hochfrequente Rewind-Gesten an Struktur- und Drop-Übergängen
      - 'vinyl_brake': Kontinuierlicher Pitch-Abfall / Tape-Stop vor Breaks
      - 'beat_juggle': Hochfrequente Snare-/Drum-Stakkato-Pattern
      - 'drop_impact': Massiver Energie-Einschlag direkt auf Drop-Zeiten
    """
    actions: list[dict] = []

    # 1. Scratch Events integrieren
    for sc in scratch_events:
        actions.append({
            "time": float(sc.get("time", 0.0)),
            "action": "scratch",
            "strength": float(sc.get("strength", 0.5)),
            "kind": sc.get("kind", "detected"),
            "duration": 0.18,
        })

    # 2. Drop Impacts
    for dt in drop_times:
        actions.append({
            "time": float(dt),
            "action": "drop_impact",
            "strength": 0.95,
            "kind": "detected",
            "duration": 0.35,
        })

    # 3. Drum Rolls / Beat Juggling aus drum_accents
    for da in drum_accents:
        if da.get("kind") in ("roll", "burst") and da.get("strength", 0.0) >= 0.6:
            actions.append({
                "time": float(da["time"]),
                "action": "beat_juggle",
                "strength": float(da["strength"]),
                "kind": "detected",
                "duration": float(da.get("duration", 0.25)),
            })

    # 4. Backspin / Rewind & Vinyl Brake Erkennung
    if librosa is not None and len(y) > sr * 2:
        try:
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=512)[0]
            times = librosa.frames_to_time(np.arange(len(centroid)), sr=sr, hop_length=512)
            # Struktur-Wechsel vor Hooks oder Drops untersuchen
            trans_times = [s for s, _, l in structure if l in ("hook", "breakdown")] + list(drop_times)
            for tt in trans_times:
                idx = np.searchsorted(times, tt)
                win_len = int(sr * 0.45 / 512)
                if idx >= win_len:
                    prev_c = centroid[idx - win_len:idx]
                    if len(prev_c) >= 3:
                        # Starker Pitch-Anstieg vor Drop -> Backspin / Riser
                        if np.max(prev_c) > DJ_SYNC_BACKSPIN_THRESH_HZ and np.mean(np.diff(prev_c)) > 50.0:
                            actions.append({
                                "time": max(0.0, float(tt - 0.25)),
                                "action": "backspin",
                                "strength": 0.85,
                                "kind": "detected",
                                "duration": 0.30,
                            })
                        # Kontinuierlicher Pitch-Abfall -> Vinyl Brake / Tape Stop
                        elif np.mean(np.diff(prev_c)) < -80.0 and prev_c[-1] < prev_c[0] * 0.6:
                            actions.append({
                                "time": max(0.0, float(tt - 0.35)),
                                "action": "vinyl_brake",
                                "strength": 0.80,
                                "kind": "detected",
                                "duration": 0.40,
                            })
        except Exception:
            pass

    # Sortieren & Deduplizieren
    actions.sort(key=lambda a: a["time"])
    merged_actions: list[dict] = []
    for a in actions:
        if merged_actions and abs(a["time"] - merged_actions[-1]["time"]) < 0.15:
            if a["strength"] > merged_actions[-1]["strength"]:
                merged_actions[-1] = a
        else:
            merged_actions.append(a)

    return merged_actions


def _detect_song_structure(y: np.ndarray, sr: int, duration_sec: float,
                            beat_times: list, energy_per_beat: list) -> list:
    """Echte Song-Struktur-Erkennung (Intro/Verse/Hook/Bridge/Breakdown/Outro)
    via blockweisem MFCC-Similarity-Clustering — ersetzt/ergänzt die reine
    low/mid/high-Energie-Sektionierung (audio.sections bleibt unverändert für
    Rückwärtskompatibilität, siehe config.py-Kommentar).

    Ablauf:
      1. Song in STRUCTURE_BLOCK_SEC-Blöcke teilen, pro Block ein MFCC-Mittel-
         wertvektor (Klangfarben-Fingerabdruck).
      2. Blöcke greedy zu Clustern gruppieren (Cosine-Similarity zum jeweils
         ERSTEN Block eines Clusters >= STRUCTURE_SIM_THRESHOLD = "gleicher
         Part", z.B. zwei Hook-Wiederholungen klingen ähnlich).
      3. Cluster mit >= STRUCTURE_HOOK_MIN_REPEATS Wiederholungen -> "hook".
      4. Erster/letzter Block (innerhalb der Intro/Outro-Grenzfraktion UND
         leiser als der Song-Schnitt UND kein Hook) -> "intro"/"outro".
      5. Singuläre (nicht wiederholte), spürbar leisere Blöcke -> "bridge"
         (moderater Abfall) bzw. "breakdown" (starker Abfall, fast Stille).
      6. Alles andere -> "verse".
      7. Angrenzende Blöcke gleichen Labels werden zu Sektionen gemergt.

    Fällt auf eine einzige "verse"-Sektion zurück, wenn der Song zu kurz für
    ein Blockraster ist oder MFCC nicht berechenbar ist (defensiv, damit ein
    DSP-Ausreißer nie den gesamten Analyse-Lauf killt)."""
    if duration_sec <= 0:
        return [(0.0, max(duration_sec, 0.0), "verse")]
    if duration_sec < STRUCTURE_BLOCK_SEC * 2:
        return [(0.0, duration_sec, "verse")]

    try:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    except Exception:
        return [(0.0, duration_sec, "verse")]
    if mfcc.shape[1] < 2:
        return [(0.0, duration_sec, "verse")]
    mfcc_times = librosa.frames_to_time(np.arange(mfcc.shape[1]), sr=sr)

    block_bounds = np.arange(0.0, duration_sec, STRUCTURE_BLOCK_SEC)
    if len(block_bounds) == 0 or block_bounds[-1] < duration_sec:
        block_bounds = np.append(block_bounds, duration_sec)

    start_idxs = np.searchsorted(mfcc_times, block_bounds[:-1])
    end_idxs = np.searchsorted(mfcc_times, block_bounds[1:])
    beat_bounds = np.searchsorted(beat_times, block_bounds)

    blocks = []  # [{"start","end","vec","energy"}]
    for i in range(len(block_bounds) - 1):
        b_start, b_end = float(block_bounds[i]), float(block_bounds[i + 1])
        s_i, e_i = int(start_idxs[i]), int(end_idxs[i])
        vec = np.mean(mfcc[:, s_i:e_i], axis=1) if e_i > s_i else np.zeros(mfcc.shape[0])
        b_s, b_e = int(beat_bounds[i]), int(beat_bounds[i + 1])
        e_vals = energy_per_beat[b_s:b_e]
        blocks.append({"start": b_start, "end": b_end, "vec": vec,
                        "energy": float(np.mean(e_vals)) if len(e_vals) else 0.0})
    if len(blocks) < 2:
        return [(0.0, duration_sec, "verse")]

    # Greedy Clustering (Repräsentant = erster Block je Cluster -> stabil,
    # kein Centroid-Drift über viele Wiederholungen hinweg).
    clusters: list = []  # [{"rep": vec, "block_indices": [...]}]
    cluster_of_block: dict = {}
    for idx, block in enumerate(blocks):
        best_idx, best_sim = -1, -1.0
        for c_idx, cluster in enumerate(clusters):
            sim = _cosine(block["vec"].tolist(), cluster["rep"].tolist())
            if sim > best_sim:
                best_sim, best_idx = sim, c_idx
        if best_idx >= 0 and best_sim >= STRUCTURE_SIM_THRESHOLD:
            clusters[best_idx]["block_indices"].append(idx)
            cluster_of_block[idx] = best_idx
        else:
            clusters.append({"rep": block["vec"], "block_indices": [idx]})
            cluster_of_block[idx] = len(clusters) - 1
    repeat_counts = {c_idx: len(c["block_indices"]) for c_idx, c in enumerate(clusters)}

    energy_mean = float(np.mean([b["energy"] for b in blocks])) if blocks else 0.0
    n_blocks = len(blocks)
    intro_block_limit = max(1, int(round(n_blocks * STRUCTURE_INTRO_MAX_FRAC)))
    outro_block_limit = max(1, int(round(n_blocks * STRUCTURE_OUTRO_MAX_FRAC)))

    labels = []
    for idx, block in enumerate(blocks):
        is_hook_cluster = repeat_counts[cluster_of_block[idx]] >= STRUCTURE_HOOK_MIN_REPEATS
        if idx < intro_block_limit and block["energy"] <= energy_mean and not is_hook_cluster:
            labels.append("intro")
        elif idx >= n_blocks - outro_block_limit and block["energy"] <= energy_mean and not is_hook_cluster:
            labels.append("outro")
        elif is_hook_cluster:
            labels.append("hook")
        elif energy_mean > 0 and block["energy"] <= energy_mean * (1.0 - STRUCTURE_BRIDGE_ENERGY_DROP):
            labels.append("breakdown" if block["energy"] <= energy_mean * 0.35 else "bridge")
        else:
            labels.append("verse")

    structure = []
    cur_start, cur_label = blocks[0]["start"], labels[0]
    for idx in range(1, len(blocks)):
        if labels[idx] != cur_label:
            structure.append((cur_start, blocks[idx]["start"], cur_label))
            cur_start, cur_label = blocks[idx]["start"], labels[idx]
    structure.append((cur_start, duration_sec, cur_label))
    return structure


def _detect_felt_tempo_and_rhythm_feel(
    y: np.ndarray,
    sr: int,
    beat_times: list,
    bpm: float,
    drum_onset_times: list | np.ndarray
) -> tuple[float, str, str, list, list]:
    """Erkennt anhand der Snare/Clap- und Kick-Positionen (sowie der Phrasenlänge),
    ob ein nomineller 140-BPM-Track echt als 70 BPM (Half-Time, Trap/Drill) oder
    als 140 BPM (Double-Time, Boom Bap/Jersey) gefühlt wird.

    Regel:
      - Snare auf Beat 3 (in 4/4 bei 140 BPM Grid) -> 70 BPM gefühlt (Half-Time)
      - Snare auf Beat 2 und 4 -> 140 BPM gefühlt (Double-Time / Straight)
    """
    if bpm <= 0 or len(beat_times) < 4 or librosa is None or len(y) == 0 or float(np.max(np.abs(y))) < 1e-4:
        felt_bpm = round(bpm / 2.0, 1) if bpm >= 115 else round(bpm, 1)
        return felt_bpm, "half_time" if bpm >= 115 else "double_time", "4/4", [], []

    try:
        hop = 512
        spec = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)

        snare_band_mask = (freqs >= 1500) & (freqs <= 5500)
        kick_band_mask = (freqs >= 35) & (freqs <= 140)

        snare_env = np.mean(spec[snare_band_mask, :], axis=0) if np.any(snare_band_mask) else np.zeros(spec.shape[1])
        kick_env = np.mean(spec[kick_band_mask, :], axis=0) if np.any(kick_band_mask) else np.zeros(spec.shape[1])

        snare_peaks = librosa.util.peak_pick(snare_env, pre_max=3, post_max=3, pre_avg=3, post_avg=3, delta=0.5, wait=5)
        kick_peaks = librosa.util.peak_pick(kick_env, pre_max=3, post_max=3, pre_avg=3, post_avg=3, delta=0.5, wait=5)

        snare_times = librosa.frames_to_time(snare_peaks, sr=sr, hop_length=hop).tolist()
        kick_times = librosa.frames_to_time(kick_peaks, sr=sr, hop_length=hop).tolist()

        beat_arr = np.asarray(beat_times)
        tolerance = (60.0 / max(30.0, bpm)) * 0.28

        beat_hits = {0: 0, 1: 0, 2: 0, 3: 0}
        for st in snare_times:
            diffs = np.abs(beat_arr - st)
            min_idx = int(np.argmin(diffs))
            if diffs[min_idx] <= tolerance:
                beat_pos = min_idx % 4
                beat_hits[beat_pos] += 1

        snare_on_beat_3 = beat_hits[2]
        snare_on_beat_2_4 = beat_hits[1] + beat_hits[3]

        if bpm >= 110:
            if snare_on_beat_3 >= snare_on_beat_2_4 * 0.85:
                felt_bpm = round(bpm / 2.0, 1)
                tempo_feel = "half_time"
            else:
                felt_bpm = round(bpm, 1)
                tempo_feel = "double_time"
        else:
            felt_bpm = round(bpm, 1)
            tempo_feel = "double_time" if bpm >= 85 else "half_time"

        return felt_bpm, tempo_feel, "4/4", [round(t, 3) for t in snare_times], [round(t, 3) for t in kick_times]
    except Exception:
        felt_bpm = round(bpm / 2.0, 1) if bpm >= 120 else round(bpm, 1)
        tempo_feel = "half_time" if bpm >= 120 else "double_time"
        return felt_bpm, tempo_feel, "4/4", [], []


def load_audio_file(audio_path: str | _os.PathLike, sr: int = 22050, mono: bool = True) -> tuple[np.ndarray, int]:
    """Lädt eine Audiodatei (.mp3, .m4a, .wav etc.) direkt, schnell und ohne Warnungen.
    
    Reihenfolge:
      1. soundfile.read (schnell für Standard WAV / FLAC / MP3)
      2. FFmpeg Direct Raw PCM float32 Stream (100% zuverlässig für alle Container wie .m4a/AAC/MP3)
      3. librosa.load Fallback mit unterdrückten Legacy-Warnungen
    """
    import subprocess
    import warnings
    from pathlib import Path

    path_obj = Path(audio_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Audio-Datei existiert nicht: {audio_path}")

    ext = path_obj.suffix.lower()
    if ext not in (".m4a", ".aac", ".mp4"):
        try:
            import soundfile as sf
            data, native_sr = sf.read(str(path_obj), dtype="float32", always_2d=True)
            if mono and data.ndim > 1:
                data = np.mean(data, axis=1)
            else:
                data = data[:, 0] if data.ndim > 1 else data
            if native_sr != sr and librosa is not None:
                data = librosa.resample(data, orig_sr=native_sr, target_sr=sr)
            return data, sr
        except Exception:
            pass

    # 2. FFmpeg Direct Raw PCM Stream Decoding
    try:
        cmd = [
            "ffmpeg", "-v", "error", "-i", str(path_obj),
            "-f", "f32le", "-ac", "1" if mono else "2",
            "-ar", str(sr), "pipe:1"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if proc.stdout:
            data = np.frombuffer(proc.stdout, dtype=np.float32)
            if len(data) > 0:
                return data, sr
    except Exception:
        pass

    # 3. Librosa Fallback mit Warnungsunterdrückung
    if librosa is not None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            warnings.simplefilter("ignore", category=FutureWarning)
            y, out_sr = librosa.load(str(path_obj), sr=sr, mono=mono)
            return y, out_sr

    raise RuntimeError(f"Konnte Audio-Datei nicht decodieren: {audio_path}")


def _analyze_song_uncached(mp3_path: str) -> AudioAnalysis:
    if librosa is None:
        raise RuntimeError(
            "librosa ist nicht installiert. `pip install librosa` (siehe requirements.txt)."
        )

    try:
        y, sr = load_audio_file(mp3_path, sr=22050, mono=True)
    except Exception as error:
        raise ValueError(f"Audio-Datei konnte nicht gelesen werden: {mp3_path}") from error
    duration_sec = librosa.get_duration(y=y, sr=sr)
    if not len(y) or duration_sec <= 0:
        raise ValueError(f"Audio-Datei ist leer: {mp3_path}")

    # Stem-Separation (Drums/Vocals/Bass/Other) VOR dem Beat-Tracking: die
    # Drum-Stem liefert ein deutlich saubereres Beatgrid und messerscharfe Transienten
    # als der volle Mix, weil Vocals/Melodie die Drums nicht mehr überlagern.
    try:
        stems = stem_separator.separate_stems(mp3_path, y=y, sr=sr)
    except Exception:
        stems = {}
    beat_source_y = y
    drum_y = None
    if stems.get("drums"):
        try:
            drum_loaded, _drum_sr = load_audio_file(stems["drums"], sr=sr, mono=True)
            if len(drum_loaded):
                drum_y = drum_loaded
                beat_source_y = drum_loaded
        except Exception:
            pass

    # HPSS-Fallback für percussive Komponente, falls keine isolierte Drum-Stem vorliegt
    if drum_y is None and librosa is not None:
        try:
            _, drum_y = librosa.effects.hpss(y)
            if len(drum_y) and float(np.max(np.abs(drum_y))) > 1e-4:
                beat_source_y = drum_y
            else:
                drum_y = y
        except Exception:
            drum_y = y

    # Drum-Transienten & Onset-Envelope
    drum_onset_strength = librosa.onset.onset_strength(y=drum_y, sr=sr)
    drum_onset_frames = librosa.onset.onset_detect(
        onset_envelope=drum_onset_strength, sr=sr, backtrack=True
    )
    drum_onset_times = librosa.frames_to_time(drum_onset_frames, sr=sr)

    # Stage 1 — Beatgrid mit Drum-Transient Snapping
    tempo, beat_frames = librosa.beat.beat_track(y=beat_source_y, sr=sr, units="frames")
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    bpm_values = np.asarray(tempo).reshape(-1)
    bpm = float(bpm_values[0]) if len(bpm_values) else 0.0
    bpm = max(0.0, bpm)

    # ── MixMeister BPM Analyzer Fallback ─────────────────────────────────────
    # Greift wenn librosa kein valides BPM ermitteln konnte (bpm=0) oder ein
    # verdächtiges Ergebnis liefert (<= 20 BPM = definitiv falsch erkannt).
    # MixMeister ist besonders präzise bei stark komprimierten EDM/Hip-Hop-Tracks
    # ohne klares Onset-Profil (z.B. Trap-Subs, Heavy-Reverb Vocals).
    if (MIXMEISTER_BPM_FALLBACK_ENABLED
            and bpm <= 20.0
            and _bpm_analyzer_mod is not None
            and _bpm_analyzer_mod.is_available()):
        mm_bpm = _bpm_analyzer_mod.detect_bpm(mp3_path, timeout=MIXMEISTER_TIMEOUT_SEC)
        if mm_bpm > 0:
            bpm = mm_bpm
            print(f"[audio] MixMeister BPM Fallback: {bpm:.1f} BPM für {mp3_path}", flush=True)

    if len(beat_times) < 2:
        # Fallback: synthetisches Grid falls Beat-Tracking versagt (z.B. Ambient ohne klaren Beat)
        step = 60.0 / max(bpm, 60.0)
        beat_times = list(np.arange(0, duration_sec, step))

    # Sub-frame Transient Alignment: Schnitte exakt auf den Attack-Peak der Kick/Snare einrasten
    cxx_engine = cxx_accel.get_cxx_engine()
    if DRUM_STEM_SYNC_ENABLED and len(drum_onset_times) > 0:
        beat_times = cxx_engine.snap_transients_batch(
            beat_times, drum_onset_times.tolist(), tolerance_sec=DRUM_TRANSIENT_SNAP_TOLERANCE_SEC
        )

    # Stage 2 — Energie pro Beat (RMS, beat-synchron gemittelt, vektorisiert)
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    beat_indices = np.searchsorted(rms_times, beat_times)
    beat_indices = np.append(beat_indices, len(rms))
    energy_per_beat = [
        float(np.mean(rms[beat_indices[i]:beat_indices[i + 1]])) if beat_indices[i + 1] > beat_indices[i] else 0.0
        for i in range(len(beat_times))
    ]
    if max(energy_per_beat, default=0) > 0:
        peak = max(energy_per_beat)
        energy_per_beat = [e / peak for e in energy_per_beat]

    # Stage 3 — grobe Songsektionen über gleitenden Energie-Mittelwert
    sections = _segment_sections(beat_times, energy_per_beat, duration_sec)
    downbeats = beat_times[::4]
    rms_value = float(np.sqrt(np.mean(np.square(y)))) if len(y) else 0.0
    loudness_db = float(20.0 * np.log10(max(rms_value, 1e-10)))

    onset_strength = librosa.onset.onset_strength(y=y, sr=sr)
    onset_mean = float(np.mean(onset_strength)) if len(onset_strength) else 0.0
    onset_std = float(np.std(onset_strength)) if len(onset_strength) else 0.0
    groove = float(min(1.0, (onset_std / (onset_mean + 1e-6)) / 3.0))
    onset_delta = np.maximum(0.0, np.diff(onset_strength))
    spectral_flux = float(np.mean(onset_delta)) if len(onset_delta) else 0.0
    spectral_flux = float(min(1.0, spectral_flux / (onset_mean + 1e-6)))

    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_strength, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # Schnelle Wiederholungen & Akzent-Bursts (Drums + Mix gemergt)
    drum_accents, drum_rep_windows = _detect_drum_accents_and_rolls(
        drum_onset_times, drum_onset_strength, duration_sec, sr=sr
    )
    mix_rep_windows = _detect_repetition_windows(onset_times, duration_sec)
    repetition_windows = _merge_repetition_windows(mix_rep_windows + drum_rep_windows)

    structure = _detect_song_structure(y, sr, duration_sec, beat_times, energy_per_beat)

    # DJ-Scratch-Erkennung braucht audio.structure (für die Hook-Einstiegs-
    # Kandidaten, siehe SCRATCH_AT_HOOK_ENTRY) -> erst NACH _detect_song_structure
    # aufrufen, sonst wären dort noch keine Hook-Blöcke bekannt.
    scratch_events = _detect_scratch_dj_events(y, sr, onset_times, duration_sec, structure)

    # MC-Gendern-Optimierung: F0-Schätzung auf der isolierten Vocal-Stem statt
    # dem vollen Mix, sofern vorhanden (siehe stem_separator.py oben). Bass/
    # Drums/Instrumental im vollen Mix verschieben pyin's F0-Tracking sonst
    # spürbar (v.a. bei bass-lastigen Trap-/Phonk-Beats) -> Vocal-Stem liefert
    # ein deutlich saubereres, isoliertes Stimmsignal für die Median-F0-
    # Schätzung. Fällt automatisch auf den vollen Mix zurück, wenn keine
    # MC-Gendern-Optimierung & LibSync Spitting Vocal Onsets
    gender_source_y = y
    vocal_stem_y = None
    if stems.get("vocals"):
        try:
            vocal_y, _vocal_sr = load_audio_file(stems["vocals"], sr=sr, mono=True)
            if len(vocal_y):
                gender_source_y = vocal_y
                vocal_stem_y = vocal_y
        except Exception:
            pass
    mc_gender, vocal_pitch_hz = _estimate_mc_gender(gender_source_y, sr)

    # LibSync MC Spitting & Vocal Cadence Analyse
    if vocal_stem_y is None and librosa is not None:
        try:
            vocal_stem_y = librosa.effects.harmonic(y)
        except Exception:
            vocal_stem_y = y

    vocal_onset_times = np.array([])
    if librosa is not None and vocal_stem_y is not None and len(vocal_stem_y):
        try:
            vocal_onset_strength = librosa.onset.onset_strength(y=vocal_stem_y, sr=sr)
            vocal_onset_frames = librosa.onset.onset_detect(onset_envelope=vocal_onset_strength, sr=sr, backtrack=True)
            vocal_onset_times = librosa.frames_to_time(vocal_onset_frames, sr=sr)
        except Exception:
            vocal_onset_times = np.array([])

    spitting_burst_windows, vocal_cadence_hz = _detect_spitting_bursts(
        vocal_onset_times, duration_sec,
        window_sec=LIBSYNC_CADENCE_WINDOW_SEC,
        rate_threshold=LIBSYNC_CADENCE_RATE_THRESHOLD
    )

    harmonic = librosa.effects.harmonic(y)
    harmonic_rms = float(np.sqrt(np.mean(np.square(harmonic)))) if len(harmonic) else 0.0
    vocal_activity = float(min(1.0, harmonic_rms / (rms_value + 1e-6)))

    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    except Exception:
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    harmonic_change = float(np.mean(np.abs(np.diff(chroma, axis=1)))) if chroma.shape[1] > 1 else 0.0
    harmonic_change = float(min(1.0, harmonic_change))

    drop_times = []
    energy_deltas = np.maximum(0.0, np.diff(energy_per_beat))
    drop_threshold = max(0.35, float(np.percentile(energy_deltas, 80))) if len(energy_deltas) else 0.35
    for index in range(1, len(energy_per_beat)):
        previous = energy_per_beat[index - 1]
        current = energy_per_beat[index]
        if previous < 0.35 and current - previous >= drop_threshold:
            drop_times.append(float(beat_times[index]))

    energy_mean = float(np.mean(energy_per_beat)) if energy_per_beat else 0.0

    # DJ Sync Actions Analyse (Scratches, Backspins, Vinyl Brake, Drops, Beat Juggling)
    dj_actions = _detect_dj_sync_actions(
        y, sr, onset_times, duration_sec, structure,
        drop_times, drum_accents, scratch_events
    )

    # Felt-Tempo & Snare/Kick Rhythmus-Erkennung (70 BPM Half-Time vs 140 BPM Double-Time)
    felt_bpm, tempo_feel, time_signature, snare_onsets, kick_onsets = _detect_felt_tempo_and_rhythm_feel(
        y, sr, beat_times, bpm, drum_onset_times
    )

    music_dna = {
        "bpm": bpm,
        "felt_bpm": felt_bpm,
        "tempo_feel": tempo_feel,
        "time_signature": time_signature,
        "duration_sec": duration_sec,
        "downbeats": downbeats,
        "energy_curve": energy_per_beat,
        "energy_mean": energy_mean,
        "energy_peak": float(max(energy_per_beat, default=0.0)),
        "energy_variance": float(np.var(energy_per_beat)) if energy_per_beat else 0.0,
        "loudness_db": loudness_db,
        "groove": groove,
        "spectral_flux": spectral_flux,
        "harmonic_change": harmonic_change,
        "vocal_activity": vocal_activity,
        "drop_times": drop_times,
        "sections": sections,
        "mc_gender": mc_gender,
        "vocal_pitch_hz": vocal_pitch_hz,
        "repetition_windows": repetition_windows,
        "stems": sorted(stems.keys()),
        "structure": structure,
        "scratch_events": scratch_events,
        "dj_actions": dj_actions,
        "drum_accents": drum_accents,
        "drum_onsets": drum_onset_times.tolist(),
        "vocal_onsets": vocal_onset_times.tolist() if isinstance(vocal_onset_times, np.ndarray) else list(vocal_onset_times),
        "spitting_burst_windows": spitting_burst_windows,
        "vocal_cadence_hz": vocal_cadence_hz,
        "snare_onsets": snare_onsets,
        "kick_onsets": kick_onsets,
    }

    return AudioAnalysis(
        bpm=bpm,
        duration_sec=duration_sec,
        beat_times=beat_times,
        energy=energy_per_beat,
        sections=sections,
        downbeats=downbeats,
        loudness_db=loudness_db,
        groove=groove,
        spectral_flux=spectral_flux,
        harmonic_change=harmonic_change,
        vocal_activity=vocal_activity,
        drop_times=drop_times,
        music_dna=music_dna,
        mc_gender=mc_gender,
        vocal_pitch_hz=vocal_pitch_hz,
        repetition_windows=repetition_windows,
        structure=structure,
        stems=stems,
        scratch_events=scratch_events,
        dj_actions=dj_actions,
        drum_accents=drum_accents,
        drum_onsets=drum_onset_times.tolist(),
        vocal_onsets=vocal_onset_times.tolist() if isinstance(vocal_onset_times, np.ndarray) else list(vocal_onset_times),
        spitting_burst_windows=spitting_burst_windows,
        vocal_cadence_hz=vocal_cadence_hz,
        felt_bpm=felt_bpm,
        tempo_feel=tempo_feel,
        time_signature=time_signature,
        snare_onsets=snare_onsets,
        kick_onsets=kick_onsets,
    )


def analyze_song(mp3_path: str) -> AudioAnalysis:
    """Öffentlicher Einstiegspunkt mit thread-sicherem Prozess-Cache."""
    key = _cache_key(mp3_path)
    with _ANALYSIS_CACHE_LOCK:
        cached = _ANALYSIS_CACHE.get(key)
        if cached is not None:
            return cached
    result = _analyze_song_uncached(mp3_path)
    with _ANALYSIS_CACHE_LOCK:
        _ANALYSIS_CACHE[key] = result
    return result


def _segment_sections(beat_times, energy, duration_sec) -> list:
    """Teilt den Song in Blöcke von ~SECTION_SMOOTH_SEC und klassifiziert
    jeden Block grob als low/mid/high Energie -> steuert später die Cut-Dichte
    und die bevorzugten Clip-Tags (z.B. 'calm' vs 'action')."""
    if not beat_times:
        return [(0.0, duration_sec, "mid")]

    sections = []
    block_start = 0.0
    block_energies = []
    for t, e in zip(beat_times, energy):
        block_energies.append(e)
        if t - block_start >= SECTION_SMOOTH_SEC:
            label = _energy_label(np.mean(block_energies) if block_energies else 0.0)
            sections.append((block_start, t, label))
            block_start = t
            block_energies = []
    if block_start < duration_sec:
        label = _energy_label(np.mean(block_energies) if block_energies else 0.0)
        sections.append((block_start, duration_sec, label))
    return sections


def _energy_label(e: float) -> str:
    if e < 0.33:
        return "low"
    if e < 0.66:
        return "mid"
    return "high"


def energy_to_segment_length(e: float) -> float:
    """Energie-Wave-Cut-Density (wie BeatSync-Engine): hohe Energie -> kurze Cuts,
    ruhige Passagen -> längere Cuts."""
    e = max(0.0, min(1.0, e))
    return MAX_SEGMENT_SEC - e * (MAX_SEGMENT_SEC - MIN_SEGMENT_SEC)
