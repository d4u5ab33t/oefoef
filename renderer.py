"""
renderer.py — DIRECT SUBPROCESS FFMPEG, kein moviepy/ffmpeg-python Wrapper.
"""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import hardware
from config import (ASPECT_FILL_THRESHOLD, AUDIO_MASTER_CLIP_ENABLED,
                     AUDIO_MASTER_CLIP_THRESHOLD, AUDIO_MASTER_COMP_ATTACK_MS,
                     AUDIO_MASTER_COMP_MAKEUP_DB, AUDIO_MASTER_COMP_RATIO,
                     AUDIO_MASTER_COMP_RELEASE_MS, AUDIO_MASTER_COMP_THRESH_DB,
                     AUDIO_MASTER_DEESS_ENABLED, AUDIO_MASTER_DEESS_FREQ,
                     AUDIO_MASTER_DEESS_INTENSITY, AUDIO_MASTER_DEESS_MAX,
                     AUDIO_MASTER_ENABLED, AUDIO_MASTER_HIGHPASS_HZ,
                     AUDIO_MASTER_SUBSONIC_HPF_HZ, AUDIO_MASTER_808_BOOST_HZ,
                     AUDIO_MASTER_808_BOOST_DB, AUDIO_MASTER_808_BOOST_WIDTH,
                     AUDIO_MASTER_MUD_CUT_HZ, AUDIO_MASTER_MUD_CUT_DB,
                     AUDIO_MASTER_MUD_CUT_WIDTH, AUDIO_MASTER_SUNO_DEHARSH_HZ,
                     AUDIO_MASTER_SUNO_DEHARSH_DB, AUDIO_MASTER_SUNO_DEHARSH_WIDTH,
                     AUDIO_MASTER_HF_AIR_HZ, AUDIO_MASTER_HF_AIR_DB,
                     AUDIO_MASTER_LIMITER_CEILING, AUDIO_MASTER_MS_ENABLED,
                     AUDIO_MASTER_MS_LOWCUT_HZ, AUDIO_MASTER_MS_SIDE_SHELF_DB,
                     AUDIO_MASTER_MS_SIDE_SHELF_HZ, AUDIO_MASTER_SATURATION_DRIVE_DB,
                     AUDIO_MASTER_SATURATION_ENABLED, AUDIO_MASTER_SATURATION_MAKEUP_DB,
                     AUDIO_MASTER_TARGET_LRA, AUDIO_MASTER_TARGET_LUFS,
                     AUDIO_MASTER_TARGET_LUFS_BY_STYLE,
                     AUDIO_MASTER_TARGET_TP, AUDIO_MASTER_VOCAL_PRESENCE_DB,
                     AUDIO_MASTER_VOCAL_PRESENCE_HZ, AUDIO_MASTER_VOCAL_PRESENCE_WIDTH_OCT,
                     AUDIO_MASTER_VOCAL_DUCK_ENABLED, AUDIO_MASTER_VOCAL_DUCK_THRESHOLD_DB,
                     AUDIO_MASTER_VOCAL_DUCK_RATIO, AUDIO_MASTER_VOCAL_DUCK_ATTACK_MS,
                     AUDIO_MASTER_VOCAL_DUCK_RELEASE_MS, AUDIO_MASTER_VOCAL_DUCK_MAKEUP_DB,
                     BEAT_DANCE_AMPLITUDE, BEAT_DANCE_DOWNBEAT_BOOST,
                     BEAT_DANCE_ENABLED, BEAT_DANCE_POWER_EXPONENT,
                     BEAT_DANCE_SWAY_AMPLITUDE,
                     CAMERA_ELASTIC_DECAY, CAMERA_ELASTIC_OVERSHOOT_CYCLES,
                     CAMERA_ENABLED, CAMERA_FOLLOW_MOTION_DIRECTION,
                     CAMERA_HEADROOM, CAMERA_MC_MOTION_DAMPENING, CAMERA_MIN_SEGMENT_SEC,
                     CAMERA_MOTION_FOLLOW_STRENGTH,
                     CAMERA_PERSPECTIVE_ENABLED, CAMERA_PERSPECTIVE_STRENGTH,
                     CAMERA_RUBBER_BAND_ENABLED, CAMERA_RUBBER_CYCLES_CHOICES,
                     CAMERA_RUBBER_DAMPING, CAMERA_RUBBER_PAN_RIPPLE_FRACTION,
                     CRF, CUT_STYLE_BREAK_ZOOM_DAMPEN, CUT_STYLE_DISSOLVE_ENABLED,
                     CUT_STYLE_DISSOLVE_SEC, CUT_STYLE_PUSH_ZOOM_BOOST,
                     CUT_STYLE_WHIP_FORCE_PUSH, DRIFT_ZOOM_TARGET, ENCODE_PRESET,
                     FADE_OUT_AUDIO_SEC, FADE_OUT_VIDEO_SEC, FFMPEG_BIN,
                     HOLD_SOFT_PUSH_BOOST_MAX, HOLD_SOFT_PUSH_TARGET,
                     HOLD_STATIC_MOTION_MAX, LIBSYNC_CADENCE_ZOOM_PULSE,
                     MAX_PAN_FRACTION, MIN_SEGMENT_SEC,
                     MOTION_DIRECTION_THRESHOLD, OUTPUT_FPS, OUTPUT_RESOLUTION,
                     OUTPUT_RESOLUTION_BY_PLATFORM,
                     PUSH_FADE_PUSH_FRACTION, PUSH_FADE_SEC, PUSH_FADE_XFADE_SEC,
                     PUSH_ZOOM_TARGET, REPETITION_FLASH_COUNT, REPETITION_FLASH_PULSE_SEC,
                     REPETITION_FLASH_STRENGTH,
                     SMOOTH_STUTTER_DECAY, SMOOTH_STUTTER_ENABLED,
                     SMOOTH_STUTTER_MICRO_PULSES, SMOOTH_STUTTER_OPACITY,
                     SYNC_TYPE_BREATH_DAMPEN, SYNC_TYPE_SNAP_ZOOM_BOOST,
                     SCRATCH_AUDIO_DUR_SEC, SCRATCH_AUDIO_GAIN_DB, SCRATCH_ENABLED,
                     SCRATCH_VIDEO_FLICK_SEC,
                     SLIDE_TRANSITION_ENABLED,
                     SNAP_PUNCH_FRACTION, SNAP_ZOOM_TARGET, SPEED_RAMP_ENABLED,
                     SPEED_RAMP_FREEZE_PAD_MAX_SEC,
                     STYLE_COLOR_GRADE_ENABLED, STYLE_FX_RENDER_ENABLED,
                     FX_GRAIN_STRENGTH, FX_FLICKER_STRENGTH, FX_FLICKER_HZ, FX_CHROMA_SHIFT_PX,
                     TMP_DIR, USE_NVENC_IF_AVAIL, VIDEO_CODEC_CPU, VIDEO_CODEC_NVENC)
from timeline_builder import TimelineSegment


def _run_subprocess(cmd, **kwargs) -> subprocess.CompletedProcess:
    """Sicherer Subprocess-Runner mit UTF-8 & errors='replace'.
    Verhindert UnicodeDecodeError in _readerthread unter Windows wenn FFmpeg
    Sonderzeichen, Umlaute oder unvollständige Multibyte-Chunks auf stdout/stderr ausgibt.
    """
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    return subprocess.run(cmd, **kwargs)


_DIMS_CACHE: dict[str, tuple[int, int] | None] = {}
_DIMS_CACHE_LOCK = __import__("threading").Lock()


def _probe_dimensions(path: str) -> tuple[int, int] | None:
    try:
        result = _run_subprocess(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", path],
            timeout=10,
        )
        w_str, h_str = result.stdout.strip().split("x")
        w, h = int(w_str), int(h_str)
        return (w, h) if w > 0 and h > 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _dims_cache_bulk(paths: set, globe: dict | None = None) -> dict:
    result: dict = {}
    missing = []
    with _DIMS_CACHE_LOCK:
        for path in paths:
            if path in _DIMS_CACHE:
                result[path] = _DIMS_CACHE[path]
            elif globe and path in globe:
                meta = globe[path]
                w = meta.get("width", 0)
                h = meta.get("height", 0)
                if w > 0 and h > 0:
                    _DIMS_CACHE[path] = (w, h)
                    result[path] = (w, h)
                else:
                    missing.append(path)
            else:
                missing.append(path)
    if not missing:
        return result
    max_workers = min(16, max(1, os.cpu_count() or 4))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_path = {pool.submit(_probe_dimensions, p): p for p in missing}
        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                dims = future.result()
            except Exception:
                dims = None
            result[path] = dims
    with _DIMS_CACHE_LOCK:
        _DIMS_CACHE.update(result)
    return result


def _nvenc_available() -> bool:
    if not USE_NVENC_IF_AVAIL:
        return False
    try:
        out = _run_subprocess([FFMPEG_BIN, "-hide_banner", "-encoders"], timeout=15)
        return "h264_nvenc" in out.stdout
    except Exception:
        return False


