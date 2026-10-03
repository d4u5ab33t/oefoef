"""
timeline_builder.py — Kernstück: baut aus (Song-Analyse + Song-Tag-Vektor +
Clip-Globe) eine frame-genaue Schnittliste.

Scoring pro Kandidat-Clip für ein Segment:
    score = SEMANTIC_WEIGHT * cosine(song_vec, clip_vec)
          + (1-SEMANTIC_WEIGHT) * energy_match(section_label, clip.motion_score)
          + FACE_BOOST_VOCAL   (falls Sektion vokal/emotional UND clip.face_score hoch)

Anti-Repeat (PARTIELL): NO_REPEAT_WINDOW (harte Sperre für die zuletzt genutzten
ZEITBEREICHE der letzten N Clip-Ausschnitte in diesem Render) +
PARTIAL_REPEAT_COOLDOWN_SEC (zeitbasierte Sperre über beat_sync.db hinweg,
rendersübergreifend) + MAX_CLIP_USES_TOTAL (Obergrenze über die gesamte
Beat-Sync-Historie, damit ein Clip nicht in jedem Video wieder auftaucht).

WICHTIG: gesperrt wird nur der tatsächlich genutzte Ausschnitt eines Clips
(+ Sicherheitsabstand PARTIAL_REPEAT_PADDING_SEC), NICHT der komplette Clip.
Ein 40s-Clip bleibt für andere Sekundenbereiche weiterhin wählbar, auch wenn
eine seiner Sekunden gerade erst benutzt wurde.
"""
import hashlib
import math
import random
from dataclasses import dataclass

import numpy as np

from audio_analysis import AudioAnalysis, energy_to_segment_length
from config import (BREATH_ENERGY_THRESHOLD, BREATH_EXTEND_FACTOR,
                     BREATH_SEGMENT_MAX_SEC, CLIP_CLUSTER_SIM_THRESHOLD,
                     DIVERSITY_DOMAIN_SWITCH_BONUS,
                     DIVERSITY_EXPLORATION_BONUS, DIVERSITY_TEMPERATURE,
                     DIVERSITY_USAGE_PENALTY_WEIGHT,
                     DJ_SYNC_ACTION_BOOST, DJ_SYNC_ACTION_ENABLED,
                     DRUM_BURST_RATE_THRESHOLD,
                     DRUM_MICRO_CUT_ENABLED, DRUM_MICRO_CUT_MAX_SLICES,
                     DRUM_MICRO_CUT_MIN_BURST_DUR, DRUM_ROLL_SPEED_RAMP_BOOST,
                     DRUM_STEM_SYNC_ENABLED, DRUM_TRANSIENT_SNAP_TOLERANCE_SEC,
                     DUAL_FRAME_HIGHLIGHT_ENABLED, DUAL_FRAME_THRESHOLD_MAYBE,
                     FACE_BOOST_VOCAL, GENDER_BOOST_VOCAL,
                     LIBSYNC_CADENCE_ZOOM_PULSE, LIBSYNC_PERFORMANCE_BOOST,
                     LIBSYNC_SPITTING_ENABLED, MAX_CLIP_USES_TOTAL,
                     MAX_SEGMENT_SEC, MIN_SEGMENT_SEC,
                     MOTION_FLOW_CONTINUITY_BONUS, MOTION_FLOW_CONTINUITY_ENABLED,
                     MOTION_FLOW_DIRECTION_THRESHOLD, MOTION_FLOW_FAST_CUT_SEC,
                     MOTION_FLOW_MAX_STREAK, MOTION_FLOW_SLOW_CUT_SEC,
                     NO_REPEAT_WINDOW,
                     PARTIAL_REPEAT_COOLDOWN_SEC, PARTIAL_REPEAT_PADDING_SEC,
                     SCRATCH_ENABLED, SCRATCH_PROBABILITY,
                     SEMANTIC_WEIGHT, SESSION_COOLDOWN_HOURS,
                     SESSION_MAX_GLOBAL_USES, SESSION_POOL_LOCK_ENABLED,
                     SESSION_POOL_LOCK_RATIO,
                     SMOOTH_STUTTER_ENABLED, SMOOTH_STUTTER_ENERGY_THRESH,
                     SONG_TOUCH_SEED_SALT,
                     SPEED_RAMP_ENABLED, SPEED_RAMP_MAX, SPEED_RAMP_MIN,
                     STILL_FRAME_SCORE_MAX,
                     STORY_CLUSTER_BONUS, STORY_CLUSTER_STICKINESS,
                     STORY_SWITCH_ON_STRUCTURE_CHANGE,
                     STRUCTURE_TEMPO_MULT)
from clip_pool import get_clip_dj_action_score, get_clip_spitting_score
from clip_highlight import get_clip_highlight_score, select_clip_duration
from creative_genome import build_intent, score_candidate
import db
from self_learning import get_global_learning_engine
from semantic_matching import calculate_semantic_match, compute_cluster_mask, VISUAL_SCENE_VOCAB
import user_prefs
from vector_tree import get_global_vector_tree
import cxx_accel


@dataclass
class TimelineSegment:
    start_sec: float
    end_sec: float
    clip_path: str
    clip_in_point: float   # wo im Quell-Clip geschnitten wird
    section_label: str = "mid"
    theme: str = "freedom"
    semantic_symbol: str = "BETON"  # OIDA Visual DNA: BETON, EISBACH, 089, OIDA, etc.
    camera: str = "hold"
    lighting: str = "natural"
    color: str = "neutral"
    transition: str = "cut"
    target_energy: float = 0.0
    confidence: float = 0.0
    information_density: float = 0.0
    motion_score: float = 0.5
    motion_direction: float = 0.0  # -1=Bildinhalt driftet links, +1=driftet rechts (siehe clip_pool.py)
    loop_boundary: bool = False
    speed_factor: float = 1.0      # Speed-Ramp: >1 = beschleunigt (Whip), <1 = verlangsamt (Slow-Mo)
    repetition: bool = False       # True innerhalb einer schnellen Wiederholungs-/Stutter-Zone
    mc_gender: str = "unknown"     # Stimmlagen-Schätzung des Songs, für Clip-Gender-Matching
    structure_label: str = "verse"     # Intro/Verse/Hook/Bridge/Breakdown/Outro (audio.structure)
    on_structure_boundary: bool = False  # True = Segmentende fällt exakt auf einen echten Struktur-Wechsel
    scratch: bool = False               # True = Segment beginnt mit einer DJ-Scratch-Cutaway (renderer._build_scratch_transition)
    scratch_strength: float = 0.0       # 0..1, aus audio_analysis._detect_scratch_dj_events (0 = kein Scratch)
    scratch_direction: str = "forward_back"  # "forward_back" (Scrub-vor-dem-Hit) oder "back_forward" (Backspin-in-den-Drop)
    dj_action: str = "none"             # DJ-Action-Typ: "scratch", "backspin", "vinyl_brake", "beat_juggle", "drop_impact", "none"
    smooth_stutter: bool = False        # True = sanfter, eleganter Highlight-Stutter auf musikalische Akzente
    audio_bpm: float = 120.0            # Song-BPM für beat-synchrones Tanzen des Bildinhalts
    fx: tuple = ()                      # Style-FX (z.B. grain/flicker/chroma), siehe creative_genome.StyleSpec.fx
    cut_style: str = "cut"              # z.B. hard_cut/jump_cut/push/break/whip/dissolve/fade_out
    sync_type: str = "on_beat"          # z.B. snap_drop/energy_peak/on_beat/syncopated/polyrhythm/breath/lip_sync


def _cosine(a: list, b: list) -> float:
    """Schnelle Cosine-Similarity ohne numpy-Array-Allokationen."""
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(n):
        ai = a[i]
        bi = b[i]
        dot += ai * bi
        norm_a += ai * ai
        norm_b += bi * bi
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / ((norm_a * norm_b) ** 0.5)))


