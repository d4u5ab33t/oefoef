#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RapVideo_Dynamic_Content_Slicer_FAST.py

Fast dynamic slicer:
- 1 to max 8 bars per cut
- chooses strong parts across ALL source videos
- avoids repeated source regions
- rejects black/near-black, frozen and obviously broken clips
- uses scene changes + motion/brightness to rank candidates
- FFmpeg uses the veryfast encoder preset for faster exports
"""

import logging
import re
import subprocess
from pathlib import Path

VIDEO_SRC_DIR = Path("./logvids")
TARGET_CUTS_DIR = Path("./newcuts")
TARGET_CUTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = Path("./logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "dynamic_slicer.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("DynamicSlicer")

BPM = 140
BEAT_DURATION = 60.0 / BPM
BAR_DURATION = 4.0 * BEAT_DURATION

MIN_BARS = 1
MAX_BARS = 8

TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
TARGET_FPS = 24

# Faster candidate scan: inspect low-res material every beat.
SCAN_FPS = 6
MIN_SCORE = 0.42
MAX_CANDIDATES_PER_SOURCE = 250
MAX_OUTPUT_CLIPS = 0  # 0 = all selected candidates

# Defect thresholds
BLACK_MEAN = 12.0
FREEZE_DIFF_MAX = 0.8
MIN_SOURCE_GAP = 1.0


def run(cmd, timeout=120):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def probe_duration(src):
    try:
        r = run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(src)
        ], 15)
        return float(r.stdout.strip()) if r.returncode == 0 else 0.0
    except Exception:
        return 0.0


def detect_scene_changes(src, threshold=0.25):
    """Find useful visual change points."""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(src),
        "-filter:v",
        f"select='gt(scene,{threshold})',metadata=print:file=-",
        "-an", "-f", "null", "-"
    ]
    try:
        r = run(cmd, 180)
        text = r.stdout + "\n" + r.stderr
        return sorted({
            float(m.group(1))
            for m in re.finditer(r"pts_time:([0-9.]+)", text)
        })
    except Exception as e:
        logger.warning("Scene detection failed for %s: %s", src.name, e)
        return []


def scan_visuals(src):
    """
    Low-resolution scan. YAVG is used as a cheap brightness/variation signal.
    This is intentionally much faster than analysing every HD frame.
    """
    vf = (
        f"fps={SCAN_FPS},"
        "scale=320:-2:flags=fast_bilinear,"
        "signalstats,metadata=print:file=-"
    )
    try:
        r = run([
            "ffmpeg", "-hide_banner", "-i", str(src),
            "-vf", vf, "-an", "-f", "null", "-"
        ], 300)
        text = r.stdout + "\n" + r.stderr
        y = [float(x) for x in re.findall(r"YAVG=([0-9.]+)", text)]

        data = []
        for i, value in enumerate(y):
            previous = y[i - 1] if i else value
            data.append({
                "t": i / SCAN_FPS,
                "mean": value,
                "diff": abs(value - previous),
            })
        return data
    except Exception as e:
        logger.warning("Visual scan failed for %s: %s", src.name, e)
        return []


def check_clip_quality(src, start, duration):
    """
    Fast reject pass:
    - black/dark output
    - frozen material
    - FFmpeg decode failure

    The final exported file is also decoded/probed, so corrupt files are
    removed instead of reaching newcuts.
    """
    vf = (
        f"fps=4,scale=320:-2:flags=fast_bilinear,"
        "signalstats,metadata=print:file=-"
    )
    try:
        r = run([
            "ffmpeg", "-hide_banner",
            "-ss", f"{start:.3f}", "-i", str(src),
            "-t", f"{duration:.3f}",
            "-vf", vf, "-an", "-f", "null", "-"
        ], 90)

        if r.returncode != 0:
            return False, "decode_error"

        text = r.stdout + "\n" + r.stderr
        y = [float(x) for x in re.findall(r"YAVG=([0-9.]+)", text)]

        if not y:
            return False, "no_frames"

        dark_ratio = sum(v < BLACK_MEAN for v in y) / len(y)
        if dark_ratio > 0.40:
            return False, "black_or_bad_frame"

        # Large sequences with almost no brightness change are suspicious.
        diffs = [abs(y[i] - y[i - 1]) for i in range(1, len(y))]
        if len(diffs) >= 3:
            frozen_ratio = sum(d < FREEZE_DIFF_MAX for d in diffs) / len(diffs)
            if frozen_ratio > 0.90:
                return False, "frozen_frame"

        return True, "ok"
    except Exception as e:
        return False, f"quality_check_error:{e}"


def scene_distance(t, scene_times):
    if not scene_times:
        return 999.0
    return min(abs(t - s) for s in scene_times)


def build_candidates(src):
    duration = probe_duration(src)
    if duration < BAR_DURATION:
        return []

    scenes = detect_scene_changes(src)
    visuals = scan_visuals(src)
    if not visuals:
        return []

    # Short cuts are deliberately weighted heavily.
    bar_pattern = [1, 1, 1, 2, 2, 3, 3, 4, 5, 6, 8]
    candidates = []

    # One candidate every beat instead of every frame.
    stride = max(1, round(BAR_DURATION / 4 * SCAN_FPS))

    for i in range(0, len(visuals), stride):
        v = visuals[i]
        start = round(v["t"] / BEAT_DURATION) * BEAT_DURATION

        bars = bar_pattern[len(candidates) % len(bar_pattern)]
        length = bars * BAR_DURATION
        if start + length > duration:
            continue

        # Never start directly on a hard transition; those often contain
        # ugly half-transition frames.
        if scene_distance(start, scenes) < 0.06:
            continue

        motion = min(1.0, v["diff"] / 10.0)
        brightness = 1.0 - min(abs(v["mean"] - 105.0) / 105.0, 1.0)

        # Slight preference for cuts ending near a scene change.
        end_scene = max(
            0.0,
            1.0 - min(scene_distance(start + length, scenes), 2.0) / 2.0
        )

        score = (
            0.50 * motion +
            0.30 * brightness +
            0.20 * end_scene
        )

        if score >= MIN_SCORE:
            candidates.append({
                "src": src,
                "start": start,
                "duration": length,
                "bars": bars,
                "score": score,
            })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:MAX_CANDIDATES_PER_SOURCE]


def select_best(candidates):
    """Global selection so good parts from all source videos compete equally."""
    selected = []
    used = {}

    for c in sorted(candidates, key=lambda x: x["score"], reverse=True):
        key = str(c["src"])
        ranges = used.setdefault(key, [])
        a = c["start"]
        b = a + c["duration"]

        if any(a < rb + MIN_SOURCE_GAP and b > ra - MIN_SOURCE_GAP
               for ra, rb in ranges):
            continue

        selected.append(c)
        ranges.append((a, b))

        if MAX_OUTPUT_CLIPS and len(selected) >= MAX_OUTPUT_CLIPS:
            break

    return selected


def export(c, index):
    src = c["src"]
    start = c["start"]
    duration = c["duration"]
    bars = c["bars"]

    name = f"{src.stem}_cut_{index:04d}_{bars}bars.mp4"
    out = TARGET_CUTS_DIR / name

    if out.exists():
        return True

    ok, reason = check_clip_quality(src, start, duration)
    if not ok:
        logger.info("Rejected %s @ %.2fs: %s", src.name, start, reason)
        return False

    vf = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:"
        "force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},setsar=1,"
        f"fps={TARGET_FPS},format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-i", str(src),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-an",
        "-fps_mode", "cfr",
        str(out),
    ]

    try:
        r = run(cmd, 300)
        if r.returncode != 0 or not out.exists() or out.stat().st_size < 10240:
            logger.warning("Bad export removed: %s", name)
            out.unlink(missing_ok=True)
            return False

        # Final integrity/decode check.
        p = run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=duration,nb_frames",
            "-of", "default=noprint_wrappers=1", str(out)
        ], 20)

        if p.returncode != 0:
            logger.warning("Corrupt output removed: %s", name)
            out.unlink(missing_ok=True)
            return False

        logger.info(
            "OK %s | %.2fs | %d bars | score %.2f",
            name, duration, bars, c["score"]
        )
        return True

    except Exception as e:
        logger.warning("Export error %s: %s", name, e)
        out.unlink(missing_ok=True)
        return False


def process_videos():
    if not VIDEO_SRC_DIR.exists():
        logger.error("Missing source directory: %s", VIDEO_SRC_DIR)
        return

    sources = [
        p for p in VIDEO_SRC_DIR.rglob("*")
        if p.suffix.lower() in {".mp4", ".mov", ".mkv"}
    ]
    if not sources:
        logger.error("No source videos in %s", VIDEO_SRC_DIR.resolve())
        return

    logger.info(
        "Found %d sources. Searching 1..8 bar high-quality cuts...",
        len(sources)
    )

    candidates = []
    for src in sources:
        found = build_candidates(src)
        logger.info("%s -> %d candidates", src.name, len(found))
        candidates.extend(found)

    selected = select_best(candidates)
    logger.info(
        "Selected %d cuts from %d candidates.",
        len(selected), len(candidates)
    )

    exported = sum(export(c, i) for i, c in enumerate(selected))
    logger.info("Finished: %d clips -> %s", exported, TARGET_CUTS_DIR.resolve())


if __name__ == "__main__":
    process_videos()
