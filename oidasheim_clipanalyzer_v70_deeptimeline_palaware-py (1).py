# =============================================================================
# OIDASHEIM CLIP ANALYZER V70 - DEEP TIMELINE & PAL-AWARE
# =============================================================================
# Version: 70
# Vollständige Integration aller ursprünglichen Funktionen aus Oidasheim_ClipAnalyzer_V56_DeepTimeline_PALaware.py
# + Neue Upgrades: Speedramps, Warps, Polyrhythmik, Beat-Sync, Self-Learning
# =============================================================================

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
import time

import numpy as np
import cv2

# =============================================================================
# KONFIGURATION IMPORTIEREN (ohne Hardcoded-Pfade)
# =============================================================================

import oidasheim_config as CFG

# =============================================================================
# SELF-LEARNING & DYNAMIC LEXICON CORE
# =============================================================================

try:
    import oidasheim_learning_core as OLC
    if not hasattr(OLC, 'DynamicLexiconLearner'):
        CLIP_LEARNER = OLC.DynamicLexiconLearner()
    else:
        CLIP_LEARNER = OLC.DynamicLexiconLearner()
    SELF_LEARNING_AVAILABLE = True
except ImportError:
    CLIP_LEARNER = None
    SELF_LEARNING_AVAILABLE = False


# =============================================================================
# LOGGING (aus Original)
# =============================================================================

LOG_FILE = CFG.LOGS_DIR / "clip_analyzer_V70_deep.log"
logger = logging.getLogger("OidasheimClipAnalyzerV70")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)-8s] %(filename)s:%(lineno)d - %(message)s"))
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)


def print_flush(*args, **kwargs):
    """Flushed Print (aus Original)."""
    kwargs.setdefault('flush', True)
    print(*args, **kwargs)


# =============================================================================
# URSPRÜNGLICHE FUNKTIONEN & KLASSEN AUS Oidasheim_ClipAnalyzer_V56
# (1:1 übernommen, nur um neue Features erweitert)
# =============================================================================

# --- Video Timeline Analysis (aus Original) ---

try:
    from scenedetect import VideoManager, SceneManager
    from scenedetect.detectors import ContentDetector
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    VideoManager = None
    SceneManager = None
    ContentDetector = None


def analyze_video_timeline(
    video_path: Union[str, Path],
    deep: bool = False,
    model=None,
    classes=None
) -> Dict:
    """Analysiert die Timeline eines Videos und erkennt Szenen (aus Original)."""
    if not CV2_AVAILABLE:
        print_flush("ERROR: --deep-analysis erfordert 'opencv-python' und 'scenedetect'. Bitte installieren mit:")
        print_flush("  pip install opencv-python numpy scenedetect")
        return {}

    video_path = Path(video_path)
    video_manager = VideoManager([str(video_path)])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=27.0))

    base_timecode = video_manager.get_base_timecode()
    video_manager.set_downscale_factor()

    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)
    video_manager.release()

    scene_list = scene_manager.get_scene_list()

    scenes = []
    for i, scene in enumerate(scene_list):
        scenes.append({
            "start_time": scene[0].get_seconds(),
            "end_time": scene[1].get_seconds(),
            "start_frame": scene[0].get_frames(),
            "end_frame": scene[1].get_frames(),
            "scene_index": i
        })

    return {"video_path": str(video_path), "scenes": scenes, "deep_analysis": deep}


# --- Clip Quality Assessment (aus Original) ---

def assess_clip_quality(clip_path: Path) -> Dict:
    """Bewertet die Qualität eines Clips (PAL, HD, 4K) (aus Original)."""
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        return {"error": "Could not open video file"}

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0.0

    bitrate = int(cap.get(cv2.CAP_PROP_BITRATE))
    bpp = (bitrate / (width * height * fps)) if (width * height * fps) > 0 else 0.0

    if height >= 720:
        quality_tier = "HD"
    elif height >= 576:
        quality_tier = "PAL"
    else:
        quality_tier = "SD"

    cap.release()

    return {
        "path": str(clip_path),
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "bitrate": bitrate,
        "bpp": bpp,
        "quality_tier": quality_tier,
        "is_pal": quality_tier == "PAL"
    }