@dataclass(slots=True)
class PrecomputedClip:
    path: str
    meta: dict
    duration: float
    motion_score: float
    motion_direction: float
    face_score: float
    semantic_match: float
    pref_bonus: float
    info_density: float
    tags_set: frozenset[str]
    vector_sim_raw: float
    alt_starts: list[float]
    bad_windows: tuple[tuple[float, float], ...]
    effect_allow_still: bool
    domain: str = "URBAN_STREET"
    learned_leaf_bonus: float = 0.0
    spitting_score: float = 0.0
    dj_action_score: float = 0.0
    highlight_score: float = 0.5


def precompute_candidates(globe: dict, song_vector: list, mc_gender: str = "unknown",
                          song_mood_tags: list | None = None,
                          song_style_weights: dict | None = None,
                          song_visual_objects: list | None = None,
                          song_cluster_mask: int | None = None) -> tuple[list[PrecomputedClip], list[tuple[str, dict]]]:
    """Precomputes static candidate features once per song to eliminate
    redundant scoring across thousands of segments."""
    pool: list[PrecomputedClip] = []
    fallback_pool: list[tuple[str, dict]] = []

    try:
        vtree = get_global_vector_tree()
    except Exception:
        vtree = None

    for path, meta in globe.items():
        if meta.get("failed") or not meta.get("playback_ok", True):
            continue
        duration = float(meta.get("duration", 0.0))
        if duration <= 0:
            continue


        still_score = meta.get("still_frame_score", 0.0)
        motion_score = float(meta.get("motion_score", 0.5))
        effect_allow_still = bool(meta.get("effect_allow_still", False))

        if still_score >= STILL_FRAME_SCORE_MAX:
            fallback_pool.append((path, meta))
            continue
        if motion_score <= 0.01 and not effect_allow_still:
            fallback_pool.append((path, meta))
            continue

        face_score = float(meta.get("face_score", 0.0))
        motion_direction = float(meta.get("motion_direction", 0.0))
        tags = meta.get("tags") or []
        tags_set = frozenset(t.lower() for t in tags)
        pref_bonus = user_prefs.preference_bonus(tags)
        spitting_score = get_clip_spitting_score(meta)
        dj_action_score = get_clip_dj_action_score(meta)

        sem_match = calculate_semantic_match(
            meta, song_vector,
            song_mood_tags=song_mood_tags,
            song_mc_gender=mc_gender,
            song_style_weights=song_style_weights,
            song_visual_objects=song_visual_objects,
            song_cluster_mask=song_cluster_mask,
        )
        if sem_match is None:
            sem_match = 0.5

        info_density = float(meta.get("information_density", 0.0))
        if not info_density:
            from creative_genome import information_density
            info_density = information_density(meta)

        clip_vec = meta.get("vector") or []
        vec_sim_raw = (_cosine(song_vector, clip_vec) + 1.0) / 2.0 if (song_vector and clip_vec) else 0.5

        # Self-Learning & Hierarchical Vector-Tree Prior Boost
        leaf = vtree.leaves.get(path) if (vtree and hasattr(vtree, "leaves")) else None
        leaf_domain = getattr(leaf, "domain", None) or (meta.get("domain") or "URBAN_STREET")
        learned_leaf_bonus = 0.0
        leaf_uses = getattr(leaf, "uses", 0)
        leaf_mean_reward = getattr(leaf, "mean_reward", 0.5)
        if leaf and leaf_uses > 0:
            learned_leaf_bonus = max(-0.1, min(0.1, (leaf_mean_reward - 0.5) * 0.15))

        learned = meta.get("learned") or {}
        learned_bonus = 0.0
        if learned:
            avg_rew = float(learned.get("avg_reward", 0.5))
            uses = int(learned.get("uses", 0))
            if uses > 0:
                learned_bonus = (avg_rew - 0.5) * 0.15

        sem_match = min(1.0, max(0.0, sem_match + learned_bonus))

        alt_starts = [float(s) for s in meta.get("alternative_start_points", []) if isinstance(s, (int, float))]
        bad_windows = tuple((float(br.get("start", 0.0)), float(br.get("end", 0.0))) for br in (meta.get("bad_frame_ranges") or []))

        pool.append(PrecomputedClip(
            path=path,
            meta=meta,
            duration=duration,
            motion_score=motion_score,
            motion_direction=motion_direction,
            face_score=face_score,
            semantic_match=sem_match,
            pref_bonus=pref_bonus,
            info_density=info_density,
            tags_set=tags_set,
            vector_sim_raw=vec_sim_raw,
            alt_starts=alt_starts,
            bad_windows=bad_windows,
            effect_allow_still=effect_allow_still,
            domain=leaf_domain,
            learned_leaf_bonus=learned_leaf_bonus,
            spitting_score=spitting_score,
            dj_action_score=dj_action_score,
            highlight_score=get_clip_highlight_score(meta),
        ))

    # Fast C++ Native SIMD Matrix
    matrix_rows = [
        (i, c.duration, c.motion_score, c.motion_direction, c.face_score,
         c.semantic_match, c.pref_bonus, c.info_density, c.learned_leaf_bonus)
        for i, c in enumerate(pool)
    ]
    candidate_matrix = np.array(matrix_rows, dtype=np.float32) if matrix_rows else np.empty((0, 9), dtype=np.float32)
    try:
        pool.candidate_matrix = candidate_matrix  # type: ignore[attr-defined]
    except Exception:
        pass

    return pool, fallback_pool


def _section_at(sections: list, t: float) -> str:
    for start, end, label in sections:
        if start <= t < end:
            return label
    return "mid"


def _structure_at(structure: list, t: float) -> str:
    """Echte Song-Struktur (Intro/Verse/Hook/Bridge/Breakdown/Outro) an Zeitpunkt
    t, aus audio_analysis._detect_song_structure (MFCC-Similarity-Clustering).
    Unabhängig von der groben low/mid/high-Energie-Sektionierung (_section_at)."""
    for start, end, label in structure:
        if start <= t < end:
            return label
    return "verse"


def _next_structure_boundary(structure: list, t: float):
    """Zeitpunkt des nächsten ECHTEN Struktur-Wechsels nach t (z.B. Verse->Hook),
    oder None ohne Struktur-Daten bzw. wenn t bereits im letzten Block liegt.
    structure ist eine lückenlose Liste von (start, end, label)-Blöcken, der
    Wechsel zwischen Block i und i+1 liegt exakt bei block[i].end == block[i+1].start."""
    starts = sorted(start for start, _end, _label in structure if start > t + 1e-6)
    return starts[0] if starts else None


def _energy_match(section_label: str, motion_score: float) -> float:
    """Belohnt hohe Motion-Clips in energiereichen Sektionen und ruhige Clips
    in energiearmen Sektionen — analog zu BeatSync-Engine's Energy-Wave-Logik,
    nur hier direkt als Scoring-Term statt als reine Cut-Dichte."""
    target = {"low": 0.2, "mid": 0.5, "high": 0.85}[section_label]
    return 1.0 - abs(target - motion_score)


def _motion_flow_bonus(candidate_direction: float, prev_direction: float | None,
                       seg_len: float, streak: int) -> float:
    if not MOTION_FLOW_CONTINUITY_ENABLED or prev_direction is None:
        return 0.0
    if (abs(prev_direction) < MOTION_FLOW_DIRECTION_THRESHOLD
            or abs(candidate_direction) < MOTION_FLOW_DIRECTION_THRESHOLD):
        return 0.0
    if streak >= MOTION_FLOW_MAX_STREAK:
        return 0.0
    alignment = 1.0 if (prev_direction > 0) == (candidate_direction > 0) else -1.0
    strength = min(abs(prev_direction), abs(candidate_direction))
    span = max(1e-6, MOTION_FLOW_SLOW_CUT_SEC - MOTION_FLOW_FAST_CUT_SEC)
    tempo_weight = 1.0 - max(0.0, min(1.0, (seg_len - MOTION_FLOW_FAST_CUT_SEC) / span))
    return MOTION_FLOW_CONTINUITY_BONUS * alignment * strength * tempo_weight