def _seeded_unit(*parts) -> float:
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return (int(digest[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0


def _seeded_choice(choices: list, *parts):
    unit = _seeded_unit(*parts)
    idx = int((unit + 1.0) / 2.0 * len(choices))
    idx = max(0, min(len(choices) - 1, idx))
    return choices[idx]


def _speed_ramp_prefix(speed_factor: float, duration: float, fps: int) -> str:
    if not SPEED_RAMP_ENABLED or abs(speed_factor - 1.0) < 1e-3:
        return ""
    speed_factor = max(0.5, min(2.0, speed_factor))
    if speed_factor > 1.0 and duration > SPEED_RAMP_FREEZE_PAD_MAX_SEC:
        max_speed_for_cap = duration / (duration - SPEED_RAMP_FREEZE_PAD_MAX_SEC)
        speed_factor = min(speed_factor, max_speed_for_cap)
    parts = [f"setpts=PTS/{speed_factor}", f"fps={fps}"]
    sped_up_len = duration / speed_factor
    return ",".join(parts) + ","


def _repetition_flash_suffix(repetition: bool, duration: float) -> str:
    if not repetition or duration <= 0:
        return ""
    n = max(1, REPETITION_FLASH_COUNT)
    pulse = max(0.01, min(REPETITION_FLASH_PULSE_SEC, duration / (n * 2)))
    terms = []
    for i in range(n):
        center = duration * (i + 0.5) / n
        terms.append(
            f"if(lt(abs(t-{center:.4f}),{pulse / 2:.4f}),"
            f"pow(cos(PI*(t-{center:.4f})/{pulse:.4f}),2),0)"
        )
    envelope = "+".join(terms) if len(terms) > 1 else terms[0]
    return f",eq=contrast='1+{REPETITION_FLASH_STRENGTH}*({envelope})':brightness='0.03*({envelope})':eval=frame"


def _color_grade_filter(lighting: str, color: str, force_enable: bool = False) -> str:
    if not STYLE_COLOR_GRADE_ENABLED and not force_enable:
        return ""
    eq_parts = []
    cb_parts = []

    # Lighting-Grading
    if lighting in ("lowkey", "dark", "shadowy"):
        eq_parts += ["brightness=-0.07", "contrast=1.20", "gamma=0.92"]
    elif lighting in ("highkey", "bright"):
        eq_parts += ["brightness=0.05", "contrast=0.95", "gamma=1.05"]
    elif lighting in ("dramatic", "chiaroscuro"):
        eq_parts += ["brightness=-0.04", "contrast=1.25", "gamma=0.90"]
    elif lighting in ("neon_backlight", "neon"):
        eq_parts += ["brightness=-0.02", "contrast=1.15", "gamma=0.96"]
    elif lighting == "strobe":
        eq_parts += ["contrast=1.30"]

    # Color-Grading
    if color in ("desaturated", "bw", "monochrome"):
        eq_parts.append("saturation=0.35")
    elif color in ("vivid", "saturated"):
        eq_parts.append("saturation=1.35")
    elif color in ("neon", "cyber"):
        eq_parts.append("saturation=1.45")
        cb_parts.append("colorbalance=rs=0.06:gs=-0.02:bs=0.08:rm=0.03:gm=-0.01:bm=0.05")
    elif color in ("warm", "golden_hour", "amber"):
        cb_parts.append("colorbalance=rs=0.08:gs=0.02:bs=-0.10:rm=0.05:gm=0.01:bm=-0.05:rh=0.04:bh=-0.04")
    elif color in ("cold_cyan", "cold", "teal_orange", "cyan"):
        cb_parts.append("colorbalance=rs=-0.06:gs=0.02:bs=0.08:rm=-0.04:gm=0.01:bm=0.06:rh=-0.03:bh=0.05")
    elif color in ("matrix_green", "green", "emerald"):
        cb_parts.append("colorbalance=rs=-0.04:gs=0.08:bs=-0.04:rm=-0.02:gm=0.06:bm=-0.02")
    elif color in ("vintage_film", "vintage", "retro"):
        eq_parts += ["contrast=1.08", "saturation=0.88", "gamma=1.06"]
        cb_parts.append("colorbalance=rs=0.05:gs=0.01:bs=-0.04:rm=0.02:gm=0.01:bm=-0.03")
    elif color in ("noir", "industrial"):
        eq_parts += ["contrast=1.35", "saturation=0.15", "brightness=-0.03"]

    filters = []
    if eq_parts:
        filters.append("eq=" + ":".join(eq_parts))
    if cb_parts:
        filters.extend(cb_parts)

    return ("," + ",".join(filters)) if filters else ""


def _semantic_motif_grade_filter(symbol: str, theme: str, force_enable: bool = False) -> str:
    """Wendet subtile, motiv-spezifische Farb- und Kontrast-Nuancen an,
    basierend auf der OIDA Visual DNA (BETON, EISBACH, 089, OIDA, CYBER, WEED, GRAFFITI)."""
    if not STYLE_COLOR_GRADE_ENABLED and not force_enable:
        return ""
    sym = (symbol or "").upper()
    thm = (theme or "").lower()

    parts = []
    if "BETON" in sym or "URBAN" in thm:
        # Kaltes Industrie-Grau mit punchigem Kontrast
        parts.append("colorbalance=rs=-0.03:gs=-0.01:bs=0.04:rm=-0.02:bm=0.03")
    elif "EISBACH" in sym or "ISAR" in sym or "WATER" in sym or "NATURE" in thm:
        # Frischer Aqua/Teal-Ton mit klarer Schärfe
        parts.append("colorbalance=rs=-0.05:gs=0.03:bs=0.06:rm=-0.03:gm=0.02:bm=0.05")
    elif "089" in sym or "OIDA" in sym or "BAVARIA" in sym:
        # Warmer Münchner Straßenkontrast mit sattem Schwarz
        parts.append("eq=contrast=1.05:brightness=-0.02:saturation=1.10")
        parts.append("colorbalance=rs=0.04:gs=0.01:bs=-0.03:rm=0.03:gm=0.01:bm=-0.02")
    elif "CYBER" in sym or "ROBOTER" in sym or "GLITCH" in sym or "TECH" in thm:
        # Cyberpunk Neon-Look (Teal/Magenta Akzentuierung)
        parts.append("colorbalance=rs=0.05:gs=-0.02:bs=0.06:rm=-0.03:gm=0.02:bm=0.05")
        parts.append("eq=contrast=1.12:saturation=1.18")
    elif "WEED" in sym or "420" in sym or "KUSH" in sym:
        # Weiches Smaragdgrün mit verträumtem Gamma
        parts.append("colorbalance=rs=-0.02:gs=0.05:bs=-0.02:rm=-0.01:gm=0.04:bm=-0.01")
        parts.append("eq=gamma=1.04:saturation=1.12")
    elif "GRAFFITI" in sym or "ART" in sym:
        # Hyper-sattes Farbspektrum
        parts.append("eq=contrast=1.08:saturation=1.28")

    return ("," + ",".join(parts)) if parts else ""


def _fx_filter(fx: tuple, duration: float) -> str:
    if not STYLE_FX_RENDER_ENABLED or not fx or duration <= 0:
        return ""
    parts = []
    if "grain" in fx or "film_grain" in fx:
        parts.append(f"noise=alls={FX_GRAIN_STRENGTH}:allf=t+u")
    if "flicker" in fx:
        parts.append(f"eq=brightness='{FX_FLICKER_STRENGTH}*sin(2*PI*{FX_FLICKER_HZ}*t)':eval=frame")
    if "chroma" in fx or "chromatic_aberration" in fx:
        parts.append(f"rgbashift=rh={FX_CHROMA_SHIFT_PX}:bh=-{FX_CHROMA_SHIFT_PX}")
    if "vignette" in fx:
        parts.append("vignette=PI/4")
    if "scanlines" in fx:
        parts.append("drawgrid=w=iw:h=4:t=1:c=black@0.12")
    if "halate" in fx or "glow" in fx:
        parts.append("unsharp=luma_msize_x=7:luma_msize_y=7:luma_amount=-0.5")
    # ── Eyecannndy VCAM & Visual Effect Techniques ───────────────────────────
    if "snorricam_strobe" in fx or "strobe_bw" in fx:
        parts.append("eq=contrast=1.6:saturation=0:brightness='0.12*sin(2*PI*10*t)':eval=frame")
    if "void_slitscan" in fx or "slitscan" in fx:
        parts.append("rgbashift=rh=6:bv=-5")
    if "coffin_crop" in fx or "overhead_coffin" in fx:
        parts.append("vignette=PI/2.6")
    if "tableau_hold" in fx:
        parts.append("eq=contrast=1.28:saturation=1.15")

    return ("," + ",".join(parts)) if parts else ""


def _apply_cut_sync_zoom_modifiers(camera_plan: dict | None, segment: TimelineSegment) -> dict | None:
    """Wendet die in config.py dokumentierte 'Cut-Style / Sync-Type Wiring'
    (CUT_STYLE_PUSH_ZOOM_BOOST/CUT_STYLE_BREAK_ZOOM_DAMPEN/
    SYNC_TYPE_SNAP_ZOOM_BOOST/SYNC_TYPE_BREATH_DAMPEN) tatsächlich auf den
    bereits von _plan_camera() geplanten Zoom-Hub (end_zoom - start_zoom) und
    Pan an. BUGFIX (Deep-Wiring-Audit Teil 2): main.py schreibt segment.
    cut_style/.sync_type zwar seit dem letzten Fix auf das TimelineSegment,
    aber renderer.py hat diese Felder bis hierher nirgends gelesen -- die
    komplette 'Cut-Style/Sync-Type Wiring'-Sektion in config.py war trotz
    gegenteiliger Kommentare ("Der Renderer nutzt sie hier...") totes
    Konfigurations-Vokabular ohne jeden Effekt auf das Bild. Modifiziert
    camera_plan in-place und gibt es zurück (None bleibt None)."""
    if camera_plan is None:
        return None
    start_zoom = camera_plan["start_zoom"]
    hub = camera_plan["end_zoom"] - start_zoom

    if segment.sync_type == "breath":
        hub *= SYNC_TYPE_BREATH_DAMPEN
        camera_plan["pan_x"] = camera_plan.get("pan_x", 0.0) * SYNC_TYPE_BREATH_DAMPEN
        camera_plan["pan_y"] = camera_plan.get("pan_y", 0.0) * SYNC_TYPE_BREATH_DAMPEN
    elif segment.sync_type == "lip_sync":
        hub *= LIBSYNC_CADENCE_ZOOM_PULSE
        camera_plan["pan_x"] = camera_plan.get("pan_x", 0.0) * 0.5
        camera_plan["pan_y"] = camera_plan.get("pan_y", 0.0) * 0.5
    elif segment.cut_style == "push":
        hub *= CUT_STYLE_PUSH_ZOOM_BOOST
    elif segment.cut_style == "break":
        hub *= CUT_STYLE_BREAK_ZOOM_DAMPEN

    if segment.sync_type in ("snap_drop", "energy_peak") and camera_plan.get("movement") == "snap":
        hub *= SYNC_TYPE_SNAP_ZOOM_BOOST

    # Nach Boost/Dampen-Stacking (z.B. push + snap gleichzeitig) auf einen
    # sinnvollen Bereich clampen, damit kein unbrauchbar harter oder
    # unsichtbar schwacher Zoom entsteht.
    hub = max(-0.5, min(0.5, hub))
    camera_plan["end_zoom"] = max(start_zoom, start_zoom + hub)  # zoom nie unter start_zoom (zoompan: z < 1.0 → schwarze Ränder)
    return camera_plan


def _plan_camera(segment: TimelineSegment, duration: float,
                 src_dims, w: int = None, h: int = None) -> dict | None:
    """Dünner Wrapper um _plan_camera_raw(): wendet _apply_cut_sync_zoom_modifiers()
    auf JEDEN Rückgabepfad an, ohne die vielen einzelnen return-Stellen unten
    anfassen zu müssen."""
    plan = _plan_camera_raw(segment, duration, src_dims, w, h)
    if plan is not None:
        plan["bpm"] = float(getattr(segment, "audio_bpm", 120.0) or 120.0)
    return _apply_cut_sync_zoom_modifiers(plan, segment)


def _plan_camera_raw(segment: TimelineSegment, duration: float,
                     src_dims, w: int = None, h: int = None) -> dict | None:
    if not CAMERA_ENABLED or duration < CAMERA_MIN_SEGMENT_SEC:
        return None

    if w is None or h is None:
        w, h = OUTPUT_RESOLUTION
    target_ar = w / h
    needs_fill = False
    if src_dims:
        src_w, src_h = src_dims
        if src_w > 0 and src_h > 0:
            src_ar = src_w / src_h
            if abs(src_ar - target_ar) / target_ar > ASPECT_FILL_THRESHOLD:
                needs_fill = True

    movement = segment.camera if segment.camera in ("push", "snap", "drift", "hold", "focus_zoom", "back_spin", "dominance", "chaos", "intelligence", "explosion", "pull", "whip_pan_dolly", "snorricam", "overhead", "worms_eye") else "drift"
    soft_hold_push = movement == "hold" and segment.motion_score < HOLD_STATIC_MOTION_MAX

    if not needs_fill and movement == "hold" and not soft_hold_push:
        # Lebendiger, subtiler Drift gegen Standbild-Gefühl
        pan_seed = _seeded_unit(segment.clip_path, segment.clip_in_point, "pan")
        subtle_pan = pan_seed * MAX_PAN_FRACTION * 0.15
        rubber_cycles = _seeded_choice(CAMERA_RUBBER_CYCLES_CHOICES, segment.clip_path,
                                        segment.clip_in_point, "rubber")
        mc_damp = max(0.2, 1.0 - CAMERA_MC_MOTION_DAMPENING * segment.motion_score)
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": HOLD_SOFT_PUSH_TARGET,
                "punch_fraction": None, "pan_x": subtle_pan, "pan_y": 0.0,
                "direction": _pan_direction(subtle_pan), "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}

    pan_seed = _seeded_unit(segment.clip_path, segment.clip_in_point, "pan")
    if CAMERA_FOLLOW_MOTION_DIRECTION and abs(segment.motion_direction) >= MOTION_DIRECTION_THRESHOLD:
        pan_unit = (CAMERA_MOTION_FOLLOW_STRENGTH * segment.motion_direction
                    + (1.0 - CAMERA_MOTION_FOLLOW_STRENGTH) * pan_seed)
        pan_unit = max(-1.0, min(1.0, pan_unit))
    else:
        pan_unit = pan_seed
    pan_x = pan_unit * MAX_PAN_FRACTION

    rubber_cycles = _seeded_choice(CAMERA_RUBBER_CYCLES_CHOICES, segment.clip_path,
                                    segment.clip_in_point, "rubber")
    mc_damp = max(0.2, 1.0 - CAMERA_MC_MOTION_DAMPENING * segment.motion_score)

    if movement == "whip_pan_dolly":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": 1.25,
                "punch_fraction": 0.20, "pan_x": pan_x * 1.6, "pan_y": 0.0,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles * 1.8, "mc_damp": mc_damp}
    if movement == "snorricam":
        return {"movement": movement, "start_zoom": 1.05, "end_zoom": 1.05,
                "punch_fraction": None, "pan_x": pan_x * 0.1, "pan_y": 0.02,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles, "mc_damp": 0.2}
    if movement == "overhead":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": 1.10,
                "punch_fraction": None, "pan_x": 0.0, "pan_y": -0.06,
                "direction": 0, "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}
    if movement == "worms_eye":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": 1.12,
                "punch_fraction": None, "pan_x": pan_x * 0.3, "pan_y": 0.08,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}

    if movement == "dominance":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": PUSH_ZOOM_TARGET,
                "punch_fraction": None, "pan_x": pan_x * 0.25, "pan_y": 0.05,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}
    if movement == "chaos":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": 1.08,
                "punch_fraction": None, "pan_x": pan_x, "pan_y": 0.05,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles * 2.5, "mc_damp": 0.5}
    if movement == "intelligence":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": DRIFT_ZOOM_TARGET,
                "punch_fraction": None, "pan_x": pan_x * 0.4, "pan_y": 0.02,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}
    if movement == "explosion":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": SNAP_ZOOM_TARGET,
                "punch_fraction": SNAP_PUNCH_FRACTION, "pan_x": pan_x * 0.3, "pan_y": 0.0,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}
    if movement == "push":
        pan_x = pan_x * 0.3
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": PUSH_ZOOM_TARGET,
                "punch_fraction": None, "pan_x": pan_x, "pan_y": 0.0,
                "direction": _pan_direction(pan_x),
                "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}
    if movement == "snap":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": SNAP_ZOOM_TARGET,
                "punch_fraction": SNAP_PUNCH_FRACTION, "pan_x": pan_x * 0.2, "pan_y": 0.0,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}
    if movement == "pull":
        return {"movement": movement, "start_zoom": PUSH_ZOOM_TARGET, "end_zoom": 1.0,
                "punch_fraction": None, "pan_x": pan_x * 0.3, "pan_y": 0.0,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}

    if movement == "focus_zoom":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": 1.08,
                "punch_fraction": 0.15, "pan_x": pan_x * 0.2, "pan_y": 0.0,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}
    if movement == "back_spin":
        return {"movement": movement, "start_zoom": 1.06, "end_zoom": 1.0,
                "punch_fraction": None, "pan_x": pan_x * 0.5, "pan_y": 0.0,
                "direction": _pan_direction(pan_x), "rubber_cycles": rubber_cycles * 1.5, "mc_damp": mc_damp}

    if movement == "drift":
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": DRIFT_ZOOM_TARGET,
                "punch_fraction": None, "pan_x": pan_x * 0.5, "pan_y": 0.0,
                "direction": _pan_direction(pan_x),
                "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}

    if soft_hold_push:
        staticness = 1.0 - max(0.0, min(1.0, segment.motion_score / HOLD_STATIC_MOTION_MAX))
        boost = 1.0 + staticness * (HOLD_SOFT_PUSH_BOOST_MAX - 1.0)
        target_zoom = 1.0 + (HOLD_SOFT_PUSH_TARGET - 1.0) * boost
        # Sanfte minimale Pan-Bewegung gegen Standbild-Gefuehl
        subtle_pan = pan_x * 0.15 if abs(pan_x) > 1e-4 else 0.02
        return {"movement": movement, "start_zoom": 1.0, "end_zoom": target_zoom,
                "punch_fraction": None, "pan_x": subtle_pan, "pan_y": 0.0,
                "direction": _pan_direction(subtle_pan),
                "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}
    return {"movement": movement, "start_zoom": 1.0, "end_zoom": DRIFT_ZOOM_TARGET,
            "punch_fraction": None, "pan_x": pan_x * 0.2, "pan_y": 0.0, "direction": _pan_direction(pan_x),
            "rubber_cycles": rubber_cycles, "mc_damp": mc_damp}


def _pan_direction(pan_x: float) -> int:
    if pan_x > 1e-4:
        return 1
    if pan_x < -1e-4:
        return -1
    return 0


def _round_even(value: float) -> int:
    n = int(round(value))
    return n if n % 2 == 0 else n + 1


def _smooth_stutter_filter(smooth_stutter: bool, duration: float) -> str:
    """Erzeugt einen dezenten, fließenden Highlight-Stutter auf musikalische Akzente
    (DJ-Scratching, Rolls, Drops) ohne störendes Flackern."""
    if not SMOOTH_STUTTER_ENABLED or not smooth_stutter or duration <= 0:
        return ""
    n = max(2, SMOOTH_STUTTER_MICRO_PULSES)
    pulses = []
    for i in range(n):
        p_time = 0.05 * (i + 1)
        pulses.append(f"if(lt(abs(t-{p_time:.3f}),0.025),{SMOOTH_STUTTER_OPACITY}*exp(-{i}*0.7),0)")
    env = "+".join(pulses)
    return f",eq=contrast='1+{env}':brightness='0.02*({env})':eval=frame"


def _zoompan_filter(camera_plan: dict, duration: float, fps: int, w: int, h: int) -> str:
    total_frames = max(1, round(duration * fps))
    start_zoom = camera_plan["start_zoom"]
    end_zoom = camera_plan["end_zoom"]
    punch_fraction = camera_plan.get("punch_fraction")
    pan_x = camera_plan.get("pan_x", 0.0)
    pan_y = camera_plan.get("pan_y", 0.0)
    rubber_cycles = camera_plan.get("rubber_cycles", 2.0)
    mc_damp = camera_plan.get("mc_damp", 1.0)
    bpm = float(camera_plan.get("bpm", 120.0) or 120.0)

    # Dezent halten: VCam soll die Bewegung im Clip geschmeidig und organisch
    # unterstützen, wie eine hochwertige Steadicam / Cine-Gimbal-Fahrt.
    pan_x = max(-0.28, min(0.28, pan_x))
    pan_y = max(-0.16, min(0.16, pan_y))

    t_expr = f"(on/{total_frames})"
    # Smoothstep-Kurve S(t) = 3t^2 - 2t^3 für fließende, cineastische Beschleunigung/Abbremsung
    smooth_t = f"(3*pow({t_expr},2)-2*pow({t_expr},3))"

    if punch_fraction:
        punch_frames = max(1, round(punch_fraction * total_frames))
        z_expr = (f"if(lte(on,{punch_frames}),"
                  f"{start_zoom}+({end_zoom}-{start_zoom})*on/{punch_frames},"
                  f"{end_zoom})")
    elif abs(end_zoom - start_zoom) > 1e-6:
        if CAMERA_RUBBER_BAND_ENABLED:
            ease = (f"(1-exp(-{CAMERA_ELASTIC_DECAY}*{t_expr})*"
                    f"cos(2*PI*{CAMERA_ELASTIC_OVERSHOOT_CYCLES}*{t_expr}))")
            z_expr = f"{start_zoom}+({end_zoom}-{start_zoom})*{ease}"
        else:
            z_expr = f"{start_zoom}+({end_zoom}-{start_zoom})*{smooth_t}"
    else:
        z_expr = f"{start_zoom}"

    # Beat-Dancing: Rhythmisches Bouncen & Atmen im Takt des Songs
    if BEAT_DANCE_ENABLED and bpm > 0:
        beat_hz = bpm / 60.0
        beat_pulse = f"({BEAT_DANCE_AMPLITUDE}*pow(max(0,cos(2*PI*{beat_hz:.3f}*({duration}*{t_expr}))),{BEAT_DANCE_POWER_EXPONENT}))"
        z_expr = f"({z_expr})*(1+{beat_pulse})"

    if camera_plan.get("movement") == "back_spin":
        pan_base = f"({pan_x})*sin(2*PI*2*{t_expr})*exp(-5*{t_expr})"
    else:
        pan_base = f"({pan_x})*({smooth_t}-0.5)"

    if CAMERA_RUBBER_BAND_ENABLED and abs(pan_x) > 1e-6:
        ripple_amp = pan_x * CAMERA_RUBBER_PAN_RIPPLE_FRACTION * mc_damp
        ripple = (f"+({ripple_amp:.6f})*exp(-{CAMERA_RUBBER_DAMPING}*{t_expr})*"
                  f"sin(2*PI*{rubber_cycles}*{t_expr})")
    else:
        ripple = ""

    if BEAT_DANCE_ENABLED and bpm > 0:
        sway_hz = (bpm / 60.0) / 2.0
        sway = f"+({BEAT_DANCE_SWAY_AMPLITUDE})*sin(2*PI*{sway_hz:.3f}*({duration}*{t_expr}))"
    else:
        sway = ""

    margin_x = "(iw-iw/zoom)/2"
    margin_y = "(ih-ih/zoom)/2"
    # Autozoom-Void-Schutz: clip() verhindert strikt, dass die Kamera über
    # den sichtbaren Bildrand hinaus in schwarze Ränder oder ins Leere driftet.
    raw_x = f"{margin_x}*(1+2*({pan_base}{ripple}{sway}))"
    raw_y = f"{margin_y}*(1+2*(({pan_y})*({smooth_t}-0.5)))"
    x_expr = f"clip({raw_x},0,max(0,iw-iw/zoom))"
    y_expr = f"clip({raw_y},0,max(0,ih-ih/zoom))"

    return f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d=1:s={w}x{h}:fps={fps}"


def _perspective_filter(camera_plan: dict, duration: float, fps: int, w: int, h: int) -> str:
    """Erzeugt eine räumliche 2.5D / Fake-3D Perspektiven-Warping-Projektion
    mit echter Fluchtpunkt-Geometrie und Tiefenstaffelung."""
    if not CAMERA_PERSPECTIVE_ENABLED:
        return ""

    movement = camera_plan.get("movement", "drift")
    direction = camera_plan.get("direction", 0)
    pan_x = camera_plan.get("pan_x", 0.0)

    # Bei Snap/Explosion/Dominance: räumlicher 3D-Punch
    is_3d_impact = movement in ("snap", "explosion", "dominance")
    if not is_3d_impact and abs(pan_x) < 1e-4 and direction == 0:
        return ""

    total_frames = max(1, round(duration * fps))
    max_shift_x = CAMERA_PERSPECTIVE_STRENGTH * min(w, h) * (1.3 if is_3d_impact else 1.0)
    max_shift_y = max_shift_x * 0.55

    t_ratio = f"(on/{total_frames})"
    smooth_t = f"(3*pow({t_ratio},2)-2*pow({t_ratio},3))"
    amt_x = f"({max_shift_x:.3f}*{smooth_t})"
    amt_y = f"({max_shift_y:.3f}*{smooth_t})"

    if direction >= 0:
        # Kamera schwenkt nach rechts -> rechtes Bildfeld kommt nach vorne (Fake 3D Yaw), linkes weicht zurück
        x0 = f"{amt_x}"
        y0 = f"{amt_y}"
        x1 = f"W"
        y1 = f"-{amt_y}*0.3"
        x2 = f"-{amt_x}*0.4"
        y2 = f"H-{amt_y}"
        x3 = f"W+{amt_x}*0.3"
        y3 = f"H+{amt_y}*0.4"
    else:
        # Kamera schwenkt nach links -> linkes Bildfeld kommt nach vorne, rechtes weicht zurück
        x0 = f"-{amt_x}*0.3"
        y0 = f"-{amt_y}*0.3"
        x1 = f"W-{amt_x}"
        y1 = f"{amt_y}"
        x2 = f"-{amt_x}*0.3"
        y2 = f"H+{amt_y}*0.4"
        x3 = f"W+{amt_x}*0.4"
        y3 = f"H-{amt_y}"

    filters = [
        f"perspective=x0='{x0}':y0='{y0}':x1='{x1}':y1='{y1}':x2='{x2}':y2='{y2}':x3='{x3}':y3='{y3}':eval=frame:interpolation=linear"
    ]

    # Bei starken 3D-Impacts: 2.5D Tiefen-Krümmung für cineastischen Horizon-Pop
    if is_3d_impact:
        filters.append("lenscorrection=cx=0.5:cy=0.5:k1=-0.015:k2=0.005")

    return "," + ",".join(filters)



def _encode_segment(clip_path: str, clip_in: float, duration: float, vf: str,
                     out_path: Path, video_codec: str, use_nvenc: bool,
                     threads: int | None = None) -> bool:
    cmd = [FFMPEG_BIN, "-y", "-nostdin", "-stream_loop", "-1", "-ss", f"{clip_in:.3f}", "-i", clip_path,
           "-vf", vf, "-an", "-c:v", video_codec,
           "-pix_fmt", "yuv420p"]
    if use_nvenc:
        cmd += ["-preset", "p4", "-tune", "hq", "-rc", "vbr", "-cq", str(CRF), "-b:v", "0"]
    else:
        cmd += ["-crf", str(CRF), "-preset", ENCODE_PRESET]
    if threads:
        cmd += hardware.thread_ffmpeg_args(video_codec, threads)
    cmd += ["-t", f"{duration:.3f}", str(out_path)]
    result = _run_subprocess(cmd, timeout=180)
    return result.returncode == 0 and out_path.is_file()


def _build_push_fade_transition(prev_seg_path: Path, curr_seg_path: Path, out_path: Path,
                                duration: float, fps: int, w: int, h: int,
                                direction: str, video_codec: str = VIDEO_CODEC_CPU,
                                use_nvenc: bool = False) -> tuple[bool, str | None]:
    if not SLIDE_TRANSITION_ENABLED or duration < 0.10:
        return False, None
    work_dir = out_path.parent
    moving_tail = work_dir / f"{out_path.stem}_mtail.mp4"
    push_canvas = work_dir / f"{out_path.stem}_mpush.mp4"
    try:
        push_sec = min(PUSH_FADE_SEC, max(0.05, duration * 0.45))
        xfade_sec = min(PUSH_FADE_XFADE_SEC, max(0.025, push_sec * 0.6))
        grab = _run_subprocess(
            [FFMPEG_BIN, "-y", "-nostdin", "-sseof", f"-{push_sec:.3f}", "-i", str(prev_seg_path),
             "-t", f"{push_sec:.3f}", "-an", "-c:v", VIDEO_CODEC_CPU, "-crf", str(CRF),
             "-preset", "ultrafast", str(moving_tail)],
            timeout=30,
        )
        if grab.returncode != 0 or not moving_tail.is_file():
            reason = f"tail-grab: {(grab.stderr or '').strip()[-300:]}"
            return False, reason

        push_px = _round_even(w * PUSH_FADE_PUSH_FRACTION)
        canvas_w = w + push_px
        if direction == "left":
            pad_x = 0
            crop_x_expr = f"{push_px}*t/{push_sec:.3f}"
        else:
            pad_x = push_px
            crop_x_expr = f"{push_px}*(1-t/{push_sec:.3f})"
        fade_start = push_sec * 0.35
        fade_dur = push_sec * 0.65
        push_vf = (
            f"scale={w}:{h}:flags=lanczos,pad={canvas_w}:{h}:{pad_x}:0:color=black,"
            f"crop={w}:{h}:'{crop_x_expr}':0,"
            f"fade=t=out:st={fade_start:.3f}:d={fade_dur:.3f},format=yuv420p"
        )
        build_push = _run_subprocess(
            [FFMPEG_BIN, "-y", "-nostdin", "-i", str(moving_tail), "-vf", push_vf,
             "-r", str(fps), "-an", "-c:v", VIDEO_CODEC_CPU, "-crf", str(CRF),
             "-preset", "ultrafast", str(push_canvas)],
            timeout=30,
        )
        if build_push.returncode != 0 or not push_canvas.is_file():
            return False, f"push-canvas: {(build_push.stderr or '').strip()[-300:]}"

        xfade_cmd = [
            FFMPEG_BIN, "-y", "-nostdin", "-i", str(push_canvas), "-i", str(curr_seg_path),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fadeblack:duration={xfade_sec:.3f}:offset=0,"
            f"format=yuv420p",
            "-an", "-c:v", VIDEO_CODEC_CPU, "-crf", str(CRF), "-preset", "ultrafast",
            "-t", f"{duration:.3f}", str(out_path),
        ]
        result = _run_subprocess(xfade_cmd, timeout=60)
        if result.returncode != 0 or not out_path.is_file():
            return False, f"xfade: {(result.stderr or '').strip()[-300:]}"
        return True, None
    except Exception as e:
        return False, f"exception: {e}"
    finally:
        for tmp in (moving_tail, push_canvas):
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass


def _build_dissolve_transition(prev_seg_path: Path, curr_seg_path: Path, out_path: Path,
                               duration: float, fps: int, w: int, h: int) -> tuple[bool, str | None]:
    """cut_style=='dissolve': weicher Crossfade-Übergang statt Push/Fade
    (siehe config.py CUT_STYLE_DISSOLVE_ENABLED/CUT_STYLE_DISSOLVE_SEC).
    Nutzt das echte, bewegte Videomaterial am Ende des auslaufenden Segments
    (keine Standbilder/PNG-Freeze-Frames) und blendet es CUT_STYLE_DISSOLVE_SEC
    lang per echtem Crossfade ('fade') in den Anfang des aktuellen Segments über.
    Lässt segment_files[-1] unangetastet -- nur der Anfang des AKTUELLEN Segments
    wird ersetzt, Gesamtdauer bleibt duration."""
    if not CUT_STYLE_DISSOLVE_ENABLED or duration < 0.10:
        return False, None
    work_dir = out_path.parent
    moving_tail = work_dir / f"{out_path.stem}_dtail.mp4"
    try:
        dissolve_sec = min(CUT_STYLE_DISSOLVE_SEC, max(0.05, duration * 0.4))
        grab = _run_subprocess(
            [FFMPEG_BIN, "-y", "-nostdin", "-sseof", f"-{dissolve_sec:.3f}", "-i", str(prev_seg_path),
             "-t", f"{dissolve_sec:.3f}", "-an", "-c:v", VIDEO_CODEC_CPU, "-crf", str(CRF),
             "-preset", "ultrafast", str(moving_tail)],
            timeout=30,
        )
        if grab.returncode != 0 or not moving_tail.is_file():
            reason = f"dissolve-tail-grab: {(grab.stderr or '').strip()[-300:]}"
            return False, reason

        xfade_cmd = [
            FFMPEG_BIN, "-y", "-nostdin", "-i", str(moving_tail), "-i", str(curr_seg_path),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={dissolve_sec:.3f}:offset=0,"
            f"format=yuv420p",
            "-an", "-c:v", VIDEO_CODEC_CPU, "-crf", str(CRF), "-preset", "ultrafast",
            "-t", f"{duration:.3f}", str(out_path),
        ]
        result = _run_subprocess(xfade_cmd, timeout=60)
        if result.returncode != 0 or not out_path.is_file():
            return False, f"dissolve-xfade: {(result.stderr or '').strip()[-300:]}"
        return True, None
    except Exception as e:
        return False, f"exception: {e}"
    finally:
        for tmp in (moving_tail,):
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass


def _build_scratch_transition(clip_path: str, clip_in: float, curr_seg_path: Path,
                              out_path: Path, duration: float, fps: int, w: int, h: int,
                              direction: str, video_codec: str, use_nvenc: bool) -> tuple[bool, str | None]:
    if not SCRATCH_ENABLED or duration <= SCRATCH_VIDEO_FLICK_SEC * 2:
        return False, None
    work_dir = out_path.parent
    flick_half = max(0.04, min(SCRATCH_VIDEO_FLICK_SEC / 2.0, duration * 0.25))
    fwd_path = work_dir / f"{out_path.stem}_flickfwd.mp4"
    rev_path = work_dir / f"{out_path.stem}_flickrev.mp4"
    combo_path = work_dir / f"{out_path.stem}_flickcombo.mp4"
    combo_list = work_dir / f"{out_path.stem}_flicklist.txt"
    try:
        flick_vf = f"scale={w}:{h}:flags=lanczos:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}"
        if not _encode_segment(clip_path, clip_in, flick_half, flick_vf,
                               fwd_path, VIDEO_CODEC_CPU, False):
            return False, "flick-forward: _encode_segment lieferte keinen Output (siehe ffmpeg-Aufruf in _encode_segment)"

        rev_cmd = [FFMPEG_BIN, "-y", "-nostdin", "-i", str(fwd_path), "-vf", "reverse",
                   "-an", "-c:v", VIDEO_CODEC_CPU, "-crf", str(CRF), "-preset", ENCODE_PRESET,
                   str(rev_path)]
        rev_result = _run_subprocess(rev_cmd, timeout=30)
        if rev_result.returncode != 0 or not rev_path.is_file():
            return False, f"flick-reverse: {(rev_result.stderr or '').strip()[-300:]}"

        order = (fwd_path, rev_path) if direction == "forward_back" else (rev_path, fwd_path)
        with open(combo_list, "w", encoding="utf-8") as f:
            for p in order:
                escaped = str(p.resolve()).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
        concat_cmd = [FFMPEG_BIN, "-y", "-nostdin", "-f", "concat", "-safe", "0",
                      "-i", str(combo_list), "-c", "copy", str(combo_path)]
        concat_result = _run_subprocess(concat_cmd, timeout=30)
        if concat_result.returncode != 0 or not combo_path.is_file():
            return False, f"concat: {(concat_result.stderr or '').strip()[-300:]}"

        xfade_dur = min(flick_half, 0.08)
        xfade_cmd = [
            FFMPEG_BIN, "-y", "-nostdin", "-i", str(combo_path), "-i", str(curr_seg_path),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fadeblack:duration={xfade_dur:.3f}:offset=0,"
            f"format=yuv420p",
            "-an", "-c:v", VIDEO_CODEC_CPU, "-crf", str(CRF), "-preset", ENCODE_PRESET,
            "-t", f"{duration:.3f}", str(out_path),
        ]
        result = _run_subprocess(xfade_cmd, timeout=60)
        if result.returncode != 0 or not out_path.is_file():
            return False, f"xfade: {(result.stderr or '').strip()[-300:]}"
        return True, None
    except Exception as e:
        return False, f"exception: {e}"
    finally:
        for tmp in (fwd_path, rev_path, combo_path, combo_list):
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass


def _build_scratch_audio_bed(scratch_times: list, song_path: str, work_dir: Path) -> Path | None:
    if not scratch_times:
        return None
    # Deckel auf max 16 Scratch-Stellen pro Song gegen Prozess-/Filter-Überlastung
    scratch_times = sorted(set(scratch_times))[:16]
    bed_path = work_dir / "scratch_audio_bed.m4a"
    filter_parts = []
    inputs = ["-i", song_path]
    for i, t in enumerate(scratch_times):
        start = max(0.0, t - SCRATCH_AUDIO_DUR_SEC / 2.0)
        inputs += ["-ss", f"{start:.3f}", "-t", f"{SCRATCH_AUDIO_DUR_SEC:.3f}", "-i", song_path]
        delay_ms = int(start * 1000)
        filter_parts.append(
            f"[{i + 1}:a]areverse,volume={SCRATCH_AUDIO_GAIN_DB}dB,"
            f"adelay={delay_ms}|{delay_ms}[scr{i}]"
        )
    mix_inputs = "[0:a]" + "".join(f"[scr{i}]" for i in range(len(scratch_times)))
    filter_complex = ";".join(filter_parts) + (";" if filter_parts else "") + (
        f"{mix_inputs}amix=inputs={len(scratch_times) + 1}:duration=first:"
        f"dropout_transition=0:normalize=0[aout]"
    )
    cmd = [FFMPEG_BIN, "-y", "-nostdin", *inputs, "-filter_complex", filter_complex,
           "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", str(bed_path)]
    try:
        result = _run_subprocess(cmd, timeout=120)
        return bed_path if result.returncode == 0 and bed_path.is_file() else None
    except Exception:
        return None


def _resolve_vocal_duck_stems(song_path: str) -> dict:
    """Liefert {vocals/drums/bass/other: Pfad} für song_path, NUR wenn eine
    ECHTE 4-Stem-Demucs-Trennung bereits im stems/-Cache liegt (siehe
    stem_separator.py). Der HPSS-Fallback liefert nur 2 Pseudo-Stems
    (vocals=harmonic INKLUSIVE Melodie/Synths, drums=percussiv) -- ein Duck
    auf Basis dieser Proxys würde Melodie-Instrumente fälschlich als "Vocal"
    behandeln und im Instrumental wegducken (siehe config.py
    AUDIO_MASTER_VOCAL_DUCK_*-Kommentar, "Gate prüft auf alle 4 Demucs-Stem-
    Keys"). Wirft nie -- fehlt stem_separator/das Modul, einfach kein Duck."""
    try:
        import stem_separator
    except Exception:
        return {}
    try:
        stems = stem_separator._existing_stems(song_path, stem_separator.DEMUCS_STEMS)
    except Exception:
        return {}
    return stems if set(stems) == set(stem_separator.DEMUCS_STEMS) else {}


def _build_vocal_duck_mix(stems: dict, work_dir: Path) -> Path | None:
    """Duckt drums+bass+other (amix zu einem Instrumental-Bus) sanft im Takt
    der vocals-Stem-Energie (sidechaincompress, Instrumental=Hauptsignal,
    Vocals=Sidechain-Key) und mischt beide danach wieder zusammen -- siehe
    config.py AUDIO_MASTER_VOCAL_DUCK_* und dortigen Feature-Kommentar."""
    out_path = work_dir / "vocal_duck_mix.m4a"
    cmd = [
        FFMPEG_BIN, "-y", "-nostdin",
        "-i", stems["vocals"], "-i", stems["drums"], "-i", stems["bass"], "-i", stems["other"],
        "-filter_complex",
        "[1:a][2:a][3:a]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0[instr];"
        f"[instr][0:a]sidechaincompress=threshold={AUDIO_MASTER_VOCAL_DUCK_THRESHOLD_DB}dB:"
        f"ratio={AUDIO_MASTER_VOCAL_DUCK_RATIO}:attack={AUDIO_MASTER_VOCAL_DUCK_ATTACK_MS}:"
        f"release={AUDIO_MASTER_VOCAL_DUCK_RELEASE_MS}:makeup={AUDIO_MASTER_VOCAL_DUCK_MAKEUP_DB}dB[instr_duck];"
        "[instr_duck][0:a]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]",
        "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", str(out_path),
    ]
    try:
        result = _run_subprocess(cmd, timeout=180)
        return out_path if result.returncode == 0 and out_path.is_file() else None
    except Exception:
        return None


def _master_audio(audio_path: str, work_dir: Path, _log,
                  song_path: str | None = None, target_lufs: float | None = None) -> str:
    if not AUDIO_MASTER_ENABLED:
        return audio_path

    # BUGFIX (Deep-Wiring-Audit Teil 3): AUDIO_MASTER_TARGET_LUFS_BY_STYLE
    # (config.py, dokumentiert mit explizitem Verweis auf DIESEN
    # `target_lufs`-Parameter) und AUDIO_MASTER_VOCAL_DUCK_* (config.py,
    # dokumentiert mit explizitem Verweis auf DIESE Funktion + das 4-Demucs-
    # Stem-Gate) waren beide importiert, aber nirgends in dieser Funktion
    # gelesen -- exakt dasselbe tote Konfigurations-Vokabular-Muster wie
    # Cut-Style/Sync-Type/Fade-Out vorher (siehe _apply_cut_sync_zoom_modifiers
    # und _render_into_workdir). target_lufs=None -> Default bleibt exakt wie
    # vorher (AUDIO_MASTER_TARGET_LUFS für alle Styles).
    if target_lufs is None:
        target_lufs = AUDIO_MASTER_TARGET_LUFS

    if AUDIO_MASTER_VOCAL_DUCK_ENABLED and song_path:
        stems = _resolve_vocal_duck_stems(song_path)
        if stems:
            duck_mix = _build_vocal_duck_mix(stems, work_dir)
            if duck_mix is not None:
                if audio_path != song_path:
                    _log("[renderer] Vocal-Duck aktiv: ersetzt Audioquelle durch Stem-Remix "
                         "(ein evtl. gemischtes Scratch-Audiobett entfällt dadurch für diesen Render, "
                         "da es nicht Teil der Stem-Trennung war).")
                else:
                    _log("[renderer] Vocal-Duck aktiv: Instrumental-Stems geduckt gegen Vocals-Energie.")
                audio_path = str(duck_mix)
            else:
                _log("[renderer] Vocal-Duck-Remix fehlgeschlagen, verwende unverändertes Audio.")

    measure_cmd = [
        FFMPEG_BIN, "-nostdin", "-i", audio_path,
        "-af", (f"loudnorm=I={target_lufs}:TP={AUDIO_MASTER_TARGET_TP}:"
                f"LRA={AUDIO_MASTER_TARGET_LRA}:print_format=json"),
        "-f", "null", "-",
    ]
    try:
        measured = _run_subprocess(measure_cmd, timeout=180)
        idx_key = measured.stderr.find('"input_i"')
        if idx_key != -1:
            json_start = measured.stderr.rfind("{", 0, idx_key)
            json_end = measured.stderr.find("}", idx_key)
        else:
            json_start = measured.stderr.find("{")
            json_end = measured.stderr.rfind("}")
        if json_start == -1 or json_end <= json_start:
            raise ValueError("Kein JSON-Block in loudnorm stderr gefunden")
        raw_json = measured.stderr[json_start:json_end + 1]
        # Guard: ffmpeg schreibt bei vollständiger Stille "-inf" als JSON-Wert (kein valides JSON).
        # Ersetze -inf/+inf durch 0 resp. sehr kleinen/großen Wert vor dem Parsen.
        raw_json = raw_json.replace("-inf", '"-999"').replace("+inf", '"0"').replace("inf", '"0"').replace("nan", '"0"')
        stats = json.loads(raw_json)
        # Sicherstellen dass alle Felder für loudnorm vorhanden und parseable sind.
        for key in ("input_i", "input_tp", "input_lra", "input_thresh"):
            val = stats.get(key, "0")
            try:
                float(val)
            except (TypeError, ValueError):
                stats[key] = "0"
    except Exception as e:
        _log(f"[renderer] Audio-Mastering: Messpass fehlgeschlagen ({e}), überspringe Mastering.")
        return audio_path

    mastered_path = work_dir / "mastered_audio.m4a"

    parts = [f"[0:a]highpass=f={AUDIO_MASTER_SUBSONIC_HPF_HZ},aformat=channel_layouts=stereo[hp]"]

    if AUDIO_MASTER_MS_ENABLED:
        parts.append("[hp]pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0-0.5*c1[ms]")
        parts.append("[ms]channelsplit=channel_layout=stereo[mid][side]")
        parts.append(
            f"[side]highpass=f={AUDIO_MASTER_MS_LOWCUT_HZ},"
            f"treble=f={AUDIO_MASTER_MS_SIDE_SHELF_HZ}:g={AUDIO_MASTER_MS_SIDE_SHELF_DB}[side_p]"
        )
        mid_in = "mid"
    else:
        mid_in = "hp"

    # Mid-Kanal Klangoptimierung: 808-Subbass-Punch (65Hz) + Mud-Cut (280Hz) +
    # Vocal-Präsenz (3.5kHz) + Suno AI De-Harshing (4.5kHz)
    mid_eq = (
        f"bass=f={AUDIO_MASTER_808_BOOST_HZ}:g={AUDIO_MASTER_808_BOOST_DB}:"
        f"width_type=o:width={AUDIO_MASTER_808_BOOST_WIDTH},"
        f"equalizer=f={AUDIO_MASTER_MUD_CUT_HZ}:width_type=o:"
        f"width={AUDIO_MASTER_MUD_CUT_WIDTH}:g={AUDIO_MASTER_MUD_CUT_DB},"
        f"equalizer=f={AUDIO_MASTER_VOCAL_PRESENCE_HZ}:width_type=o:"
        f"width={AUDIO_MASTER_VOCAL_PRESENCE_WIDTH_OCT}:g={AUDIO_MASTER_VOCAL_PRESENCE_DB},"
        f"equalizer=f={AUDIO_MASTER_SUNO_DEHARSH_HZ}:width_type=o:"
        f"width={AUDIO_MASTER_SUNO_DEHARSH_WIDTH}:g={AUDIO_MASTER_SUNO_DEHARSH_DB}"
    )
    parts.append(f"[{mid_in}]{mid_eq}[mid_eq]")
    vocal_out = "mid_eq"

    if AUDIO_MASTER_DEESS_ENABLED:
        parts.append(
            f"[mid_eq]deesser=i={AUDIO_MASTER_DEESS_INTENSITY}:f={AUDIO_MASTER_DEESS_FREQ}:"
            f"m={AUDIO_MASTER_DEESS_MAX}:s=o[mid_d]"
        )
        vocal_out = "mid_d"

    if AUDIO_MASTER_MS_ENABLED:
        parts.append(f"[{vocal_out}][side_p]amerge=inputs=2[ms_p]")
        parts.append("[ms_p]pan=stereo|c0=c0+c1|c1=c0-c1[bus]")
        bus = "bus"
    else:
        bus = vocal_out

    # Summen-Bus: HF-Air-Rekonstruktion (>12kHz) + Glue-Kompression + EBU R128 Loudnorm + Sättigung + Limiter
    tail = (
        f"treble=f={AUDIO_MASTER_HF_AIR_HZ}:g={AUDIO_MASTER_HF_AIR_DB},"
        f"acompressor=threshold={AUDIO_MASTER_COMP_THRESH_DB}dB:"
        f"ratio={AUDIO_MASTER_COMP_RATIO}:attack={AUDIO_MASTER_COMP_ATTACK_MS}:"
        f"release={AUDIO_MASTER_COMP_RELEASE_MS}:makeup={AUDIO_MASTER_COMP_MAKEUP_DB}dB,"
        f"loudnorm=I={target_lufs}:TP={AUDIO_MASTER_TARGET_TP}:"
        f"LRA={AUDIO_MASTER_TARGET_LRA}:"
        f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
        f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
        f"linear=true:print_format=summary"
    )
    if AUDIO_MASTER_SATURATION_ENABLED:
        tail += (
            f",volume={AUDIO_MASTER_SATURATION_DRIVE_DB}dB,asoftclip=type=tanh,"
            f"volume={AUDIO_MASTER_SATURATION_MAKEUP_DB}dB"
        )
    if AUDIO_MASTER_CLIP_ENABLED:
        tail += f",asoftclip=type=hard:threshold={AUDIO_MASTER_CLIP_THRESHOLD}"
    tail += f",alimiter=limit={AUDIO_MASTER_LIMITER_CEILING}:attack=5:release=50[aout]"
    parts.append(f"[{bus}]{tail}")

    filter_complex = ";".join(parts)
    cmd = [FFMPEG_BIN, "-y", "-nostdin", "-i", audio_path, "-filter_complex", filter_complex,
           "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", str(mastered_path)]
    try:
        result = _run_subprocess(cmd, timeout=180)
        if result.returncode == 0 and mastered_path.is_file():
            _log(f"[renderer] Audio-Mastering angewendet: Ziel {target_lufs} LUFS "
                 f"(gemessen vorher: {stats['input_i']} LUFS; 808-Boost={AUDIO_MASTER_808_BOOST_DB}dB@{AUDIO_MASTER_808_BOOST_HZ}Hz, "
                 f"Mud-Cut={AUDIO_MASTER_MUD_CUT_DB}dB@{AUDIO_MASTER_MUD_CUT_HZ}Hz, "
                 f"De-Harsh={AUDIO_MASTER_SUNO_DEHARSH_DB}dB@{AUDIO_MASTER_SUNO_DEHARSH_HZ}Hz, "
                 f"HF-Air=+{AUDIO_MASTER_HF_AIR_DB}dB@{AUDIO_MASTER_HF_AIR_HZ}Hz, "
                 f"M/S-Mono-Sub={AUDIO_MASTER_MS_LOWCUT_HZ}Hz, De-Ess={AUDIO_MASTER_DEESS_ENABLED}, "
                 f"Sättigung={AUDIO_MASTER_SATURATION_ENABLED}, Hard-Clip={AUDIO_MASTER_CLIP_ENABLED}).")
            return str(mastered_path)
        _log(f"[renderer] Audio-Mastering fehlgeschlagen (rc={result.returncode}), "
             f"unbearbeiteter Ton wird verwendet: {result.stderr[-400:]}")
        return audio_path
    except Exception as e:
        _log(f"[renderer] Audio-Mastering fehlgeschlagen ({e}), unbearbeiteter Ton wird verwendet.")
        return audio_path


def render_music_video(timeline: list, song_path: str, output_path: str, log=None,
                       platform: str = "full", metadata: dict | None = None,
                       globe: dict | None = None) -> str | None:
    def _log(msg: str):
        if log:
            log(msg)

    if not timeline:
        raise ValueError("Leere Timeline übergeben.")

    w, h = OUTPUT_RESOLUTION_BY_PLATFORM.get(platform, OUTPUT_RESOLUTION)
    _log(f"[renderer] Ziel-Auflösung: {w}x{h} (platform={platform}).")
    use_nvenc = _nvenc_available()
    video_codec = VIDEO_CODEC_NVENC if use_nvenc else VIDEO_CODEC_CPU
    _log(f"[renderer] Encoder: {video_codec} (NVENC={'ja' if use_nvenc else 'nein, CPU-Fallback'})")

    work_dir = TMP_DIR / Path(output_path).stem
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        return _render_into_workdir(timeline, song_path, output_path, work_dir,
                                     w, h, video_codec, use_nvenc, _log,
                                     metadata=metadata, globe=globe)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _plan_segment_filter(seg: TimelineSegment, duration: float, src_dims,
                         w: int, h: int, video_fade_sec: float = 0.0) -> str:
    # BUGFIX (Standbild am Clip-Ende): Quell-Clips liegen so gut wie nie exakt
    # auf OUTPUT_FPS (z.B. 23.976/24/25/50/60fps-Footage vs. festem Projekt-
    # Output). zoompan berechnet seine z/x/y-Ausdrücke gegen
    # total_frames=round(duration*OUTPUT_FPS) (siehe _zoompan_filter), zieht
    # sein Bildmaterial aber bei d=1 pro Output-Tick genau EIN neues Input-
    # Frame -- ohne vorherige CFR-Normalisierung auf OUTPUT_FPS laufen native
    # Frameanzahl und erwartete total_frames auseinander. Läuft der Clip
    # zuerst leer (typisch bei niedrigerer nativer fps als OUTPUT_FPS),
    # wiederholt zoompan intern das letzte dekodierte Frame für den Rest des
    # Segments -> sichtbares Standbild am Clip-Ende. Ein explizites
    # `fps=OUTPUT_FPS` VOR zoompan (bzw. direkt nach scale/crop im
    # kamera-losen Zweig, für saubere concat-Übergänge) erzwingt echte CFR-
    # Duplizierung/Verwerfung an genau dieser Stelle, sodass die Framezahl
    # danach exakt zu total_frames passt und kein Frame-Unterlauf mehr
    # auftreten kann.
    camera_plan = _plan_camera(seg, duration, src_dims, w, h)
    if camera_plan is None:
        vf = f"scale={w}:{h}:flags=lanczos:force_original_aspect_ratio=increase,crop={w}:{h},fps={OUTPUT_FPS}"
    else:
        canvas_w = _round_even(w * CAMERA_HEADROOM)
        canvas_h = _round_even(h * CAMERA_HEADROOM)
        pre = (f"scale={canvas_w}:{canvas_h}:flags=lanczos:force_original_aspect_ratio=increase,"
              f"crop={canvas_w}:{canvas_h},fps={OUTPUT_FPS}")
        vf = pre + "," + _zoompan_filter(camera_plan, duration, OUTPUT_FPS, w, h)
        vf = vf + _perspective_filter(camera_plan, duration, OUTPUT_FPS, w, h)

    vf = _speed_ramp_prefix(seg.speed_factor, duration, OUTPUT_FPS) + vf
    vf = vf + _repetition_flash_suffix(seg.repetition, duration)
    vf = vf + _color_grade_filter(seg.lighting, seg.color)
    vf = vf + _semantic_motif_grade_filter(seg.semantic_symbol, seg.theme)
    vf = vf + _fx_filter(seg.fx, duration)
    vf = vf + _smooth_stutter_filter(getattr(seg, "smooth_stutter", False), duration)
    # BUGFIX (Deep-Wiring-Audit Teil 2): FADE_OUT_VIDEO_SEC (config.py, "Dauer
    # des Bild-Ausblendens am allerletzten Segment (cut_style=='fade_out')")
    # war definiert, aber nirgends gelesen -- das letzte Segment endete bisher
    # immer hart, auch wenn main.py es via _calculate_cut_style() als
    # "fade_out" klassifiziert hatte.
    if video_fade_sec > 0 and duration > video_fade_sec:
        vf = vf + f",fade=t=out:st={duration - video_fade_sec:.3f}:d={video_fade_sec:.3f}"
    return vf


def _encode_one_segment(idx: int, seg: TimelineSegment, dims_cache: dict,
                        work_dir: Path, w: int, h: int, video_codec: str,
                        use_nvenc: bool, _log, threads: int | None = None,
                        video_fade_sec: float = 0.0) -> "tuple[int, Path | None]":
    duration = round(seg.end_sec - seg.start_sec, 3)
    if duration <= 0 or not seg.clip_path:
        return idx, None
    src_dims = dims_cache.get(seg.clip_path)
    vf = _plan_segment_filter(seg, duration, src_dims, w, h, video_fade_sec=video_fade_sec)

    seg_out = work_dir / f"seg_{idx:05d}.mp4"
    try:
        ok = _encode_segment(seg.clip_path, seg.clip_in_point, duration, vf,
                              seg_out, video_codec, use_nvenc, threads=threads)
    except Exception as e:
        _log(f"[renderer] Segment {idx}: Encode-Fehler/Timeout ({e}), versuche CPU-Fallback.")
        ok = False
    if not ok and use_nvenc:
        try:
            ok = _encode_segment(seg.clip_path, seg.clip_in_point, duration, vf,
                                  seg_out, VIDEO_CODEC_CPU, False, threads=threads)
        except Exception as e:
            _log(f"[renderer] Segment {idx}: CPU-Fallback ebenfalls fehlgeschlagen ({e}).")
            ok = False
    if not ok:
        _log(f"[renderer] Segment {idx} übersprungen (Encode fehlgeschlagen): {seg.clip_path}")
        try:
            import db
            db.purge_clip_entry(seg.clip_path, log=_log)
        except Exception:
            pass
        return idx, None
    return idx, seg_out



def render_silent_video(timeline: list, work_dir: Path, w: int, h: int,
                        video_codec: str, use_nvenc: bool, _log,
                        globe: dict | None = None) -> Path:
    unique_clip_paths = {seg.clip_path for seg in timeline if seg.clip_path}
    dims_cache: dict = _dims_cache_bulk(unique_clip_paths, globe=globe)

    max_workers, threads_per_worker = hardware.recommend_encode_plan(
        w, h, video_codec, ENCODE_PRESET, use_nvenc, log=_log)

    last_idx = len(timeline) - 1
    encoded: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_encode_one_segment, idx, seg, dims_cache, work_dir,
                       w, h, video_codec, use_nvenc, _log, threads=threads_per_worker,
                       video_fade_sec=(FADE_OUT_VIDEO_SEC if idx == last_idx and seg.cut_style == "fade_out" else 0.0))
            for idx, seg in enumerate(timeline)
        ]
        for future in concurrent.futures.as_completed(futures):
            idx, seg_out = future.result()
            if seg_out is not None:
                encoded[idx] = seg_out

    _log(f"[renderer] {len(encoded)}/{len(timeline)} Segmente parallel encodiert "
         f"(workers={max_workers}).")

    segment_files = []
    transition_count = len(encoded)
    for loop_pos, idx in enumerate(sorted(encoded), 1):
        if loop_pos % 20 == 0 or loop_pos == transition_count:
            _log(f"[renderer] Übergänge: {loop_pos}/{transition_count} Segmente verarbeitet...")
        seg = timeline[idx]
        seg_out = encoded[idx]
        duration = round(seg.end_sec - seg.start_sec, 3)

        prev_seg = timeline[idx - 1] if idx > 0 else None

        if seg.scratch and duration > max(SCRATCH_VIDEO_FLICK_SEC * 2, 0.5):
            scratched_out = work_dir / f"seg_{idx:05d}_scratch.mp4"
            scratch_ok, scratch_reason = _build_scratch_transition(
                seg.clip_path, seg.clip_in_point, seg_out,
                scratched_out, duration, OUTPUT_FPS, w, h,
                seg.scratch_direction, video_codec, use_nvenc)
            if scratch_ok:
                try:
                    seg_out.unlink(missing_ok=True)
                except Exception:
                    pass
                seg_out = scratched_out
            elif scratch_reason:
                _log(f"[renderer] Segment {idx}: Scratch-Cutaway fehlgeschlagen ({scratch_reason}), harter Schnitt beibehalten.")
        elif (CUT_STYLE_DISSOLVE_ENABLED and seg.cut_style == "dissolve"
                and segment_files and prev_seg is not None
                and duration >= 0.10):
            dissolved_out = work_dir / f"seg_{idx:05d}_dissolve.mp4"
            dissolve_ok, dissolve_reason = _build_dissolve_transition(
                segment_files[-1], seg_out, dissolved_out, duration, OUTPUT_FPS, w, h)
            if dissolve_ok:
                try:
                    seg_out.unlink(missing_ok=True)
                except Exception:
                    pass
                seg_out = dissolved_out
            elif dissolve_reason:
                _log(f"[renderer] Segment {idx}: Dissolve-Übergang fehlgeschlagen ({dissolve_reason}), harter Schnitt beibehalten.")
        elif (segment_files and prev_seg is not None and (
                (seg.transition in ("slide", "whip") and abs(prev_seg.motion_direction) >= MOTION_DIRECTION_THRESHOLD)
                or (CUT_STYLE_WHIP_FORCE_PUSH and seg.cut_style in ("whip", "push")))):
            direction = "left" if prev_seg.motion_direction < 0 else ("right" if prev_seg.motion_direction > 0 else ("left" if idx % 2 == 0 else "right"))
            pushed_out = work_dir / f"seg_{idx:05d}_push.mp4"
            push_ok, push_reason = _build_push_fade_transition(
                segment_files[-1], seg_out, pushed_out, duration, OUTPUT_FPS, w, h, direction,
                video_codec=video_codec, use_nvenc=use_nvenc)
            if push_ok:
                try:
                    seg_out.unlink(missing_ok=True)
                except Exception:
                    pass
                seg_out = pushed_out
            elif push_reason:
                _log(f"[renderer] Segment {idx}: Push/Fade-Übergang fehlgeschlagen ({push_reason}), harter Schnitt beibehalten.")

        segment_files.append(seg_out)

    if not segment_files:
        raise RuntimeError("Kein einziges Segment konnte gerendert werden.")

    concat_list = work_dir / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sf in segment_files:
            escaped = str(sf.resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    silent_video = work_dir / "video_only.mp4"
    concat_cmd = [FFMPEG_BIN, "-y", "-nostdin", "-f", "concat", "-safe", "0",
                  "-i", str(concat_list), "-c", "copy", str(silent_video)]
    result = _run_subprocess(concat_cmd, timeout=600)
    if result.returncode != 0 or not silent_video.is_file():
        raise RuntimeError(f"Concat fehlgeschlagen: {result.stderr[-800:]}")
    _log(f"[renderer] {len(segment_files)}/{len(timeline)} Segmente concat'ed.")
    return silent_video


def _escape_ffmetadata(value: str) -> str:
    value = str(value).replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\\", "\\\\")
    for ch in ("=", ";", "#"):
        value = value.replace(ch, f"\\{ch}")
    return value.replace("\n", "\\\n")


def _write_ffmetadata_file(work_dir: Path, tags: dict, chapters: list) -> Path:
    lines = [";FFMETADATA1"]
    for key, val in tags.items():
        if val is None or val == "":
            continue
        lines.append(f"{_escape_ffmetadata(str(key))}={_escape_ffmetadata(str(val))}")
    for chap in chapters:
        start_ms = max(0, int(round(chap["start_sec"] * 1000)))
        end_ms = max(start_ms + 1, int(round(chap["end_sec"] * 1000)))
        lines.append("")
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={start_ms}")
        lines.append(f"END={end_ms}")
        lines.append(f"title={_escape_ffmetadata(str(chap.get('title', '')))}")
    meta_path = work_dir / "video_metadata.ffmeta"
    meta_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return meta_path


def _render_into_workdir(timeline: list, song_path: str, output_path: str, work_dir: Path,
                         w: int, h: int, video_codec: str, use_nvenc: bool, _log,
                         metadata: dict | None = None,
                         globe: dict | None = None) -> str:
    silent_video = render_silent_video(timeline, work_dir, w, h, video_codec, use_nvenc, _log, globe=globe)

    scratch_times = [seg.start_sec for seg in timeline if seg.scratch]
    audio_source = song_path
    scratch_bed = _build_scratch_audio_bed(scratch_times, song_path, work_dir) if scratch_times else None
    if scratch_bed is not None:
        audio_source = str(scratch_bed)
        _log(f"[renderer] Scratch-Audiobett mit {len(scratch_times)} Stelle(n) gemischt.")
    elif scratch_times:
        _log("[renderer] Scratch-Audiobett fehlgeschlagen, reiner Song-Ton beibehalten.")

    # BUGFIX (Deep-Wiring-Audit Teil 3): AUDIO_MASTER_TARGET_LUFS_BY_STYLE
    # (config.py) verweist explizit auf DIESEN Aufruf ("Siehe
    # renderer._master_audio() Parameter `target_lufs`"), wurde aber nie
    # aufgelöst -- _master_audio lief bisher immer mit dem globalen
    # AUDIO_MASTER_TARGET_LUFS-Default, unabhängig vom --style. style.name
    # landet laut main.py::_build_video_metadata() im MP4-Tag "genre"
    # (metadata["tags"]["genre"]); von dort lösen wir den optionalen
    # Style-Override auf (leeres Dict/unbekannter Style -> unverändert wie
    # vorher). song_path wird zusätzlich durchgereicht, damit _master_audio
    # den Demucs-Stem-Cache für AUDIO_MASTER_VOCAL_DUCK_* prüfen kann (siehe
    # dortiger Docstring) -- audio_source kann zu diesem Zeitpunkt bereits
    # das Scratch-Audiobett sein, nicht mehr die reine Songdatei.
    style_name = (metadata or {}).get("tags", {}).get("genre") or ""
    target_lufs = AUDIO_MASTER_TARGET_LUFS_BY_STYLE.get(style_name, AUDIO_MASTER_TARGET_LUFS)
    audio_source = _master_audio(audio_source, work_dir, _log,
                                 song_path=song_path, target_lufs=target_lufs)

    inputs = [str(silent_video), audio_source]
    maps = ["-map", "0:v:0", "-map", "1:a:0"]
    meta_args = []
    if metadata and (metadata.get("tags") or metadata.get("chapters")):
        meta_path = _write_ffmetadata_file(work_dir, metadata.get("tags") or {}, metadata.get("chapters") or [])
        inputs.append(str(meta_path))
        meta_args = ["-map_metadata", "2", "-map_chapters", "2"]
        _log(f"[renderer] MP4-Tags eingebettet: {len(metadata.get('tags') or {})} Tag(s), "
             f"{len(metadata.get('chapters') or [])} Kapitel (wann/was/warum je Clip).")

    # BUGFIX (Deep-Wiring-Audit Teil 2): FADE_OUT_AUDIO_SEC (config.py, "Dauer
    # des Audio-Fades am Songende (nur wenn das letzte Segment fade_out ist)")
    # war definiert, aber nirgends gelesen -- der Song-Ton endete bisher immer
    # hart, selbst wenn das Bild (siehe video_fade_sec oben) bereits sanft
    # ausblendete. Gesamtdauer = timeline[-1].end_sec, da Segmente lückenlos
    # bei 0 beginnend aneinandergereiht werden (siehe timeline_builder.py).
    audio_fade_args = []
    if timeline and timeline[-1].cut_style == "fade_out" and FADE_OUT_AUDIO_SEC > 0:
        total_duration = timeline[-1].end_sec
        fade_start = max(0.0, total_duration - FADE_OUT_AUDIO_SEC)
        audio_fade_args = ["-af", f"afade=t=out:st={fade_start:.3f}:d={FADE_OUT_AUDIO_SEC:.3f}"]
        _log(f"[renderer] Song-Ende: Audio-Fade ({FADE_OUT_AUDIO_SEC}s ab {fade_start:.1f}s) "
             "angewendet (letztes Segment cut_style='fade_out').")

    final_cmd = [FFMPEG_BIN, "-y", "-nostdin"]
    for inp in inputs:
        final_cmd += ["-i", inp]
    final_cmd += maps + meta_args + audio_fade_args + ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                                      "-shortest", str(output_path)]
    result = _run_subprocess(final_cmd, timeout=600)
    if result.returncode != 0 or not Path(output_path).is_file():
        raise RuntimeError(f"Audio-Mux fehlgeschlagen: {result.stderr[-800:]}")

    _log(f"[renderer] Video fertig -> {output_path}")
    return str(output_path)