# =============================================================================
# DATENSTRUKTUREN FÜR CLIP-ANALYSE (ERWEITERT)
# =============================================================================

@dataclass
class ClipMetadata:
    """Metadaten für einen Clip, inkl. Speedramps, Warps und ursprünglichen Eigenschaften."""
    path: Path
    duration: float
    resolution: Tuple[int, int]
    fps: float = 30.0
    bitrate: int = 0
    bpp: float = 0.0
    bpm: float = 120.0
    energy: float = 0.5
    gender: str = "neutral"
    quality_tier: str = "HD"
    is_pal: bool = False
    speedramps: List = field(default_factory=list)
    warps: List = field(default_factory=list)
    scenes: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Scene:
    """Eine Szene, die aus mehreren Clips besteht."""
    start_time: float
    end_time: float
    clips: List[ClipMetadata] = field(default_factory=list)
    bpm: float = 120.0
    energy: float = 0.5


# =============================================================================
# IMPORTS FÜR SPEEDRAMPS & WARPS (aus Oidasheim_OneClick_V70)
# =============================================================================

from Oidasheim_OneClick_V70_RHYTHM_SPEEDRAMP import SpeedRamp, TimeWarp, Clip
from Oidasheim_OneClick_V70_RHYTHM_SPEEDRAMP import (
    generate_speedramps_from_bpm,
    generate_warps_from_audio,
    apply_beat_sync_warping
)


# =============================================================================
# CLIP-ANALYSE MIT SPEEDRAMPS & WARPS (ERWEITERT)
# =============================================================================

def analyze_clip(
    clip_path: Path,
    target_bpm: float = 120.0,
    target_energy: float = 0.5,
    deep_analysis: bool = False
) -> ClipMetadata:
    """Analysiert einen Clip und fügt Speedramps/Warps hinzu."""
    quality_data = assess_clip_quality(clip_path)

    metadata = ClipMetadata(
        path=clip_path,
        duration=quality_data["duration"],
        resolution=(quality_data["width"], quality_data["height"]),
        fps=quality_data.get("fps", 30.0),
        bitrate=quality_data.get("bitrate", 0),
        bpp=quality_data.get("bpp", 0.0),
        bpm=target_bpm,
        energy=target_energy,
        quality_tier=quality_data["quality_tier"],
        is_pal=quality_data["is_pal"]
    )

    if deep_analysis and CV2_AVAILABLE:
        timeline_data = analyze_video_timeline(clip_path, deep=True)
        metadata.scenes = timeline_data.get("scenes", [])

    bpm_map = [(0.0, target_bpm), (metadata.duration, target_bpm * 1.1)]
    energy_map = [(0.0, target_energy), (metadata.duration, target_energy * 1.2)]

    temp_clip = Clip(
        path=clip_path,
        start_time=0.0,
        end_time=metadata.duration,
        bpm=target_bpm,
        energy=target_energy
    )

    speedramps = generate_speedramps_from_bpm(temp_clip, bpm_map, energy_map)
    for ramp in speedramps:
        metadata.speedramps.append(ramp)

    metadata.warps.append(TimeWarp(
        start_time=0.0,
        end_time=0.5,
        warp_type="stutter",
        intensity=0.3,
        beat_sync=True
    ))

    return metadata