def _blocked_windows(blocked_ranges: list, bad_frame_ranges: list) -> list:
    windows = list(blocked_ranges)
    for br in bad_frame_ranges:
        windows.append((br.get("start", 0.0), br.get("end", 0.0)))
    return windows


def _pick_start_point(duration: float, seg_len: float, alternative_start_points: list,
                      blocked_windows: list):
    """Sucht einen Startpunkt für ein Segment der Länge seg_len innerhalb eines
    Clips, der weder mit Anti-Repeat-Sperren noch mit bad_frame_ranges überlappt (C++ optimiert)."""
    cxx = cxx_accel.get_cxx_engine()
    seed = random.randint(0, 0xFFFFFFF)
    return cxx.pick_start_point(
        duration, seg_len,
        alternative_start_points=alternative_start_points,
        blocked_windows=blocked_windows,
        seed=seed
    )


def _speed_factor_for(seg_len: float) -> float:
    """Rhythmische Dynamik / Speed-Ramp: kurze (energiereiche) Segmente werden
    Richtung SPEED_RAMP_MAX beschleunigt (Whip-Feel), lange (ruhige) Segmente
    Richtung SPEED_RAMP_MIN leicht verlangsamt (Slow-Mo-Atmung). Die reale
    Segmentdauer in der Timeline bleibt unverändert — nur renderer.py wendet
    die Rampe an (setpts), sodass Audio/Video-Sync nie verloren geht."""
    if not SPEED_RAMP_ENABLED:
        return 1.0
    span = max(1e-6, MAX_SEGMENT_SEC - MIN_SEGMENT_SEC)
    norm_len = max(0.0, min(1.0, (seg_len - MIN_SEGMENT_SEC) / span))  # 0=kurz/energetisch, 1=lang/ruhig
    return round(max(0.1, SPEED_RAMP_MAX - norm_len * (SPEED_RAMP_MAX - SPEED_RAMP_MIN)), 3)


def _maybe_extend_for_breath(seg_len: float, e: float, t: float, duration_sec: float) -> float:
    """Lässt ruhige Stellen (Pausen, Atmen, ausklingende Endtakte) den Clip
    länger laufen statt stur im energie-basierten Raster zu schneiden — ein
    Segment "atmet" so mit der Musik, statt bei Stille/Fade-Out weiter im
    selben Tempo wegzuschneiden. Nur wirksam bei SEHR niedriger lokaler
    Energie (BREATH_ENERGY_THRESHOLD); sonst bleibt seg_len unverändert."""
    if e > BREATH_ENERGY_THRESHOLD:
        return seg_len
    extended = seg_len * BREATH_EXTEND_FACTOR
    # Ausklang-Bonus: in den letzten Songsekunden darf ein leiser, gehaltener
    # Endtakt noch etwas länger stehen bleiben (langgezogenes Ausklingen).
    if duration_sec > 0 and (duration_sec - t) <= 6.0:
        extended *= 1.15
    return min(extended, BREATH_SEGMENT_MAX_SEC)


def _in_repetition_window(t: float, end: float, repetition_windows: list) -> bool:
    """Prüft ob das Segment [t, end) eine schnelle Wiederholungs-/Stutter-Zone
    (siehe audio_analysis._detect_repetition_windows) überlappt."""
    return any(t < w_end and end > w_start for w_start, w_end in repetition_windows)


def _scratch_event_near(t: float, scratch_events: list) -> dict | None:
    """Findet ein DJ-Scratch-Event (siehe audio_analysis._detect_scratch_dj_events),
    das GENAU auf diesen Segment-Einstieg fällt — Scratch-Cutaways gehören an
    den ANFANG eines Segments (der Plattenteller wird gerissen, DANN kommt der
    neue Clip/Hit), nicht mittendrin. Toleranzfenster analog zu den anderen
    Beat-Snap-Toleranzen in diesem Modul (siehe candidate_beats-Suche oben)."""
    for ev in scratch_events:
        if abs(ev["time"] - t) <= 0.12:
            return ev
    return None


def _song_touch_seed(song_path: str) -> int:
    """Deterministischer Per-Song-Seed (siehe config.SONG_TOUCH_SEED_SALT,
    vorher nirgends verwendet): gleicher Song -> exakt gleicher rhythmischer
    "Touch" bei jedem Render, verschiedene Songs klingen/wirken erkennbar
    unterschiedlich. Kein echter Zufall -> reproduzierbar, kein Risiko für
    Audio/Video-Sync-Drift zwischen Läufen."""
    digest = hashlib.md5(f"{SONG_TOUCH_SEED_SALT}:{song_path}".encode()).hexdigest()
    return int(digest[:8], 16)


def _apply_structure_tempo(seg_len: float, structure_label: str) -> float:
    """Struktur-abhängiges Cut-Tempo (siehe config.STRUCTURE_TEMPO_MULT, vorher
    definiert aber nie verdrahtet): staucht die energie-basierte Segmentlänge
    in Hooks (schnellere, druckvollere Schnitte) und streckt sie in
    Breakdown/Outro (ruhigere, weniger "hektische" Schnitte), statt überall
    im gleichen Energie-Raster zu schneiden. Wird VOR dem Beat-Snap
    angewendet, damit der Snap auf Basis der bereits angepassten Ziellänge
    den nächstgelegenen echten Beat wählt."""
    mult = STRUCTURE_TEMPO_MULT.get(structure_label, 1.0)
    return max(MIN_SEGMENT_SEC, min(MAX_SEGMENT_SEC, seg_len * mult))


def _polyrhythm_jitter(seg_len: float, rng: random.Random, intensity: float) -> float:
    """Leichte, deterministische (per-Song geseedete) Segmentlängen-Varianz
    als Cut-seitiges Pendant zur bereits vorhandenen Kamera-Polyrhythmik
    (CAMERA_RUBBER_CYCLES_CHOICES) — aber fürs tatsächliche Schnitt-Tempo.
    intensity in [0,1] kommt aus main.py, abgeleitet von der Anzahl echter
    Beat-Switches/Movements (song_semantics.py, aus den [BEAT SWITCH - ...]-
    Markern der Traktor-Tracklisten-Lyrics): Songs mit tatsächlichen
    Tempo-Wechseln in der Produktion bekommen mehr rhythmische Cut-Varianz,
    Songs ohne bekannte Beat-Switches bleiben nah am reinen Struktur-/
    Energie-Raster (intensity=0.0 -> Funktion ist ein No-Op)."""
    if intensity <= 0.0:
        return seg_len
    jitter = 1.0 + rng.uniform(-0.18, 0.18) * intensity
    return max(MIN_SEGMENT_SEC, min(MAX_SEGMENT_SEC, seg_len * jitter))


def _resolve_active_gender_at(t: float, total_duration: float, song_semantics: dict | None, fallback_gender: str = "unknown") -> str:
    """Ermittelt das aktive Gesangs-Geschlecht (male, female, dual, unknown)
    an Zeitpunkt t anhand von zeilenweiser Lyrics-Semantik, Gender-Timeline und Sektions-Styles."""
    if not song_semantics or total_duration <= 0:
        return fallback_gender if fallback_gender != "unknown" else "unknown"

    frac = max(0.0, min(1.0, t / total_duration))

    # 1. Globale Gender-Timeline
    timeline = song_semantics.get("gender_timeline") or []
    for item in timeline:
        if item.get("start_frac", 0.0) <= frac <= item.get("end_frac", 1.0):
            g = item.get("gender")
            if g and g != "unknown":
                return g

    # 2. Zeilen-Genders
    lines = song_semantics.get("line_genders") or []
    for ln in lines:
        if ln.get("rel_start", 0.0) <= frac <= ln.get("rel_end", 1.0):
            g = ln.get("gender")
            if g and g != "unknown":
                return g

    # 3. Sektions-Vocal-Style
    sections = song_semantics.get("sections") or []
    if sections:
        sec_idx = min(int(frac * len(sections)), len(sections) - 1)
        sec = sections[sec_idx]
        sec_vocal = sec.get("vocal_style")
        if sec_vocal and sec_vocal != "unknown":
            return sec_vocal

    # 4. Overall Semantics mc_gender
    sem_mc = song_semantics.get("mc_gender")
    if sem_mc and sem_mc != "unknown":
        return sem_mc

    return fallback_gender


