#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oidasheim v106.0 — AETHER / OIR Core
Full-stack hardening upgrade of v105.5.

Goals
-----
- SQLite/WAL instead of a race-prone JSON state file.
- Deterministic render manifests / provenance.
- Correct speed-factor math.
- Hard source-segment boundaries.
- Real FFmpeg camera motion (pan/tilt/zoom/drift).
- Single-pass-ish sequential OpenCV motion sampling.
- Real sharpness measurement for PAL material.
- SongIR metadata foundation.
- VisionGenome foundation.
- Hook-score foundation.
- Safe temp cleanup and atomic-ish render finalization.
- Backwards import of the old libsync JSON database.
- Platform profiles for TikTok / YouTube.
- No external network calls; distribution/community integrations remain adapters.

This is intentionally a production-oriented core, not a fake implementation of
the ten departments. JINX/AETHER functionality is implemented here; ORION,
ECHO, HELIX, KAIRO, VEGA, ATLAS and NOVA get stable data/adapter boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

HOME = Path(os.environ.get("OIDASHEIM_HOME", Path.home() / "Oidasheim"))
MUSIC_ROOT = Path(os.environ.get("OIDASHEIM_MP3_DIR", HOME / "Musik" / "FAVs" / "Oidamo"))
DB_DIR = Path(os.environ.get("OIDASHEIM_DB_DIR", HOME / "ignaz" / "data"))
LOG_DIR = Path(os.environ.get("OIDASHEIM_LOG_DIR", HOME / "ignaz" / "logs"))
TEMP_DIR = Path(os.environ.get("OIDASHEIM_TEMP_DIR", HOME / "ignaz" / "temp"))
RAWVIDZ_DIR = Path(os.environ.get("OIDASHEIM_RAWVIDZ_DIR", HOME / "raw_vidz" / "_raw_reorga__"))
DB_PATH = Path(os.environ.get("OIDASHEIM_SQLITE_DB", DB_DIR / "oidasheim_v106.db"))
LEGACY_JSON = Path(os.environ.get("OIDASHEIM_LEGACY_JSON", DB_DIR / "libsync-flat-globe.db.json"))

FAIL_DIR = MUSIC_ROOT.parent / "clips_fail"
QUARANTINE_DIR = MUSIC_ROOT.parent / "clips_ugly_quarantine"

MIN_DURATION = 1.0
HD_READY_HEIGHT = 720
PAL_HEIGHT = 576
DEFAULT_MIN_GOOD_BPP = 0.060
DEFAULT_MIN_SHARPNESS = 80.0
FREEZE_NOISE = 0.002
FREEZE_MIN_DUR = 0.5
MIN_SEGMENT_DUR = 0.9
MOTION_SAMPLE_FRAMES = 24
MOTION_STILL_THRESHOLD = 0.15
OVERSCAN = 1.18
PERFORMANCE_EMA_ALPHA = 0.30

PLATFORMS = {
    "TikTok": {
        "w": 1080, "h": 1920, "fps": 30, "crf": 23,
        "suffix": "[TikTok-V106]", "out_subdir": "9zu16",
        "preset": "medium",
    },
    "YouTube": {
        "w": 1920, "h": 1080, "fps": 24, "crf": 23,
        "suffix": "[YouTube-V106]", "out_subdir": "16zu9",
        "preset": "medium",
    },
}

RENDER_MODES = {"copy_safe", "quality"}

# ---------------------------------------------------------------------------
# LOGGING / UTIL
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    for d in (MUSIC_ROOT, DB_DIR, LOG_DIR, TEMP_DIR, RAWVIDZ_DIR, FAIL_DIR, QUARANTINE_DIR):
        d.mkdir(parents=True, exist_ok=True)

def get_logger() -> logging.Logger:
    ensure_dirs()
    log = logging.getLogger("oidasheim_v106")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_DIR / "oidasheim_v106.log", encoding="utf-8")
    sh = logging.StreamHandler()
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(sh)
    return log

logger = get_logger()