def analyze_scene(scene: Scene, bpm_layers: List[List[float]]) -> Scene:
    """Analysiert eine Szene und wendet polyrhythmische Anpassungen an."""
    for i, clip in enumerate(scene.clips):
        bpm_layer_idx = i % len(bpm_layers)
        clip.bpm = np.mean(bpm_layers[bpm_layer_idx])

        bpm_map = [(0.0, clip.bpm), (clip.duration, clip.bpm * 1.1)]
        energy_map = [(0.0, clip.energy), (clip.duration, clip.energy * 1.2)]

        temp_clip = Clip(
            path=clip.path,
            start_time=0.0,
            end_time=clip.duration,
            bpm=clip.bpm,
            energy=clip.energy
        )

        speedramps = generate_speedramps_from_bpm(temp_clip, bpm_map, energy_map)
        clip.speedramps.extend(speedramps)

        beat_times = np.linspace(0, clip.duration, int(clip.duration * clip.bpm / 60))
        temp_clip = apply_beat_sync_warping(temp_clip, beat_times.tolist(), clip.bpm)
        for warp in temp_clip.warps:
            scene.clips[i].warps.append(warp)

    return scene


# =============================================================================
# SELF-LEARNING FÜR CLIP-METADATEN
# =============================================================================

def learn_clip_metadata(clip_metadata: ClipMetadata, track_id: str):
    """Lernt Clip-Metadaten für zukünftige Optimierungen."""
    if SELF_LEARNING_AVAILABLE:
        CLIP_LEARNER.learn("bpm", track_id, clip_metadata.bpm)
        CLIP_LEARNER.learn("gender", track_id, clip_metadata.gender)


def predict_clip_metadata(clip_path: Path, track_id: str) -> ClipMetadata:
    """Vorhersage von Clip-Metadaten basierend auf gelernten Mustern."""
    if SELF_LEARNING_AVAILABLE:
        bpm = CLIP_LEARNER.predict("bpm", track_id)
        gender = CLIP_LEARNER.predict("gender", track_id)
    else:
        bpm = 120.0
        gender = "neutral"

    quality_data = assess_clip_quality(clip_path)

    return ClipMetadata(
        path=clip_path,
        duration=quality_data["duration"],
        resolution=(quality_data["width"], quality_data["height"]),
        fps=quality_data.get("fps", 30.0),
        bitrate=quality_data.get("bitrate", 0),
        bpp=quality_data.get("bpp", 0.0),
        bpm=bpm,
        energy=0.5,
        gender=gender,
        quality_tier=quality_data["quality_tier"],
        is_pal=quality_data["is_pal"]
    )


# =============================================================================
# HAUPTPROZESS: CLIP-ANALYSE
# =============================================================================

def analyze_clips_in_directory(
    clip_dir: Path = CFG.CLIP_DIR,
    output_db_path: Path = CFG.LIBSYNC_DB,
    deep_analysis: bool = False
):
    """Analysiert alle Clips in einem Verzeichnis und speichert die Metadaten."""
    clips_metadata = []

    for clip_path in clip_dir.glob("*.mp4"):
        print_flush(f"Analysiere Clip: {clip_path}")
        metadata = analyze_clip(clip_path, deep_analysis=deep_analysis)
        clips_metadata.append(metadata)
        learn_clip_metadata(metadata, clip_path.stem)

    db_data = {
        "clips": [clip.to_dict() for clip in clips_metadata],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(output_db_path, "w", encoding="utf-8") as f:
        json.dump(db_data, f, indent=4, ensure_ascii=False)

    print_flush(f"Analysierte {len(clips_metadata)} Clips und speicherte Metadaten in {output_db_path}")


# =============================================================================
# ARGUMENT PARSING
# =============================================================================

def parse_args():
    ap = argparse.ArgumentParser(description="Oidasheim Clip Analyzer V70 - Deep Timeline & PAL-Aware")
    ap.add_argument("--clip-dir", type=str, default=str(CFG.CLIP_DIR), help="Verzeichnis mit den Clips")
    ap.add_argument("--output-db", type=str, default=str(CFG.LIBSYNC_DB), help="Pfad zur Ausgabedatenbank")
    ap.add_argument("--deep", action="store_true", help="Aktiviert Deep Analysis")
    return ap.parse_args()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    args = parse_args()
    analyze_clips_in_directory(
        clip_dir=Path(args.clip_dir),
        output_db_path=Path(args.output_db),
        deep_analysis=args.deep
    )