def _resolve_oida_semantics(t: float, audio: "AudioAnalysis", structure: list, energy: float,
                            tension_score: float = 0.5, punchline_density: float = 0.0) -> tuple[str, str]:
    """Translates current audio state into a (Symbol, CameraPersona) pair.
    Implements dynamic OIDA Visual Semantics mapping with rhythmic camera diversity,
    emotional tension response and 2.5D spatial perspective support."""
    struct_label = "verse"
    for start, end, label in structure:
        if start <= t < end:
            struct_label = label
            break

    # Check for drop event proximity
    near_drop = False
    if getattr(audio, "drop_times", None):
        for drop in audio.drop_times:
            if abs(drop - t) <= 0.35:
                near_drop = True
                break

    # Camera personas cyclic pool for verse cadence
    t_step = int(t / 1.5)
    verse_cameras = ["push", "drift", "focus_zoom", "pull", "dominance", "snap"]
    verse_persona = verse_cameras[t_step % len(verse_cameras)]

    # Tension-boosted personas
    if tension_score >= 0.75:
        verse_persona = "dominance" if (t_step % 2 == 0) else "snap"
    elif punchline_density >= 0.45:
        verse_persona = "focus_zoom" if (t_step % 2 == 0) else "snap"

    if near_drop or energy > 0.82:
        symbol = "BAM"
        camera = "explosion"
    elif struct_label == "hook":
        symbol = "OIDA"
        camera = "dominance" if (t_step % 2 == 0) else "snap"
    elif struct_label == "intro":
        symbol = "MINGA"
        camera = "drift"
    elif struct_label == "breakdown":
        symbol = "SILENCE"
        camera = "intelligence" if energy < 0.3 else "drift"
    elif struct_label == "outro":
        symbol = "WAVE"
        camera = "pull" if energy < 0.3 else "drift"
    elif struct_label == "bridge":
        symbol = "BETON"
        camera = "focus_zoom" if energy > 0.5 else "pull"
    else:
        # Verse / standard
        symbol = "BETON"
        camera = verse_persona

    if energy < 0.18:
        symbol = "SILENCE"
        camera = "intelligence"

    return symbol, camera