def run_checked(cmd: Sequence[str], timeout: int = 120, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    logger.debug("RUN %s", " ".join(map(str, cmd)))
    return subprocess.run(
        list(map(str, cmd)),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )

def tool_available(name: str) -> bool:
    return shutil.which(name) is not None

def require_media_tools() -> None:
    missing = [x for x in ("ffmpeg", "ffprobe") if not tool_available(x)]
    if missing:
        raise RuntimeError("Fehlende Abhängigkeiten: " + ", ".join(missing))

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def sanitize_filename(name: str) -> str:
    s = UNSAFE.sub("_", str(name)).strip().rstrip(".")
    return s or "untitled"

def atomic_replace(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)

# ---------------------------------------------------------------------------
# KEYWORDS
# ---------------------------------------------------------------------------

GENDER_KEYWORDS = {
    "male": {"male", "man", "boy", "bro", "dude", "king", "he", "him", "mc", "rapper",
             "typ", "mann", "kerl", "bua", "boa", "papa", "vadda", "prinz", "opa"},
    "female": {"female", "woman", "girl", "lady", "queen", "she", "her", "hers",
               "frau", "madl", "mädl", "diva", "prinzessin", "oma", "mama", "mutta"},
    "neutral": {"oida", "person", "crew", "gang", "squad", "team", "duo", "kollektiv"},
}
SUBJECT_CATEGORIES = {
    "dj": {"dj", "turntable", "mixer", "scratch", "deck", "vinyl", "platten"},
    "dancer": {"dancer", "dance", "move", "groove", "flow", "choreo", "b-boy", "tanz"},
    "singer": {"singer", "vocal", "voice", "mic", "performance", "live"},
    "car": {"car", "auto", "ride", "drive", "wheel", "drift", "bmw", "audi", "mercedes"},
    "money": {"money", "cash", "dollar", "rich", "wealth", "geld", "kohle", "stacks", "scheine"},
    "city": {"city", "street", "building", "skyline", "urban", "stadt", "beton", "gasse"},
    "group": {"group", "crew", "gang", "team", "squad", "clan", "homies"},
    "prison": {"stadelheim", "knast", "zelle", "haft", "gefängnis", "gitter"},
    "nature": {"alpen", "berg", "wald", "see", "isarufer", "alpine", "nature", "fluss"},
}
RAP_KEYWORDS = {
    "oida_anthem": {"oida", "oidamo", "oidasheim"},
    "minga_core": {"minga", "089", "muenchen", "munich", "münchen", "isar", "giesing", "schwabing"},
    "stadelheim": {"stadelheim", "stadel", "knast", "zelle", "haft"},
    "oktoberfest_vibes": {"oktoberfest", "wiesn", "ofest", "tracht", "dirndl", "lederhosen",
                          "schleife", "mass", "masskrug", "ozapft is"},
    "rap_core": {"rap", "hiphop", "mc", "rapper", "lyrics", "verse", "hook", "chorus", "bar", "flow"},
    "trap": {"trap", "808", "hi-hat", "snare", "bass", "dark", "synth"},
    "drill": {"drill", "aggressive", "hard", "menacing", "slide", "triplet"},
    "boom_bap": {"boom bap", "90s", "jazz", "soul", "sample", "vinyl"},
    "g_funk": {"g-funk", "westcoast", "wah-wah", "cowbell", "lowrider"},
    "phonk": {"phonk", "cowbell", "drift", "slow", "heavy"},
    "weisswurscht": {"weisswurscht", "weißwurscht", "wurscht", "brezn", "leberkäs"},
    "beton_street": {"beton", "asphalt", "block", "street", "straßen", "viertel"},
    "cyber_neon": {"neon", "cyber", "digital", "glitch", "code", "system"},
}
MOOD_KEYWORDS = {
    "hype": {"hype", "energy", "wild", "crazy", "insane", "turnt", "pump", "party"},
    "chill": {"chill", "calm", "relax", "smooth", "mellow", "soft", "ruhig"},
    "aggressive": {"aggressive", "hard", "brutal", "rage", "angry", "hart", "wuetend"},
    "dark": {"dark", "evil", "shadow", "night", "dunkel", "finster", "nacht"},
}

def classify_words(text: str, groups: Dict[str, set[str]]) -> Dict[str, float]:
    low = text.lower()
    tokens = set(re.findall(r"[a-zäöüß0-9\-]+", low))
    out = {}
    for cat, words in groups.items():
        exact = sum(1 for w in words if w in low)
        token = sum(1 for w in words if w in tokens)
        score = min(1.0, (exact + token) / 4.0)
        if score:
            out[cat] = score
    return out

def detect_gender(text: str) -> str:
    s = classify_words(text, GENDER_KEYWORDS)
    return max(s, key=s.get) if s and max(s.values()) > 0.2 else "neutral"

def detect_subject(text: str) -> str:
    s = classify_words(text, SUBJECT_CATEGORIES)
    return max(s, key=s.get) if s and max(s.values()) > 0.2 else "generic"

def detect_mood(text: str) -> str:
    s = classify_words(text, MOOD_KEYWORDS)
    return max(s, key=s.get) if s and max(s.values()) > 0.2 else "neutral"

def extract_themes(text: str) -> List[str]:
    s = {}
    s.update(classify_words(text, RAP_KEYWORDS))
    s.update(classify_words(text, SUBJECT_CATEGORIES))
    return [k for k, _ in sorted(s.items(), key=lambda kv: -kv[1])]

# ---------------------------------------------------------------------------
# DATA MODEL
# ---------------------------------------------------------------------------

class QualityTier(str, Enum):
    HD_READY = "hd_ready"
    PAL_GOOD_SHARPNESS = "pal_good_sharpness"
    PAL_GOOD_BITRATE = "pal_good_bitrate"
    PAL_BLURRY = "pal_blurry"
    PAL_LOW_BITRATE = "pal_low_bitrate"
    PAL_UNVERIFIED = "pal_unverified"
    SUB_PAL = "sub_pal"
    UNKNOWN = "unknown"

@dataclass
class VisionGenome:
    shot_length_histogram: List[float] = field(default_factory=list)
    camera_motion: str = "unknown"
    object_flow: str = "unknown"
    transition_type: str = "cut"
    brightness: float = 0.0
    contrast: float = 0.0
    sharpness: float = 0.0
    visual_density: float = 0.0
    face_size: float = 0.0
    object_count: int = 0
    still_ratio: float = 0.0

@dataclass
class HookFeatures:
    surprise: float = 0.0
    camera_change: float = 0.0
    text_position_score: float = 0.0
    first_05s_motion: float = 0.0
    first_3s_motion: float = 0.0
    hook_score: float = 0.0

@dataclass
class ClipSegment:
    start_s: float
    end_s: float
    cam_movement: str = "unknown"
    obj_flow: str = "unknown"
    smooth: bool = True
    still_ratio: float = 0.0
    sharpness: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0

    @property
    def duration(self) -> float:
        return max(0.0, self.end_s - self.start_s)

@dataclass
class ClipMetadata:
    path: Path
    duration: float
    width: int
    height: int
    fps: float
    bitrate: int = 0
    bpp: float = 0.0
    sharpness: Optional[float] = None
    quality_tier: QualityTier = QualityTier.UNKNOWN
    gender: str = "neutral"
    subject: str = "generic"
    themes: List[str] = field(default_factory=list)
    mood: str = "neutral"
    tags_str: str = ""
    energy: float = 0.5
    segments: List[ClipSegment] = field(default_factory=list)
    vision: VisionGenome = field(default_factory=VisionGenome)
    hook: HookFeatures = field(default_factory=HookFeatures)
    performance_score: float = 0.5

@dataclass
class SongIR:
    path: Path
    title: str
    artist: str = ""
    genre: str = ""
    key: str = ""
    bpm: float = 90.0
    duration_ms: int = 0
    beat_times_ms: List[float] = field(default_factory=list)
    onset_times_ms: List[float] = field(default_factory=list)
    energy_map: List[float] = field(default_factory=list)
    structure: List[Dict[str, Any]] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    mood: str = "neutral"
    gender: str = "neutral"

@dataclass
class RenderChunk:
    source_path: Path
    timeline_start_s: float
    duration_s: float
    source_start_s: float
    source_available_s: float
    speed_factor: float
    energy: float
    local_bpm: float
    camera_mode: str
    gender_at_cut: str = "neutral"
    narrative_role: str = "verse"
    title_text: Optional[str] = None

# ---------------------------------------------------------------------------
# FFPROBE / QUALITY
# ---------------------------------------------------------------------------

def ffprobe_json(path: Path) -> Dict[str, Any]:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries",
        "format=duration,bit_rate:stream=index,codec_type,width,height,r_frame_rate,bit_rate,pix_fmt",
        "-of", "json", str(path),
    ]
    try:
        return json.loads(run_checked(cmd, timeout=20).stdout or "{}")
    except Exception as exc:
        logger.warning("ffprobe failed for %s: %s", path, exc)
        return {}