def build_timeline(song_vector: list, audio: AudioAnalysis, globe: dict,
                    recent_used: list, style=None, platform: str = "full",
                    song_tags: list | None = None, song_path: str = "",
                    beat_switch_intensity: float = 0.0, tile_bonus_fn=None,
                    song_style_weights: dict | None = None,
                    pacing_strategy: str | None = None,
                    song_semantics: dict | None = None) -> list:
    """Erzeugt die vollständige Segmentliste für die gesamte Songlänge unter
    Berücksichtigung gelernter Thompson-Sampling-Pacing-Strategien, Lyrics-Semantik und Markov-Flows."""
    if audio.duration_sec <= 0:
        raise ValueError("Audio-Dauer muss größer als 0 Sekunden sein.")
    usable = {p: m for p, m in globe.items() if not m.get("failed")}
    if not usable:
        raise RuntimeError(
            "Keine analysierten Clips verfügbar — erst clip_pool.build_or_update_globe() "
            "laufen lassen bzw. prüfen ob alle Clips als 'failed' markiert sind."
        )
    usage_counts = db.total_uses_many(usable)

    # 2/3 Session-Pool-Sperre über Sessions hinweg
    session_locked: set[str] = set()
    if SESSION_POOL_LOCK_ENABLED:
        session_locked = db.get_session_locked_clips(
            usable,
            lock_ratio=SESSION_POOL_LOCK_RATIO,
            cooldown_hours=SESSION_COOLDOWN_HOURS,
            max_global_uses=SESSION_MAX_GLOBAL_USES
        )
        if session_locked:
            fresh_count = len(usable) - len(session_locked)
            print(f"[timeline_builder] 2/3 Session-Pool-Sperre aktiv: {len(session_locked)}/{len(usable)} Clips gesperrt ({fresh_count} frische Clips im Umlauf)")

    try:
        learning_engine = get_global_learning_engine()
    except Exception:
        learning_engine = None

    # Deep Song Semantics Auflösung
    if song_semantics is None and song_path:
        try:
            song_semantics = db.get_song_semantics(song_path)
        except Exception:
            song_semantics = None

    song_visual_objects = song_semantics.get("visual_objects", []) if song_semantics else []
    song_cluster_mask = song_semantics.get("cluster_mask", 0) if song_semantics else 0
    lyrics_sections = song_semantics.get("sections", []) if song_semantics else []
    tension_score = float(song_semantics.get("tension_score", 0.5)) if song_semantics else 0.5
    punchline_density = float(song_semantics.get("punchline_density", 0.0)) if song_semantics else 0.0

    # Partielle Anti-Repeat-Sperren: nur der genutzte Zeitbereich (+ Sicherheits-
    # abstand) wird blockiert, nicht der ganze Clip.
    blocked_ranges: dict = {}

    def _add_blocked(clip_path, clip_in, clip_out):
        if not clip_path or clip_in is None or clip_out is None:
            return
        window = (max(0.0, clip_in - PARTIAL_REPEAT_PADDING_SEC),
                  clip_out + PARTIAL_REPEAT_PADDING_SEC)
        blocked_ranges.setdefault(clip_path, []).append(window)

    for entry in recent_used[:NO_REPEAT_WINDOW]:
        _add_blocked(entry.get("clip_path"), entry.get("clip_in"), entry.get("clip_out"))
    for clip_path, ranges in db.get_clip_cooldown_ranges(PARTIAL_REPEAT_COOLDOWN_SEC).items():
        for clip_in, clip_out in ranges:
            _add_blocked(clip_path, clip_in, clip_out)

    pool, fallback_pool = precompute_candidates(
        usable, song_vector, mc_gender=audio.mc_gender,
        song_mood_tags=song_tags, song_style_weights=song_style_weights,
        song_visual_objects=song_visual_objects, song_cluster_mask=song_cluster_mask,
    )

    timeline: list = []
    touch_rng = random.Random(_song_touch_seed(song_path))

    prev_motion_direction: float | None = None
    motion_streak = 0
    prev_domain = "URBAN_STREET"
    prev_active_gender: str | None = None
    active_story_tags: frozenset[str] | None = None
    active_story_domain: str = "URBAN_STREET"
    prev_structure_label: str | None = None

    # Learned Pacing Multipliers
    pacing_mult = 1.0
    if pacing_strategy == "ultra_fast":
        pacing_mult = 0.85
    elif pacing_strategy == "narrative":
        pacing_mult = 1.25
    elif pacing_strategy == "syncopated":
        beat_switch_intensity = max(beat_switch_intensity, 0.5)

    target_duration = min(audio.duration_sec, 15.0) if platform == "tiktok" else audio.duration_sec
    t = 0.0
    while t < target_duration:
        # Segmentlänge aus lokaler Energie ableiten (kurz bei Drops, lang bei Ruhe)
        idx = min(int(t / audio.duration_sec * len(audio.energy)), len(audio.energy) - 1) if audio.energy else 0
        e = audio.energy[idx] if audio.energy else 0.5
        if platform == "tiktok" and t < 1.5:
            e = max(e, 0.75)  # visueller Hook: sofort Bewegung statt ruhigem Intro
        seg_len = energy_to_segment_length(e) * pacing_mult
        current_structure = _structure_at(audio.structure, t) if audio.structure else "verse"
        if platform != "tiktok":
            if audio.structure:
                seg_len = _apply_structure_tempo(seg_len, current_structure)
            seg_len = _polyrhythm_jitter(seg_len, touch_rng, beat_switch_intensity)
            seg_len = _maybe_extend_for_breath(seg_len, e, t, audio.duration_sec)
        end = min(t + seg_len, target_duration)

        # Musical Beat, Downbeat & Drum Transient Snapping in C++:
        cxx_engine = cxx_accel.get_cxx_engine()
        is_downbeat_pref = bool(audio.downbeats and (seg_len >= 1.2 or current_structure in ("verse", "hook")))
        drum_onsets = getattr(audio, "drum_onsets", None) if DRUM_STEM_SYNC_ENABLED else None
        
        end = cxx_engine.snap_timeline_boundary(
            t=t,
            end=end,
            seg_len=seg_len,
            target_duration=target_duration,
            drops=audio.drop_times,
            downbeats=audio.downbeats,
            beats=audio.beat_times,
            drum_transients=drum_onsets,
            min_seg_sec=MIN_SEGMENT_SEC,
            transient_tolerance_sec=DRUM_TRANSIENT_SNAP_TOLERANCE_SEC,
            is_downbeat_preferred=is_downbeat_pref
        )

        if end <= t:
            end = min(t + max(seg_len, MIN_SEGMENT_SEC), target_duration)
            if end - t < MIN_SEGMENT_SEC * 0.5:
                break  # Restfragment zu kurz für sinnvollen Clip → Render-Ende
        if platform == "tiktok":
            next_drop = next((drop for drop in audio.drop_times if drop > t + 0.05), None)
            if next_drop is not None and next_drop < end:
                end = next_drop
            if end - t < MIN_SEGMENT_SEC:
                end = min(t + max(seg_len, MIN_SEGMENT_SEC), target_duration)
        on_structure_boundary = False
        if platform != "tiktok" and audio.structure:
            next_boundary = _next_structure_boundary(audio.structure, t)
            if next_boundary is not None and t + MIN_SEGMENT_SEC <= next_boundary <= end + 1e-6:
                end = next_boundary
                on_structure_boundary = True
        structure_label = current_structure if platform != "tiktok" else (
            _structure_at(audio.structure, t) if audio.structure else "verse")
        if prev_structure_label is not None and structure_label != prev_structure_label:
            if STORY_SWITCH_ON_STRUCTURE_CHANGE:
                active_story_tags = None  # Sektionswechsel (Verse -> Hook etc.) triggert frisches Story-Motiv
        section_label = _section_at(audio.sections, t)
        if platform == "tiktok" and t < 1.5:
            section_label = "high"
        intent = build_intent(section_label, e, style, song_tags or []) if style else None

        is_repetition = _in_repetition_window(t, end, audio.repetition_windows)

        # LibSync MC Rapper Spitting & Performance Detection
        is_spitting = False
        if LIBSYNC_SPITTING_ENABLED and getattr(audio, "spitting_burst_windows", None):
            is_spitting = any(w_start <= t <= w_end for w_start, w_end, _ in audio.spitting_burst_windows)

        # DJ Sync Action Detektion (Scratches, Backspins, Vinyl Brake, Drops, Beat Juggles)
        dj_event = None
        if DJ_SYNC_ACTION_ENABLED and getattr(audio, "dj_actions", None):
            for dja in audio.dj_actions:
                if abs(dja["time"] - t) <= 0.25:
                    dj_event = dja
                    break

        # Smooth Highlight Stutter auf musikalische Akzente
        is_smooth_stutter = False
        if SMOOTH_STUTTER_ENABLED:
            if dj_event and dj_event.get("action") in ("scratch", "backspin", "beat_juggle"):
                is_smooth_stutter = True
            elif is_repetition and e >= (SMOOTH_STUTTER_ENERGY_THRESH * 0.85):
                is_smooth_stutter = True
            elif e >= SMOOTH_STUTTER_ENERGY_THRESH and (structure_label in ("hook", "breakdown") or t in (audio.downbeats or [])):
                is_smooth_stutter = True

        # Dynamische Gender-Auflösung (M/F Flip-Flop & Duette)
        active_gender = _resolve_active_gender_at(t, audio.duration_sec, song_semantics, fallback_gender=audio.mc_gender)
        is_gender_flip = (prev_active_gender in ("male", "female") and active_gender in ("male", "female") and prev_active_gender != active_gender)

        # Dynamic Micro-Cut / Stutter-Slice Reaktion auf schnelle Drum-Rolls & Accent-Bursts
        drum_roll_slices = []
        if (DRUM_MICRO_CUT_ENABLED and is_repetition and (end - t) >= DRUM_MICRO_CUT_MIN_BURST_DUR
                and getattr(audio, "drum_onsets", None)):
            drum_roll_slices = cxx_engine.slice_drum_roll(
                t, end, audio.drum_onsets,
                min_slice_sec=0.18, max_slices=DRUM_MICRO_CUT_MAX_SLICES
            )

        # Aktive Lyrics-Sektion für Grounding-Boni
        sec_visual_cues: list[str] = []
        sec_cluster_mask: int = 0
        if lyrics_sections:
            sec_idx = min(int((t / max(1.0, audio.duration_sec)) * len(lyrics_sections)), len(lyrics_sections) - 1)
            sec_data = lyrics_sections[sec_idx]
            sec_visual_cues = sec_data.get("visual_cues", [])
            sec_cluster_mask = sec_data.get("cluster_mask", 0)

        # Deep Semantics Theme, Lighting & Color Mapping
        symbol, persona = _resolve_oida_semantics(
            t, audio, audio.structure if audio.structure else [], e,
            tension_score=tension_score, punchline_density=punchline_density
        )
        active_theme = intent.theme if intent else symbol
        if sec_visual_cues:
            active_theme = sec_visual_cues[0].upper()
        elif song_visual_objects:
            active_theme = song_visual_objects[0].upper()

        active_lighting = intent.lighting if intent else "natural"
        active_color = intent.color if intent else "neutral"

        if "NIGHT_CLUB" in active_theme or "dark" in (song_tags or []):
            active_lighting = "lowkey"
        elif "CYBER_NEON" in active_theme or "highkey" in (song_tags or []):
            active_lighting = "highkey"

        if "CYBER_NEON" in active_theme or "vivid" in (song_tags or []):
            active_color = "vivid"
        elif "BAVARIAN_ROOTS" in active_theme or "WEED_SMOKE" in active_theme:
            active_color = "warm"
        elif "WEAPON_COMBAT" in active_theme or tension_score >= 0.70:
            active_color = "desaturated"

        if drum_roll_slices:
            # Segment in rhythmisch synchronisierte Micro-Cuts aufteilen
            slice_bounds = [t] + drum_roll_slices + [end]
            for s_idx in range(len(slice_bounds) - 1):
                sub_t, sub_end = slice_bounds[s_idx], slice_bounds[s_idx + 1]
                sub_speed_factor = max(1.3, min(2.0, _speed_factor_for(sub_end - sub_t) * DRUM_ROLL_SPEED_RAMP_BOOST))
                sub_src_len = (sub_end - sub_t) * sub_speed_factor

                sub_clip_path, sub_clip_in, sub_domain = _pick_clip(
                    song_vector, globe, section_label, sub_end - sub_t,
                    blocked_ranges=blocked_ranges,
                    intent=intent,
                    usage_counts=usage_counts,
                    session_locked=session_locked,
                    mc_gender=active_gender,
                    song_mood_tags=song_tags,
                    song_style_weights=song_style_weights,
                    prev_motion_direction=prev_motion_direction,
                    motion_streak=motion_streak,
                    source_len=sub_src_len,
                    precomputed_pool=pool,
                    fallback_pool=fallback_pool,
                    prev_domain=prev_domain,
                    audio_bpm=audio.bpm,
                    learning_engine=learning_engine,
                    section_visual_cues=sec_visual_cues,
                    section_cluster_mask=sec_cluster_mask,
                    is_spitting=is_spitting,
                    is_dj_action=bool(dj_event),
                    active_story_tags=active_story_tags,
                    active_story_domain=active_story_domain,
                )
                prev_domain = sub_domain
                sub_clip_meta = globe[sub_clip_path]
                sub_c_tags = sub_clip_meta.get("tags") or []
                if sub_c_tags:
                    active_story_tags = frozenset(tag.lower() for tag in sub_c_tags)
                active_story_domain = sub_domain
                prev_structure_label = structure_label
                sub_motion_dir = float(sub_clip_meta.get("motion_direction", 0.0))
                prev_motion_direction = sub_motion_dir

                timeline.append(TimelineSegment(
                    sub_t, sub_end, sub_clip_path, sub_clip_in,
                    section_label=section_label,
                    semantic_symbol=symbol,
                    theme=active_theme,
                    camera="snap" if s_idx > 0 else persona,
                    lighting=active_lighting,
                    color=active_color,
                    transition="slide" if s_idx == 0 else "cut",
                    target_energy=intent.target_energy if intent else max(0.8, e),
                    confidence=intent.confidence if intent else 0.0,
                    information_density=float(sub_clip_meta.get("information_density", 0.0)),
                    motion_score=float(sub_clip_meta.get("motion_score", 0.5)),
                    motion_direction=sub_motion_dir,
                    loop_boundary=platform == "tiktok" and sub_end >= target_duration,
                    speed_factor=sub_speed_factor,
                    repetition=True,
                    mc_gender=active_gender,
                    structure_label=structure_label,
                    on_structure_boundary=(s_idx == len(slice_bounds) - 2 and on_structure_boundary),
                    scratch=False,
                    scratch_strength=0.0,
                    scratch_direction="forward_back",
                    dj_action=(dj_event["action"] if dj_event else "none"),
                    smooth_stutter=is_smooth_stutter,
                    audio_bpm=audio.bpm,
                    fx=tuple(style.fx) if style else (),
                    cut_style="whip",
                    sync_type="snap_drop",
                ))
                sub_clip_dur = float(sub_clip_meta.get("duration", 0.0))
                sub_blocked_end = min(sub_clip_dur, sub_clip_in + sub_src_len) if sub_clip_dur > 0 else (sub_clip_in + sub_src_len)
                _add_blocked(sub_clip_path, sub_clip_in, sub_blocked_end)
                usage_counts[sub_clip_path] = usage_counts.get(sub_clip_path, 0) + 1
            prev_active_gender = active_gender
            t = end
            continue

        seg_speed_factor = _speed_factor_for(end - t)
        if is_repetition:
            seg_speed_factor = min(2.0, max(seg_speed_factor, DRUM_ROLL_SPEED_RAMP_BOOST))
        seg_source_len = (end - t) * seg_speed_factor if seg_speed_factor > 0 else (end - t)
        clip_path, clip_in_point, chosen_domain = _pick_clip(
            song_vector, globe, section_label, end - t,
            blocked_ranges=blocked_ranges,
            intent=intent,
            usage_counts=usage_counts,
            session_locked=session_locked,
            mc_gender=active_gender,
            song_mood_tags=song_tags,
            song_style_weights=song_style_weights,
            extra_score_fn=(lambda meta, _t=t, _end=end: tile_bonus_fn(_t, _end, meta)) if tile_bonus_fn else None,
            prev_motion_direction=prev_motion_direction,
            motion_streak=motion_streak,
            source_len=seg_source_len,
            precomputed_pool=pool,
            fallback_pool=fallback_pool,
            prev_domain=prev_domain,
            audio_bpm=audio.bpm,
            learning_engine=learning_engine,
            section_visual_cues=sec_visual_cues,
            section_cluster_mask=sec_cluster_mask,
            is_spitting=is_spitting,
            is_dj_action=bool(dj_event),
            active_story_tags=active_story_tags,
            active_story_domain=active_story_domain,
        )
        prev_domain = chosen_domain
        clip_meta = globe[clip_path]
        c_tags = clip_meta.get("tags") or []
        if c_tags:
            active_story_tags = frozenset(tag.lower() for tag in c_tags)
        active_story_domain = chosen_domain
        prev_structure_label = structure_label
        candidate_motion_direction = float(clip_meta.get("motion_direction", 0.0))
        if (prev_motion_direction is not None
                and abs(prev_motion_direction) >= MOTION_FLOW_DIRECTION_THRESHOLD
                and abs(candidate_motion_direction) >= MOTION_FLOW_DIRECTION_THRESHOLD
                and (prev_motion_direction > 0) == (candidate_motion_direction > 0)):
            motion_streak += 1
        else:
            motion_streak = 0
        prev_motion_direction = candidate_motion_direction

        # ── 140 BPM Highlight Snap: Beat-genaue Segmentdauer aus sync_140bpm ──
        # Wenn der Song nahe 140 BPM ist UND der Clip einen gespeicherten
        # sync_140bpm-Plan hat (FULL / FULL_HOLD = 4 Bars, CROSSFADE = 3.5 Bars,
        # SHORT = 3 Bars), korrigiert die tatsächliche Timeline-Segmentgrenze auf
        # diese optimale Bar-Länge — statt der energie-basierten seg_len-Schätzung.
        # Nur wenn das Ergebnis noch innerhalb der Song-Dauer passt.
        bpm_snap_active = False
        if (DUAL_FRAME_HIGHLIGHT_ENABLED
                and abs(audio.bpm - 140.0) < 8.0
                and platform != "tiktok"):
            clip_hl = float(clip_meta.get("highlight_score", 0.0))
            sync_plan = clip_meta.get("sync_140bpm")
            if sync_plan and isinstance(sync_plan, dict) and clip_hl >= DUAL_FRAME_THRESHOLD_MAYBE:
                snap_dur = float(sync_plan.get("duration", 0.0))
                snap_strategy = sync_plan.get("strategy", "")
                # Nur echte Beat-genaue Strategien verwenden (FULL, FULL_HOLD, SHORT)
                # CROSSFADE (3.5 Bars) ist bewusst OFF-BEAT, bleibt für Crossfades
                if snap_strategy in ("FULL", "FULL_HOLD", "SHORT") and snap_dur > MIN_SEGMENT_SEC:
                    snapped_end = min(t + snap_dur, target_duration)
                    # Sicherheitsabstand: nicht über verbleibende Songdauer hinaus
                    if snapped_end > t + MIN_SEGMENT_SEC * 0.5:
                        end = snapped_end
                        bpm_snap_active = True

        scratch_event = _scratch_event_near(t, audio.scratch_events)
        do_scratch = False
        scratch_direction = "forward_back"
        if SCRATCH_ENABLED and scratch_event is not None and (end - t) > 0.4:
            kind_factor = 1.0 if scratch_event["kind"] == "detected" else 0.7
            trigger_chance = SCRATCH_PROBABILITY * kind_factor * (0.6 + 0.4 * scratch_event["strength"])
            if touch_rng.random() < trigger_chance:
                do_scratch = True
                scratch_direction = "back_forward" if structure_label == "hook" else "forward_back"

        camera_chosen = persona if not intent else (intent.camera if intent.camera not in ('hold', 'dynamic') else persona)
        if is_spitting and (not intent or intent.camera in ('hold', 'drift', 'dynamic')):
            camera_chosen = "focus_zoom"
        elif dj_event:
            if dj_event["action"] == "backspin":
                camera_chosen = "back_spin"
            elif dj_event["action"] == "drop_impact":
                camera_chosen = "explosion"
            elif dj_event["action"] in ("scratch", "beat_juggle"):
                camera_chosen = "snap"

        # Kamera-Override bei 140 BPM HOLD-Strategie (Freeze auf Peak-Frame)
        if bpm_snap_active and clip_meta.get("sync_140bpm", {}).get("strategy") == "FULL_HOLD":
            camera_chosen = "hold"

        # Schnitt- und Transition-Auswahl bei Gender Flip-Flop, Spitting oder DJ-Actions
        transition_chosen = "slide" if (is_repetition or is_gender_flip or (dj_event and dj_event["action"] == "backspin")) else (intent.transition if intent else "cut")
        cut_style_chosen = "whip" if (is_repetition or is_gender_flip or is_spitting or bool(dj_event)) else "cut"
        sync_type_chosen = "lip_sync" if is_spitting else ("snap_drop" if (is_repetition or (dj_event and dj_event["action"] == "drop_impact")) else ("on_beat" if bpm_snap_active else "on_beat"))

        # recalc seg_source_len nach möglichem BPM-Snap
        actual_seg_len = end - t
        seg_speed_factor = _speed_factor_for(actual_seg_len)
        if is_repetition:
            seg_speed_factor = min(2.0, max(seg_speed_factor, DRUM_ROLL_SPEED_RAMP_BOOST))
        seg_source_len = actual_seg_len * seg_speed_factor if seg_speed_factor > 0 else actual_seg_len

        timeline.append(TimelineSegment(
            t, end, clip_path, clip_in_point,
            section_label=section_label,
            semantic_symbol=symbol,
            theme=active_theme,
            camera=camera_chosen,
            lighting=active_lighting,
            color=active_color,
            transition=transition_chosen,
            target_energy=intent.target_energy if intent else e,
            confidence=intent.confidence if intent else 0.0,
            information_density=float(clip_meta.get("information_density", 0.0)),
            motion_score=float(clip_meta.get("motion_score", 0.5)),
            motion_direction=candidate_motion_direction,
            loop_boundary=platform == "tiktok" and end >= target_duration,
            speed_factor=seg_speed_factor,
            repetition=is_repetition,
            mc_gender=active_gender,
            structure_label=structure_label,
            on_structure_boundary=on_structure_boundary,
            scratch=do_scratch,
            scratch_strength=scratch_event["strength"] if scratch_event else 0.0,
            scratch_direction=scratch_direction,
            dj_action=(dj_event["action"] if dj_event else "none"),
            smooth_stutter=is_smooth_stutter,
            audio_bpm=audio.bpm,
            fx=tuple(style.fx) if style else (),
            cut_style=cut_style_chosen,
            sync_type=sync_type_chosen,
        ))
        clip_dur = float(clip_meta.get("duration", 0.0))
        blocked_end = min(clip_dur, clip_in_point + seg_source_len) if clip_dur > 0 else (clip_in_point + seg_source_len)
        _add_blocked(clip_path, clip_in_point, blocked_end)
        usage_counts[clip_path] = usage_counts.get(clip_path, 0) + 1
        prev_active_gender = active_gender
        t = end

    return timeline