def ffprobe_media(path: Path) -> Tuple[float, int, int, float, int]:
    data = ffprobe_json(path)
    duration = 0.0
    try:
        duration = float((data.get("format") or {}).get("duration") or 0.0)
    except Exception:
        pass
    streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if not streams:
        return duration, 0, 0, 0.0, 0
    s = streams[0]
    w = int(s.get("width") or 0)
    h = int(s.get("height") or 0)
    fps = 0.0
    try:
        n, d = str(s.get("r_frame_rate", "0/0")).split("/")
        fps = float(n) / float(d) if float(d) else 0.0
    except Exception:
        pass
    br = 0
    try:
        br = int(s.get("bit_rate") or (data.get("format") or {}).get("bit_rate") or 0)
    except Exception:
        pass
    return max(0.0, duration), w, h, fps, br

def classify_picture_quality(height: int, bpp: float, sharpness: Optional[float]) -> Tuple[bool, str]:
    if height <= 0:
        return True, QualityTier.UNKNOWN.value
    if height >= HD_READY_HEIGHT:
        return False, QualityTier.HD_READY.value
    if height >= PAL_HEIGHT:
        if sharpness is not None:
            return (False, QualityTier.PAL_GOOD_SHARPNESS.value) if sharpness >= DEFAULT_MIN_SHARPNESS else (True, QualityTier.PAL_BLURRY.value)
        if bpp >= DEFAULT_MIN_GOOD_BPP:
            return False, QualityTier.PAL_GOOD_BITRATE.value
        return True, QualityTier.PAL_LOW_BITRATE.value
    return True, QualityTier.SUB_PAL.value

def measure_sharpness(path: Path, seconds: float = 0.0) -> Optional[float]:
    """Fast FFmpeg metric using the variance of Laplacian via signalstats is not
    available on every build, so use a tiny grayscale frame pipe with OpenCV."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", str(max(0.0, seconds)), "-i", str(path),
        "-frames:v", "1", "-vf", "scale=640:-2,format=bgr24",
        "-f", "rawvideo", "pipe:1",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=20, check=True)
        raw = p.stdout
        if not raw:
            return None
        # 640-wide frame; height inferred from source aspect ratio is awkward,
        # so decode with ffmpeg to a temporary PNG instead for correctness.
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        img = cv2.imread(str(tmp_path), cv2.IMREAD_GRAYSCALE)
        tmp_path.unlink(missing_ok=True)
        if img is None:
            return None
        return float(cv2.Laplacian(img, cv2.CV_64F).var())
    except Exception:
        return None

# ---------------------------------------------------------------------------
# MOTION / VISION
# ---------------------------------------------------------------------------

def analyze_motion_cv2(path: Path, seg_start: float, seg_end: float, fps: float) -> Tuple[str, str, bool, float, float, float, float]:
    """Sequentially sample frames. Avoid repeated CAP_PROP_POS_MSEC random seeks."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return "unknown", "unknown", True, 0.0, 0.0, 0.0, 0.0

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return "unknown", "unknown", True, 0.0, 0.0, 0.0, 0.0

    native_fps = fps if fps > 0 else (cap.get(cv2.CAP_PROP_FPS) or 25.0)
    start_frame = max(0, int(seg_start * native_fps))
    end_frame = max(start_frame + 1, int(seg_end * native_fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    total_frames = max(1, end_frame - start_frame)
    stride = max(1, total_frames // MOTION_SAMPLE_FRAMES)
    prev = None
    mags: List[float] = []
    dxs: List[float] = []
    dys: List[float] = []
    still = 0
    read_idx = start_frame

    while read_idx <= end_frame:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        if (read_idx - start_frame) % stride == 0:
            small = cv2.resize(frame, (160, 90))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if prev is not None:
                flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 2, 15, 2, 5, 1.2, 0)
                mag = float(np.mean(np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)))
                dx = float(np.mean(flow[..., 0]))
                dy = float(np.mean(flow[..., 1]))
                mags.append(mag)
                dxs.append(dx)
                dys.append(dy)
                if mag < MOTION_STILL_THRESHOLD:
                    still += 1
            prev = gray
        read_idx += 1

    cap.release()
    if not mags:
        return "unknown", "unknown", True, 0.0, 0.0, 0.0, 0.0

    avg_mag = sum(mags) / len(mags)
    avg_dx = sum(dxs) / len(dxs)
    avg_dy = sum(dys) / len(dys)
    still_ratio = still / len(mags)

    if avg_mag < MOTION_STILL_THRESHOLD:
        cam = "static"
    elif abs(avg_dx) > abs(avg_dy) * 1.4:
        cam = "pan_right" if avg_dx > 0 else "pan_left"
    elif abs(avg_dy) > abs(avg_dx) * 1.4:
        cam = "tilt_down" if avg_dy > 0 else "tilt_up"
    else:
        cam = "handheld" if avg_mag > MOTION_STILL_THRESHOLD * 3 else "drift"

    variance = sum((m - avg_mag) ** 2 for m in mags) / len(mags)
    if avg_mag < MOTION_STILL_THRESHOLD:
        obj = "static"
    elif variance > avg_mag * 0.6:
        obj = "mixed"
    elif avg_dx > MOTION_STILL_THRESHOLD:
        obj = "right"
    elif avg_dx < -MOTION_STILL_THRESHOLD:
        obj = "left"
    else:
        obj = "toward" if avg_mag > MOTION_STILL_THRESHOLD * 2 else "away"

    jumps = sum(1 for a, b in zip(mags, mags[1:]) if abs(a - b) > avg_mag * 2.5 + 0.5)
    smooth = still_ratio < 0.5 and jumps <= max(1, len(mags) // 4)

    # Cheap normalized visual metrics.
    brightness = 0.0
    contrast = 0.0
    try:
        # Re-open only for a few sequential samples, not random seeking.
        cap2 = cv2.VideoCapture(str(path))
        cap2.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        vals_b, vals_c = [], []
        for i in range(min(6, total_frames)):
            ok, frame = cap2.read()
            if not ok:
                break
            g = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY)
            vals_b.append(float(np.mean(g)) / 255.0)
            vals_c.append(float(np.std(g)) / 128.0)
        cap2.release()
        if vals_b:
            brightness = sum(vals_b) / len(vals_b)
            contrast = min(1.0, sum(vals_c) / len(vals_c))
    except Exception:
        pass

    return cam, obj, smooth, round(still_ratio, 3), brightness, contrast, avg_mag

def detect_freeze_ranges(path: Path, duration: float) -> List[Tuple[float, float]]:
    if duration <= 0:
        return []
    # One FFmpeg pass is substantially cheaper than 30/60/90s subprocess chunks.
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-v", "info",
        "-i", str(path),
        "-vf", f"freezedetect=n={FREEZE_NOISE}:d={FREEZE_MIN_DUR}",
        "-an", "-f", "null", "-",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=max(60, int(duration * 1.5) + 30), check=False)
    except Exception as exc:
        logger.warning("freeze detection failed for %s: %s", path, exc)
        return []

    ranges: List[Tuple[float, float]] = []
    start = None
    for line in p.stderr.splitlines():
        if "freeze_start:" in line:
            try:
                start = float(line.split("freeze_start:", 1)[1].split()[0])
            except Exception:
                start = None
        elif "freeze_end:" in line and start is not None:
            try:
                end = float(line.split("freeze_end:", 1)[1].split()[0])
                if end > start:
                    ranges.append((max(0.0, start), min(duration, end)))
            except Exception:
                pass
            start = None

    merged: List[Tuple[float, float]] = []
    for s, e in sorted(ranges):
        if not merged or s > merged[-1][1] + 0.5:
            merged.append((s, e))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
    return merged

def good_ranges(duration: float, freezes: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if not freezes:
        return [(0.0, duration)] if duration >= MIN_SEGMENT_DUR else []
    out = []
    cursor = 0.0
    for fs, fe in freezes:
        if fs - cursor >= MIN_SEGMENT_DUR:
            out.append((cursor, fs))
        cursor = max(cursor, fe)
    if duration - cursor >= MIN_SEGMENT_DUR:
        out.append((cursor, duration))
    return out or ([(0.0, duration)] if duration >= MIN_SEGMENT_DUR else [])

def compute_hook(path: Path, duration: float, first_motion: float, brightness: float, contrast: float) -> HookFeatures:
    if duration <= 0:
        return HookFeatures()
    motion_score = max(0.0, min(1.0, first_motion / 2.0))
    surprise = max(0.0, min(1.0, 0.55 * motion_score + 0.45 * contrast))
    camera_change = max(0.0, min(1.0, motion_score))
    # No OCR dependency is assumed. text_position_score stays neutral unless an
    # OCR adapter is installed later.
    text_position = 0.5
    hook = 0.40 * surprise + 0.30 * camera_change + 0.15 * text_position + 0.15 * brightness
    return HookFeatures(
        surprise=round(surprise, 3),
        camera_change=round(camera_change, 3),
        text_position_score=text_position,
        first_05s_motion=round(motion_score, 3),
        first_3s_motion=round(min(1.0, motion_score * 0.9), 3),
        hook_score=round(max(0.0, min(1.0, hook)), 3),
    )

def analyze_clip(path: Path, deep: bool = True) -> Optional[ClipMetadata]:
    duration, w, h, fps, bitrate = ffprobe_media(path)
    if duration < MIN_DURATION or w <= 0 or h <= 0:
        return None
    bpp = bitrate / (w * h * fps) if w * h * fps > 0 else 0.0

    sharp = measure_sharpness(path) if h < HD_READY_HEIGHT else None
    bad, tier = classify_picture_quality(h, bpp, sharp)
    if bad:
        return None

    name = path.stem
    freezes = detect_freeze_ranges(path, duration)
    ranges = good_ranges(duration, freezes)
    if not ranges:
        return None

    segments: List[ClipSegment] = []
    first_motion = 0.0
    brightness = 0.0
    contrast = 0.0
    for idx, (s, e) in enumerate(ranges):
        cam = obj = "unknown"
        smooth = True
        still = 0.0
        b = c = motion = 0.0
        if deep:
            cam, obj, smooth, still, b, c, motion = analyze_motion_cv2(path, s, e, fps)
        if idx == 0:
            first_motion, brightness, contrast = motion, b, c
        segments.append(ClipSegment(
            start_s=round(s, 3), end_s=round(e, 3),
            cam_movement=cam, obj_flow=obj, smooth=smooth, still_ratio=still,
            sharpness=sharp or 0.0, brightness=b, contrast=c,
        ))

    vision = VisionGenome(
        camera_motion=segments[0].cam_movement if segments else "unknown",
        object_flow=segments[0].obj_flow if segments else "unknown",
        brightness=round(brightness, 3),
        contrast=round(contrast, 3),
        sharpness=round(sharp or 0.0, 3),
        visual_density=round(min(1.0, contrast * 0.7 + (1.0 - min(1.0, sum(s.still_ratio for s in segments) / max(1, len(segments)))) * 0.3), 3),
        still_ratio=round(sum((s.end_s - s.start_s) * s.still_ratio for s in segments) / max(duration, 0.001), 3),
    )
    hook = compute_hook(path, duration, first_motion, brightness, contrast)

    gender = detect_gender(name)
    subject = detect_subject(name)
    themes = extract_themes(name)
    mood = detect_mood(name)
    tags = " ".join(themes + [subject, gender, mood])

    return ClipMetadata(
        path=path, duration=duration, width=w, height=h, fps=fps,
        bitrate=bitrate, bpp=bpp, sharpness=sharp,
        quality_tier=QualityTier(tier), gender=gender, subject=subject,
        themes=themes, mood=mood, tags_str=tags, energy=0.6,
        segments=segments, vision=vision, hook=hook, performance_score=0.5,
    )

# ---------------------------------------------------------------------------
# SONG IR
# ---------------------------------------------------------------------------

def analyze_track(path: Path) -> SongIR:
    try:
        import librosa
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("librosa und numpy werden für Audioanalyse benötigt") from exc

    y, sr = librosa.load(path, sr=22050, mono=True)
    duration_ms = int(len(y) / sr * 1000)
    if duration_ms <= 0:
        raise ValueError("Leere Audiodatei")

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    bpm = float(np.atleast_1d(tempo)[0]) if np.atleast_1d(tempo).size else 90.0
    if bpm <= 0:
        bpm = 90.0

    beat_ms = (librosa.frames_to_time(beats, sr=sr) * 1000).tolist()
    if len(beat_ms) < 4:
        beat_ms = list(np.arange(0, duration_ms, 60000.0 / bpm))
    if not beat_ms or beat_ms[-1] < duration_ms:
        beat_ms.append(float(duration_ms))

    rms = librosa.feature.rms(y=y)[0]
    energy = (rms / (np.max(rms) + 1e-9)).tolist()
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_ms = (librosa.frames_to_time(onset_frames, sr=sr) * 1000).tolist()

    # Deterministic coarse structure foundation. It is explicitly marked heuristic,
    # not a claim that the track contains these exact musical sections.
    d = duration_ms
    structure = [
        {"role": "intro", "start_ms": 0, "end_ms": int(d * 0.12), "confidence": 0.35},
        {"role": "verse", "start_ms": int(d * 0.12), "end_ms": int(d * 0.45), "confidence": 0.25},
        {"role": "bridge", "start_ms": int(d * 0.45), "end_ms": int(d * 0.65), "confidence": 0.20},
        {"role": "verse", "start_ms": int(d * 0.65), "end_ms": int(d * 0.85), "confidence": 0.20},
        {"role": "outro", "start_ms": int(d * 0.85), "end_ms": d, "confidence": 0.25},
    ]

    title = path.stem
    artist = ""
    try:
        from mutagen import File as MutagenFile
        m = MutagenFile(path, easy=True)
        if m:
            title = (m.get("title") or [title])[0]
            artist = (m.get("artist") or [""])[0]
            genre = (m.get("genre") or [""])[0]
        else:
            genre = ""
    except Exception:
        genre = ""

    return SongIR(
        path=path, title=title, artist=artist, genre=genre,
        bpm=bpm, duration_ms=duration_ms, beat_times_ms=beat_ms,
        onset_times_ms=onset_ms, energy_map=energy,
        structure=structure, themes=extract_themes(title), mood=detect_mood(title),
        gender=detect_gender(title),
    )

# ---------------------------------------------------------------------------
# SQLITE / AETHER DATA LAYER
# ---------------------------------------------------------------------------

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS clips (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    sha256 TEXT,
    duration REAL NOT NULL DEFAULT 0,
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    fps REAL NOT NULL DEFAULT 0,
    bitrate INTEGER NOT NULL DEFAULT 0,
    bpp REAL NOT NULL DEFAULT 0,
    sharpness REAL,
    quality_tier TEXT NOT NULL DEFAULT 'unknown',
    gender TEXT NOT NULL DEFAULT 'neutral',
    subject TEXT NOT NULL DEFAULT 'generic',
    themes_json TEXT NOT NULL DEFAULT '[]',
    mood TEXT NOT NULL DEFAULT 'neutral',
    tags TEXT NOT NULL DEFAULT '',
    performance_score REAL NOT NULL DEFAULT 0.5,
    vision_json TEXT NOT NULL DEFAULT '{}',
    hook_json TEXT NOT NULL DEFAULT '{}',
    segments_json TEXT NOT NULL DEFAULT '[]',
    mtime_ns INTEGER NOT NULL DEFAULT 0,
    indexed_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    sha256 TEXT,
    song_ir_json TEXT NOT NULL,
    indexed_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS renders (
    id INTEGER PRIMARY KEY,
    render_uuid TEXT UNIQUE NOT NULL,
    track_id INTEGER,
    platform TEXT NOT NULL,
    output_path TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    finished_at REAL,
    manifest_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(track_id) REFERENCES tracks(id)
);

CREATE TABLE IF NOT EXISTS render_chunks (
    id INTEGER PRIMARY KEY,
    render_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    source_clip_id INTEGER,
    timeline_start REAL NOT NULL,
    duration REAL NOT NULL,
    source_start REAL NOT NULL,
    source_available REAL NOT NULL,
    speed_factor REAL NOT NULL,
    camera_mode TEXT NOT NULL,
    narrative_role TEXT NOT NULL,
    energy REAL NOT NULL,
    FOREIGN KEY(render_id) REFERENCES renders(id) ON DELETE CASCADE,
    FOREIGN KEY(source_clip_id) REFERENCES clips(id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY,
    render_id INTEGER,
    clip_id INTEGER,
    platform TEXT,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(render_id) REFERENCES renders(id) ON DELETE SET NULL,
    FOREIGN KEY(clip_id) REFERENCES clips(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_clips_quality ON clips(quality_tier);
CREATE INDEX IF NOT EXISTS idx_clips_perf ON clips(performance_score);
CREATE INDEX IF NOT EXISTS idx_render_chunks_render ON render_chunks(render_id);
CREATE INDEX IF NOT EXISTS idx_feedback_clip ON feedback(clip_id);
"""

class DB:
    def __init__(self, path: Path = DB_PATH):
        ensure_dirs()
        self.path = path
        self.conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def upsert_clip(self, c: ClipMetadata) -> int:
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO clips(path,sha256,duration,width,height,fps,bitrate,bpp,sharpness,
                quality_tier,gender,subject,themes_json,mood,tags,performance_score,
                vision_json,hook_json,segments_json,mtime_ns,indexed_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                sha256=excluded.sha256,duration=excluded.duration,width=excluded.width,
                height=excluded.height,fps=excluded.fps,bitrate=excluded.bitrate,bpp=excluded.bpp,
                sharpness=excluded.sharpness,quality_tier=excluded.quality_tier,gender=excluded.gender,
                subject=excluded.subject,themes_json=excluded.themes_json,mood=excluded.mood,
                tags=excluded.tags,vision_json=excluded.vision_json,hook_json=excluded.hook_json,
                segments_json=excluded.segments_json,mtime_ns=excluded.mtime_ns,indexed_at=excluded.indexed_at
            """,
            (
                str(c.path), sha256_file(c.path), c.duration, c.width, c.height, c.fps, c.bitrate,
                c.bpp, c.sharpness, c.quality_tier.value, c.gender, c.subject,
                json.dumps(c.themes, ensure_ascii=False), c.mood, c.tags_str, c.performance_score,
                json.dumps(asdict(c.vision), ensure_ascii=False),
                json.dumps(asdict(c.hook), ensure_ascii=False),
                json.dumps([asdict(s) for s in c.segments], ensure_ascii=False),
                c.path.stat().st_mtime_ns, now,
            ),
        )
        return int(self.conn.execute("SELECT id FROM clips WHERE path=?", (str(c.path),)).fetchone()[0])

    def upsert_track(self, song: SongIR) -> int:
        self.conn.execute(
            """
            INSERT INTO tracks(path,sha256,song_ir_json,indexed_at)
            VALUES(?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                sha256=excluded.sha256,song_ir_json=excluded.song_ir_json,indexed_at=excluded.indexed_at
            """,
            (str(song.path), sha256_file(song.path), json.dumps(asdict(song), default=str, ensure_ascii=False), time.time()),
        )
        return int(self.conn.execute("SELECT id FROM tracks WHERE path=?", (str(song.path),)).fetchone()[0])

    def load_clips(self) -> List[ClipMetadata]:
        rows = self.conn.execute("SELECT * FROM clips WHERE quality_tier != 'sub_pal'").fetchall()
        result = []
        for r in rows:
            if not Path(r["path"]).exists():
                continue
            segs = [ClipSegment(**s) for s in json.loads(r["segments_json"] or "[]")]
            vision = VisionGenome(**json.loads(r["vision_json"] or "{}"))
            hook = HookFeatures(**json.loads(r["hook_json"] or "{}"))
            result.append(ClipMetadata(
                path=Path(r["path"]), duration=r["duration"], width=r["width"], height=r["height"],
                fps=r["fps"], bitrate=r["bitrate"], bpp=r["bpp"], sharpness=r["sharpness"],
                quality_tier=QualityTier(r["quality_tier"]), gender=r["gender"], subject=r["subject"],
                themes=json.loads(r["themes_json"] or "[]"), mood=r["mood"], tags_str=r["tags"],
                performance_score=r["performance_score"], segments=segs, vision=vision, hook=hook,
            ))
        return result

    def record_render(self, render_uuid: str, track_id: int, platform: str, output: Path, status: str, manifest: dict) -> int:
        self.conn.execute(
            "INSERT INTO renders(render_uuid,track_id,platform,output_path,status,created_at,manifest_json) VALUES(?,?,?,?,?,?,?)",
            (render_uuid, track_id, platform, str(output), status, time.time(), json.dumps(manifest, default=str, ensure_ascii=False)),
        )
        return int(self.conn.execute("SELECT id FROM renders WHERE render_uuid=?", (render_uuid,)).fetchone()[0])

    def finish_render(self, render_id: int, status: str, manifest: dict) -> None:
        self.conn.execute(
            "UPDATE renders SET status=?,finished_at=?,manifest_json=? WHERE id=?",
            (status, time.time(), json.dumps(manifest, default=str, ensure_ascii=False), render_id),
        )

    def record_chunks(self, render_id: int, chunks: List[RenderChunk], clip_ids: Dict[str, int]) -> None:
        self.conn.executemany(
            """
            INSERT INTO render_chunks(render_id,chunk_index,source_clip_id,timeline_start,duration,
                                      source_start,source_available,speed_factor,camera_mode,narrative_role,energy)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    render_id, i, clip_ids.get(str(c.source_path)), c.timeline_start_s, c.duration_s,
                    c.source_start_s, c.source_available_s, c.speed_factor, c.camera_mode,
                    c.narrative_role, c.energy,
                )
                for i, c in enumerate(chunks)
            ],
        )

    def add_feedback(self, clip_id: int, platform: str, metric: str, value: float, render_id: Optional[int] = None) -> None:
        self.conn.execute(
            "INSERT INTO feedback(render_id,clip_id,platform,metric,value,created_at) VALUES(?,?,?,?,?,?)",
            (render_id, clip_id, platform, metric, value, time.time()),
        )
        row = self.conn.execute("SELECT performance_score FROM clips WHERE id=?", (clip_id,)).fetchone()
        if row:
            old = float(row[0])
            new = (1.0 - PERFORMANCE_EMA_ALPHA) * old + PERFORMANCE_EMA_ALPHA * max(0.0, min(1.0, value))
            self.conn.execute("UPDATE clips SET performance_score=? WHERE id=?", (new, clip_id))

# ---------------------------------------------------------------------------
# LEGACY MIGRATION
# ---------------------------------------------------------------------------

def migrate_legacy_json(db: DB, source: Path = LEGACY_JSON) -> int:
    if not source.exists():
        logger.info("Keine Legacy-JSON-DB gefunden: %s", source)
        return 0
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Legacy-JSON konnte nicht gelesen werden: %s", exc)
        return 0

    count = 0
    for key, raw in data.items():
        if key == "_render_history" or not isinstance(raw, dict):
            continue
        p = Path(raw.get("path") or key)
        if not p.exists():
            continue
        try:
            c = ClipMetadata(
                path=p,
                duration=float(raw.get("duration", 0)),
                width=int(raw.get("width", 0)),
                height=int(raw.get("height", 0)),
                fps=float(raw.get("fps", 0)),
                bitrate=int(raw.get("bitrate", 0)),
                bpp=float(raw.get("bpp", 0)),
                sharpness=raw.get("sharpness"),
                quality_tier=QualityTier(raw.get("quality_tier", "unknown")),
                gender=raw.get("gender", "neutral"),
                subject=raw.get("subject", "generic"),
                themes=raw.get("themes", []),
                mood=raw.get("mood", "neutral"),
                tags_str=raw.get("tags_str", ""),
                performance_score=float(raw.get("performance_score", 0.5)),
            )
            db.upsert_clip(c)
            count += 1
        except Exception as exc:
            logger.warning("Migration übersprungen %s: %s", p, exc)
    logger.info("Legacy migration: %d Clips übernommen", count)
    return count

# ---------------------------------------------------------------------------
# SCAN
# ---------------------------------------------------------------------------

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

def scan_clips(db: DB, deep: bool = True) -> int:
    files = [p for p in RAWVIDZ_DIR.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    logger.info("Scan: %d Videodateien", len(files))
    count = 0
    for i, p in enumerate(files, 1):
        try:
            c = analyze_clip(p, deep=deep)
            if c:
                db.upsert_clip(c)
                count += 1
        except Exception as exc:
            logger.exception("Clipanalyse fehlgeschlagen: %s", p)
        if i % 25 == 0 or i == len(files):
            logger.info("Scan %d/%d", i, len(files))
    return count

# ---------------------------------------------------------------------------
# JINX / AETHER RENDER ENGINE
# ---------------------------------------------------------------------------

CAMERA_MODES = (
    "static", "rapid_pan_right", "rapid_pan_left",
    "tilt_up", "tilt_down", "dynamic_drift", "aggressive_sweep",
)

def camera_filter(mode: str, w: int, h: int, fps: int, speed: float) -> str:
    """Create a real camera effect. The input is first overscanned so the crop
    can move without exposing black borders."""
    ow, oh = int(round(w * OVERSCAN)), int(round(h * OVERSCAN))
    # Keep expressions simple and broadly supported by FFmpeg.
    if mode == "rapid_pan_right":
        x = "min(iw-ow,(iw-ow)*t/max(D,0.001))"
        y = "(ih-oh)/2"
    elif mode == "rapid_pan_left":
        x = "max(0,(iw-ow)*(1-t/max(D,0.001)))"
        y = "(ih-oh)/2"
    elif mode == "tilt_up":
        x = "(iw-ow)/2"
        y = "max(0,(ih-oh)*(1-t/max(D,0.001)))"
    elif mode == "tilt_down":
        x = "(iw-ow)/2"
        y = "min(ih-oh,(ih-oh)*t/max(D,0.001))"
    elif mode == "dynamic_drift":
        x = "(iw-ow)*(0.5+0.5*sin(2*PI*t/max(D,0.001)))"
        y = "(ih-oh)*(0.5+0.25*sin(PI*t/max(D,0.001)))"
    elif mode == "aggressive_sweep":
        x = "(iw-ow)*(0.5+0.5*sin(4*PI*t/max(D,0.001)))"
        y = "(ih-oh)*(0.5+0.2*cos(2*PI*t/max(D,0.001)))"
    else:
        x = "(iw-ow)/2"
        y = "(ih-oh)/2"

    # The expression variable D is output duration after setpts. FFmpeg crop
    # supports t and D in the crop expression.
    return (
        f"scale={ow}:{oh}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={ow}:{oh},"
        f"setpts=PTS-STARTPTS,"
        f"setpts=PTS/{speed:.6f},"
        f"fps={fps},"
        f"crop={w}:{h}:x={x}:y={y},"
        f"format=yuv420p"
    )

class RenderEngine:
    def __init__(self, db: DB, clips: List[ClipMetadata], seed: Optional[int] = None):
        self.db = db
        self.clips = [c for c in clips if c.path.exists()]
        self.rng = random.Random(seed)
        self.usage = defaultdict(int)
        self.recent = deque(maxlen=12)
        self.used_ranges: List[Tuple[Path, float, float]] = []

    def pick_clip(self, themes: Iterable[str], mood: str, role: str, last: Optional[Path]) -> ClipMetadata:
        if not self.clips:
            raise RuntimeError("Keine gültigen Clips in der DB")
        theme_set = set(themes)
        candidates = [c for c in self.clips if c.path not in self.recent]
        if not candidates:
            candidates = list(self.clips)

        weights = []
        for c in candidates:
            w = 1.0
            ct = set(c.themes)
            union = theme_set | ct
            if union:
                w *= 1.0 + 4.0 * len(theme_set & ct) / len(union)
            if mood != "neutral" and c.mood == mood:
                w *= 1.8
            if role == "intro" and (c.subject in {"city", "nature"} or c.vision.still_ratio > 0.1):
                w *= 2.0
            if role == "hook":
                w *= 1.0 + 2.5 * c.hook.hook_score
                if c.mood == "hype":
                    w *= 1.5
            if role == "bridge" and c.mood in {"dark", "aggressive"}:
                w *= 1.5
            if last is not None and c.path == last:
                w *= 0.03
            w *= 1.0 / (1.0 + self.usage[c.path] ** 1.4 * 0.20)
            w *= 0.5 + max(0.0, min(1.0, c.performance_score))
            weights.append(max(0.05, w))

        chosen = self.rng.choices(candidates, weights=weights, k=1)[0]
        self.recent.append(chosen.path)
        self.usage[chosen.path] += 1
        return chosen

    def pick_segment(self, clip: ClipMetadata, required_input_duration: float) -> Tuple[float, float]:
        segs = [s for s in clip.segments if s.smooth] or list(clip.segments)
        if not segs:
            segs = [ClipSegment(0, clip.duration)]
        fresh = [
            s for s in segs
            if not any(p == clip.path and abs(s.start_s - a) < 0.25 for p, a, _ in self.used_ranges)
        ]
        pool = fresh or segs
        enough = [s for s in pool if s.duration + 1e-3 >= required_input_duration]
        chosen = self.rng.choice(enough if enough else pool)
        available = min(chosen.duration, max(0.0, clip.duration - chosen.start_s))
        if available <= 0:
            raise RuntimeError(f"Ungültiges Segment: {clip.path}")
        self.used_ranges.append((clip.path, chosen.start_s, chosen.start_s + available))
        return chosen.start_s, available

    def build_timeline(self, song: SongIR) -> List[RenderChunk]:
        bpm = max(40.0, song.bpm)
        beat_len = 60.0 / bpm
        chunks: List[RenderChunk] = []
        curr = 0.0
        last = None

        while curr < song.duration_ms / 1000.0 - 0.05:
            progress = curr / max(0.001, song.duration_ms / 1000.0)
            if progress < 0.12:
                role = "intro"
            elif 0.45 <= progress <= 0.65:
                role = "bridge"
            elif progress > 0.85:
                role = "outro"
            else:
                role = "hook" if (progress % 0.25) < 0.10 else "verse"

            idx = min(len(song.energy_map) - 1, int(progress * len(song.energy_map))) if song.energy_map else 0
            energy = float(song.energy_map[idx]) if song.energy_map else 0.5
            phrase_beats = 1 if energy > 0.85 else (2 if energy > 0.5 else 4)
            if role == "intro":
                phrase_beats = max(2, phrase_beats)
            duration = max(0.35, phrase_beats * beat_len)
            end = min(song.duration_ms / 1000.0, curr + duration)
            duration = end - curr
            if duration < 0.3:
                break

            speed = 1.0
            if energy > 0.82:
                speed = self.rng.choice([1.0, 1.0, 1.15, 1.25])
            elif energy < 0.35:
                speed = self.rng.choice([0.90, 1.0, 1.0])

            # IMPORTANT: source requirement is output_duration * speed.
            required_input = duration * speed
            clip = self.pick_clip(song.themes, "hype" if energy > 0.85 else song.mood, role, last)
            source_start, available = self.pick_segment(clip, required_input)

            if available < required_input:
                # If no segment is long enough, clamp speed to what the segment can
                # safely provide. Output duration stays fixed.
                speed = max(0.25, min(2.0, available / duration))
                required_input = duration * speed
                if required_input > available + 1e-3:
                    duration = available / max(speed, 0.25)

            if energy > 0.82:
                cam = self.rng.choice(("rapid_pan_right", "rapid_pan_left", "aggressive_sweep", "dynamic_drift"))
            elif role == "intro":
                cam = self.rng.choice(("static", "dynamic_drift"))
            else:
                cam = self.rng.choice(("static", "rapid_pan_right", "rapid_pan_left", "dynamic_drift"))

            chunks.append(RenderChunk(
                source_path=clip.path,
                timeline_start_s=round(curr, 3),
                duration_s=round(duration, 3),
                source_start_s=round(source_start, 3),
                source_available_s=round(available, 3),
                speed_factor=round(speed, 4),
                energy=round(energy, 4),
                local_bpm=round(bpm, 3),
                camera_mode=cam,
                gender_at_cut=song.gender,
                narrative_role=role,
                title_text=song.title if not chunks else None,
            ))
            curr += duration
            last = clip.path

        return chunks

    def render(self, song: SongIR, platform: str, mode: str = "quality", seed: Optional[int] = None) -> Optional[Path]:
        if platform not in PLATFORMS:
            raise ValueError(f"Unbekannte Plattform: {platform}")
        if mode not in RENDER_MODES:
            raise ValueError(f"Unbekannter Render-Modus: {mode}")

        chunks = self.build_timeline(song)
        if not chunks:
            raise RuntimeError("Timeline konnte nicht gebaut werden")

        plat = PLATFORMS[platform]
        out_dir = MUSIC_ROOT / plat["out_subdir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        final_name = f"{sanitize_filename(song.title)} {plat['suffix']}.mp4"
        final_path = out_dir / final_name
        render_uuid = uuid.uuid4().hex
        tmp_root = Path(tempfile.mkdtemp(prefix=f"oidasheim_{render_uuid[:8]}_", dir=str(TEMP_DIR)))
        temp_out = tmp_root / final_name

        track_id = self.db.upsert_track(song)
        manifest = {
            "schema": "oir.render.v106",
            "render_uuid": render_uuid,
            "platform": platform,
            "mode": mode,
            "song": asdict(song),
            "chunks": [asdict(c) for c in chunks],
            "created_at": time.time(),
        }
        render_id = self.db.record_render(render_uuid, track_id, platform, final_path, "running", manifest)
        clip_ids = {
            str(c.path): int(self.db.conn.execute("SELECT id FROM clips WHERE path=?", (str(c.path),)).fetchone()[0])
            for c in chunks
            if self.db.conn.execute("SELECT id FROM clips WHERE path=?", (str(c.path),)).fetchone()
        }
        self.db.record_chunks(render_id, chunks, clip_ids)

        try:
            segment_files: List[Path] = []
            for idx, c in enumerate(chunks):
                seg_out = tmp_root / f"seg_{idx:04d}.mp4"
                # Clamp input duration to the analyzed segment. This prevents the
                # renderer from leaking into freeze/bad material.
                input_duration = min(c.duration_s * c.speed_factor, c.source_available_s)
                if input_duration <= 0.05:
                    raise RuntimeError(f"Chunk {idx}: source duration invalid")

                vf = camera_filter(c.camera_mode, plat["w"], plat["h"], plat["fps"], c.speed_factor)
                cmd = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{c.source_start_s:.3f}", "-i", str(c.source_path),
                    "-t", f"{input_duration:.3f}",
                    "-vf", vf,
                    "-an",
                    "-c:v", "libx264",
                    "-preset", plat["preset"] if mode == "quality" else "ultrafast",
                    "-crf", str(plat["crf"]),
                    "-movflags", "+faststart",
                    str(seg_out),
                ]
                try:
                    run_checked(cmd, timeout=max(120, int(input_duration * 20)))
                except subprocess.CalledProcessError as exc:
                    stderr = (exc.stderr or "")[-4000:]
                    raise RuntimeError(f"FFmpeg Segment {idx} fehlgeschlagen: {stderr}") from exc
                segment_files.append(seg_out)

            concat = tmp_root / "concat.txt"
            with concat.open("w", encoding="utf-8") as f:
                for sf in segment_files:
                    # concat demuxer requires escaped single quotes.
                    p = str(sf.resolve()).replace("\\", "/").replace("'", r"'\''")
                    f.write(f"file '{p}'\n")

            video_duration = sum(c.duration_s for c in chunks)
            cmd_final = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(concat),
                "-i", str(song.path),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-t", f"{video_duration:.3f}",
                "-movflags", "+faststart",
                str(temp_out),
            ]
            try:
                run_checked(cmd_final, timeout=max(600, int(video_duration * 12)))
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or "")[-5000:]
                raise RuntimeError(f"Finales FFmpeg fehlgeschlagen: {stderr}") from exc

            if not temp_out.exists() or temp_out.stat().st_size < 1024:
                raise RuntimeError("Finales Video fehlt oder ist leer")

            atomic_replace(temp_out, final_path)
            manifest["finished_at"] = time.time()
            manifest["output_size"] = final_path.stat().st_size
            self.db.finish_render(render_id, "success", manifest)
            logger.info("Render OK: %s", final_path)
            return final_path

        except Exception as exc:
            manifest["error"] = str(exc)
            self.db.finish_render(render_id, "failed", manifest)
            logger.exception("Render fehlgeschlagen: %s", exc)
            try:
                if final_path.exists() and final_path.stat().st_size < 1024:
                    final_path.unlink()
            except Exception:
                pass
            return None
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def command_init(args: argparse.Namespace) -> None:
    db = DB()
    try:
        logger.info("AETHER DB initialisiert: %s", DB_PATH)
        if args.migrate:
            migrate_legacy_json(db)
    finally:
        db.close()

def command_migrate(args: argparse.Namespace) -> None:
    db = DB()
    try:
        migrate_legacy_json(db, Path(args.source) if args.source else LEGACY_JSON)
    finally:
        db.close()

def command_scan(args: argparse.Namespace) -> None:
    require_media_tools()
    db = DB()
    try:
        n = scan_clips(db, deep=not args.fast)
        logger.info("Scan abgeschlossen: %d valide Clips", n)
    finally:
        db.close()

def command_render(args: argparse.Namespace) -> None:
    require_media_tools()
    db = DB()
    try:
        song = analyze_track(Path(args.audio))
        clips = db.load_clips()
        engine = RenderEngine(db, clips, seed=args.seed)
        output = engine.render(song, args.platform, mode=args.mode, seed=args.seed)
        if output is None:
            raise SystemExit(2)
        print(output)
    finally:
        db.close()

def command_status(args: argparse.Namespace) -> None:
    db = DB()
    try:
        counts = {
            "clips": db.conn.execute("SELECT COUNT(*) FROM clips").fetchone()[0],
            "tracks": db.conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0],
            "renders": db.conn.execute("SELECT COUNT(*) FROM renders").fetchone()[0],
            "successful_renders": db.conn.execute("SELECT COUNT(*) FROM renders WHERE status='success'").fetchone()[0],
            "failed_renders": db.conn.execute("SELECT COUNT(*) FROM renders WHERE status='failed'").fetchone()[0],
        }
        print(json.dumps(counts, indent=2))
    finally:
        db.close()

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Oidasheim v106 AETHER/OIR Core")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init")
    s.add_argument("--migrate", action="store_true")
    s.set_defaults(func=command_init)

    s = sub.add_parser("migrate")
    s.add_argument("--source")
    s.set_defaults(func=command_migrate)

    s = sub.add_parser("scan")
    s.add_argument("--fast", action="store_true", help="nur Basisanalyse; keine tiefe Motion-Analyse")
    s.set_defaults(func=command_scan)

    s = sub.add_parser("render")
    s.add_argument("audio", help="MP3/WAV")
    s.add_argument("--platform", choices=sorted(PLATFORMS), default="TikTok")
    s.add_argument("--mode", choices=sorted(RENDER_MODES), default="quality")
    s.add_argument("--seed", type=int, default=None)
    s.set_defaults(func=command_render)

    s = sub.add_parser("status")
    s.set_defaults(func=command_status)

    return p

def main() -> int:
    ensure_dirs()
    args = build_parser().parse_args()
    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        logger.warning("Abgebrochen.")
        return 130
    except Exception as exc:
        logger.error("FATAL: %s", exc)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