def _gender_match_boost(meta: dict, section_label: str, mc_gender: str) -> float:
    if mc_gender not in ("male", "female") or section_label == "low":
        return 0.0
    gender_vector = meta.get("gender_vector") or {}
    if gender_vector.get(mc_gender):
        return GENDER_BOOST_VOCAL
    return 0.0


def _pick_clip(song_vector: list, globe: dict, section_label: str, seg_len: float,
               blocked_ranges: dict, intent=None, usage_counts: dict = None,
               session_locked: set[str] | None = None,
               mc_gender: str = "unknown", song_mood_tags: list | None = None,
               song_style_weights: dict | None = None, extra_score_fn=None,
               prev_motion_direction: float | None = None, motion_streak: int = 0,
               source_len: float | None = None, precomputed_pool: list[PrecomputedClip] | None = None,
               fallback_pool: list[tuple[str, dict]] | None = None,
               prev_domain: str = "URBAN_STREET", audio_bpm: float = 120.0,
               learning_engine=None,
               section_visual_cues: list[str] | None = None,
               section_cluster_mask: int = 0,
               is_spitting: bool = False,
               is_dj_action: bool = False,
               dj_action_type: str = "none",
               active_story_tags: frozenset[str] | None = None,
               active_story_domain: str | None = None):
    """Optimierte Clip-Auswahl mit vorab berechneten semantischen Matches,
    2/3 Session-Pool-Sperre, Frische-Explorationsboni, Markov-Transitionen und
    Softmax-Temperatur-Sampling für maximale Clip-Vielfalt."""
    eff_len = source_len if source_len is not None else seg_len
    if usage_counts is None:
        usage_counts = db.total_uses_many(globe)

    if precomputed_pool is None:
        precomputed_pool, fallback_pool = precompute_candidates(
            globe, song_vector, mc_gender=mc_gender,
            song_mood_tags=song_mood_tags, song_style_weights=song_style_weights
        )

    target_energy = {"low": 0.2, "mid": 0.5, "high": 0.85}[section_label]
    intent_req_tags = set(intent.required_tags) if intent else set()
    intent_len = max(1, len(intent_req_tags)) if intent else 1

    apply_motion_flow = (MOTION_FLOW_CONTINUITY_ENABLED and prev_motion_direction is not None
                         and abs(prev_motion_direction) >= MOTION_FLOW_DIRECTION_THRESHOLD
                         and motion_streak < MOTION_FLOW_MAX_STREAK)
    if apply_motion_flow:
        span = max(1e-6, MOTION_FLOW_SLOW_CUT_SEC - MOTION_FLOW_FAST_CUT_SEC)
        tempo_weight = 1.0 - max(0.0, min(1.0, (seg_len - MOTION_FLOW_FAST_CUT_SEC) / span))
        prev_dir_pos = prev_motion_direction > 0
        abs_prev_dir = abs(prev_motion_direction)
        mf_base = MOTION_FLOW_CONTINUITY_BONUS * tempo_weight
    else:
        mf_base = 0.0
        prev_dir_pos = False
        abs_prev_dir = 0.0

    cxx_engine = cxx_accel.get_cxx_engine()
    c_matrix = getattr(precomputed_pool, "candidate_matrix", None)
    if c_matrix is None or len(c_matrix) != len(precomputed_pool):
        rows = [
            (i, c.duration, c.motion_score, c.motion_direction, c.face_score,
             c.semantic_match, c.pref_bonus, c.info_density, c.learned_leaf_bonus)
            for i, c in enumerate(precomputed_pool)
        ]
        c_matrix = np.array(rows, dtype=np.float32) if rows else np.empty((0, 9), dtype=np.float32)
        try:
            precomputed_pool.candidate_matrix = c_matrix  # type: ignore[attr-defined]
        except Exception:
            pass

    if len(c_matrix) > 0:
        raw_scores = cxx_engine.score_candidates_batch(
            c_matrix,
            target_energy=target_energy,
            target_duration=eff_len,
            motion_weight=1.0 - SEMANTIC_WEIGHT,
            semantic_weight=SEMANTIC_WEIGHT,
            pref_weight=1.0,
            density_weight=0.3 if intent else 0.0,
            prev_motion_dir=prev_motion_direction or 0.0,
            allow_still=False,
            check_continuity=apply_motion_flow
        )
        k = min(len(raw_scores), 512)
        top_indices = np.argpartition(raw_scores, -k)[-k:]
        top_indices = top_indices[np.argsort(-raw_scores[top_indices])]
        eval_pool = [precomputed_pool[i] for i in top_indices if raw_scores[i] > -500.0]
    else:
        eval_pool = precomputed_pool

    candidates = []
    for c in eval_pool:
        if c.duration < eff_len:
            continue
        if usage_counts.get(c.path, 0) >= MAX_CLIP_USES_TOTAL:
            continue

        clip_blocks = blocked_ranges.get(c.path)
        windows = (clip_blocks + list(c.bad_windows)) if clip_blocks and c.bad_windows else (clip_blocks or c.bad_windows)
        start_point = _pick_start_point(c.duration, eff_len, c.alt_starts, windows)
        if start_point is None:
            continue

        energy_score = 1.0 - abs(target_energy - c.motion_score)
        sim = SEMANTIC_WEIGHT * c.semantic_match + (1.0 - SEMANTIC_WEIGHT) * energy_score

        if intent:
            tag_overlap_score = len(c.tags_set & intent_req_tags) / intent_len
            if song_vector:
                tag_score = 0.5 * tag_overlap_score + 0.5 * c.vector_sim_raw
            else:
                tag_score = tag_overlap_score
            intent_energy_score = 1.0 - abs(c.motion_score - intent.target_energy)
            density_score = 1.0 - abs(c.info_density - intent.target_information)
            structural_score = 0.4 * tag_score + 0.3 * intent_energy_score + 0.3 * density_score
            sim = 0.7 * sim + 0.3 * structural_score

        score = sim
        if section_label == "mid" and c.face_score > 0.4:
            score += FACE_BOOST_VOCAL
        score += c.pref_bonus
        score += c.learned_leaf_bonus

        # ── Vielfalts-Boni & Frische-Exploration ─────────────────────────────
        clip_uses = usage_counts.get(c.path, 0)
        if clip_uses == 0:
            score += DIVERSITY_EXPLORATION_BONUS
        elif clip_uses > 1:
            score -= min(0.35, DIVERSITY_USAGE_PENALTY_WEIGHT * math.log(1.0 + clip_uses))

        if prev_domain and c.domain != prev_domain:
            score += DIVERSITY_DOMAIN_SWITCH_BONUS

        # ── Section-spezifisches Lyrics- & Visual-Object Grounding ────────────
        if section_visual_cues:
            c_terms = c.tags_set
            cue_hit = False
            for cue in section_visual_cues:
                if cue.lower() in c_terms:
                    cue_hit = True
                    break
                vocab_words = VISUAL_SCENE_VOCAB.get(cue, [])
                if any(w.lower() in c_terms for w in vocab_words):
                    cue_hit = True
                    break
            if cue_hit:
                score += 0.25

        if section_cluster_mask:
            clip_mask = compute_cluster_mask(c.tags_set)
            if clip_mask & section_cluster_mask:
                score += 0.15

        # ── Storytelling & Motiv-Gruppierung (thematische Kohärenz im Clip-Pool) ──
        if active_story_tags:
            tag_overlap = len(c.tags_set & active_story_tags) / max(1, len(active_story_tags))
            domain_match = 1.0 if (active_story_domain and c.domain == active_story_domain) else 0.0
            cluster_coherence = 0.65 * tag_overlap + 0.35 * domain_match
            if cluster_coherence >= 0.15:
                score += STORY_CLUSTER_BONUS * STORY_CLUSTER_STICKINESS * min(1.5, cluster_coherence / 0.4)

        # ── Dynamisches Gender-Alignment (M, F, Duette, Flip-Flop) ───────────
        if mc_gender and mc_gender in ("male", "female", "dual"):
            c_gvec = c.meta.get("gender_vector") or {}
            c_has_fem = bool(c_gvec.get("female"))
            c_has_mal = bool(c_gvec.get("male"))
            c_faces = int(c.meta.get("face_score", 0.0) > 0.4) + len(c.meta.get("faces") or [])

            if mc_gender == "female":
                if c_has_fem and not c_has_mal:
                    score += 0.28
                elif c_has_fem and c_has_mal:
                    score += 0.15
                elif c_has_mal and not c_has_fem:
                    score -= 0.35
            elif mc_gender == "male":
                if c_has_mal and not c_has_fem:
                    score += 0.28
                elif c_has_mal and c_has_fem:
                    score += 0.15
                elif c_has_fem and not c_has_mal:
                    score -= 0.35
            elif mc_gender == "dual":
                if (c_has_fem and c_has_mal) or c_faces >= 2:
                    score += 0.35
                elif c_has_fem or c_has_mal:
                    score += 0.18

        # ── LibSync MC Rapper Spitting & Performance Bonus ───────────────────
        if is_spitting:
            score += LIBSYNC_PERFORMANCE_BOOST * c.spitting_score
            if c.face_score > 0.4:
                score += 0.15  # Close-Up / Performance-Fokus während Spitting-Bursts

        # ── DJ Sync Action Bonus (Scratch, Backspin, Vinyl, Drops, Beat Juggle) ──
        if is_dj_action:
            score += DJ_SYNC_ACTION_BOOST * c.dj_action_score

        # ── Dual-Frame Highlight Bonus (Start/End-Bilder, 6s-Clip-Pool, 140 BPM) ──
        # HIGH (>0.80) = USE → +0.18 starker Vorzug für visuell hochwertige Clips
        # MID (0.60-0.80) = MAYBE → +0.06 leichter Boost
        # LOW (<0.60) = SKIP → dezenter Malus -0.08 (SKIP-Clips kommen nur als Fallback)
        hl = c.highlight_score
        if hl >= 0.80:
            score += 0.18
        elif hl >= 0.60:
            score += 0.06
        else:
            score -= 0.08

        # 2/3 Session-Pool Sperre
        if session_locked and c.path in session_locked:
            score -= 5.0

        # Markov Transition Flow Learning
        if learning_engine and prev_domain:
            same_dir = (prev_dir_pos == (c.motion_direction > 0)) if apply_motion_flow else True
            flow_bonus = learning_engine.get_transition_flow_bonus(prev_domain, c.domain, same_motion_direction=same_dir)
            score += flow_bonus

        # Audio BPM & Mood Resonance Learning
        if learning_engine and audio_bpm > 0:
            res_bonus = learning_engine.get_audio_resonance_bonus(audio_bpm, list(c.tags_set))
            score += res_bonus

        if mf_base > 0.0 and abs(c.motion_direction) >= MOTION_FLOW_DIRECTION_THRESHOLD:
            alignment = 1.0 if prev_dir_pos == (c.motion_direction > 0) else -1.0
            strength = min(abs_prev_dir, abs(c.motion_direction))
            score += mf_base * alignment * strength

        if extra_score_fn is not None:
            score += extra_score_fn(c.meta)

        candidates.append((score, c.path, start_point, c.domain))

    if not candidates:
        for c in precomputed_pool:
            if c.duration < eff_len:
                continue
            if usage_counts.get(c.path, 0) >= MAX_CLIP_USES_TOTAL:
                continue
            clip_blocks = blocked_ranges.get(c.path)
            windows = (clip_blocks + list(c.bad_windows)) if clip_blocks and c.bad_windows else (clip_blocks or c.bad_windows)
            start_point = _pick_start_point(c.duration, eff_len, c.alt_starts, windows)
            if start_point is None:
                continue
            candidates.append((c.semantic_match, c.path, start_point, c.domain))

    if not candidates:
        all_clips = [(c.path, c.duration, c.alt_starts, c.bad_windows, c.semantic_match, c.domain) for c in precomputed_pool]
        if fallback_pool:
            for p, m in fallback_pool:
                dur = float(m.get("duration", 0.0))
                alts = [float(s) for s in m.get("alternative_start_points", []) if isinstance(s, (int, float))]
                bads = tuple((float(br.get("start", 0.0)), float(br.get("end", 0.0))) for br in (m.get("bad_frame_ranges") or []))
                all_clips.append((p, dur, alts, bads, 0.5, "URBAN_STREET"))

        for path, duration, alt_starts, bad_windows, sem_match, dom in all_clips:
            if duration <= 0:
                continue
            clip_blocks = blocked_ranges.get(path)
            windows = (clip_blocks + list(bad_windows)) if clip_blocks and bad_windows else (clip_blocks or bad_windows)
            start_point = _pick_start_point(duration, eff_len, alt_starts, windows)
            if start_point is None:
                start_point = 0.0
            candidates.append((sem_match, path, start_point, dom))

    if not candidates:
        raise RuntimeError(
            "Keine verwendbaren Clips im Pool (alle als 'failed' markiert oder Globe leer). "
            "Prüfe die [clip_pool]-Fehlermeldungen im Log."
        )

    candidates.sort(key=lambda c: c[0], reverse=True)
    top_k = candidates[: min(len(candidates), max(4, len(candidates) // 6))]

    if len(top_k) == 1:
        chosen = top_k[0]
    else:
        scores = np.array([c[0] for c in top_k], dtype=np.float64)
        temp = max(0.1, DIVERSITY_TEMPERATURE)
        scores = (scores - np.max(scores)) / temp
        exp_scores = np.exp(scores)
        sum_exp = np.sum(exp_scores)
        if sum_exp > 0:
            probs = exp_scores / sum_exp
            probs = probs / np.sum(probs)
            chosen_idx = np.random.choice(len(top_k), p=probs)
            chosen = top_k[chosen_idx]
        else:
            chosen = top_k[0]

    return chosen[1], chosen[2], chosen[3]


