#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oidasheim V116 – Robust Batch Auto‑Render
- Handles corrupt MP4s (moov atom missing)
- Retries with error‑ignoring flags
- Skips bad clips and continues processing
- Full hardware auto‑optimisation & memory management
- Batch processing of all MP3s in music root
"""

import os
import copy
import sys
import re
import json
import random
import uuid
import subprocess
import shutil
import argparse
import time
import platform
import logging
from pathlib import Path
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple, Any

from oida_genome import clip_genome, load_genome, scene_at, semantic_score, write_film_dna

# -----------------------------------------------------------------------------
# Optional dependencies
# -----------------------------------------------------------------------------
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import librosa
    import numpy as np
    HAS_LIBROSA = True
    LIBROSA_VERSION = tuple(map(int, librosa.__version__.split('.')[:2]))
except ImportError:
    HAS_LIBROSA = False
    LIBROSA_VERSION = (0, 0)
    print("[WARN] librosa not installed – beat detection fallback", file=sys.stderr)

try:
    import demucs.api
    HAS_DEMUCS = True
except ImportError:
    HAS_DEMUCS = False
    print("[WARN] demucs not installed – stem separation disabled", file=sys.stderr)

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("[WARN] opencv-python not installed – flow analysis will be static", file=sys.stderr)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    print("[WARN] anthropic SDK not installed – LLM shot planning disabled (pip install anthropic)", file=sys.stderr)

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Oidasheim")

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "paths": {
        "home": "J:/Oidasheim",
        "music_root": "J:/Oidasheim/Musik/FAVs/Weed___Eat___Need___Sleep___Repeat",
        "extra_mp3_dirs": ["WeISSWurscht is 30 JAHRE OIDA", "Oidamo Tape", "Grind im Glas"],
        "db_dir": "J:/Oidasheim/ignaz/data",
        "logs_dir": "J:/Oidasheim/ignaz/logs",
        "temp_dir": "J:/Oidasheim/ignaz/temp",
        "rawvidz_dir": "J:/raw_vidz/_raw_reorga__"
    },
    "render": {
        "render_workers_override": None,
        "batch_size_override": None,
        "ffmpeg_preset_chunk_override": None,
        "ffmpeg_preset_xfade_override": None,
        "ffmpeg_threads_override": None,
        "enable_spotlight_override": None,
        "enable_beat_pulse_override": None,
        "enable_xfade_override": None,
        "memory_threshold_gb_override": None,
        "crf": 23,
        "min_duration": 1.0,
        "ffprobe_timeout_s": 25,
        "ffmpeg_timeout_s": 120,
        "concat_timeout_s": 120,
        "audio_mux_timeout_s": 300
    },
    "beat_pulse": {
        "min_amp": 0.0035,
        "max_amp": 0.016,
        "min_bpm": 40.0,
        "max_bpm": 220.0,
        "decay_k": 5.5
    },
    "polyrhythm": {
        "beat_choices": [1, 2, 3, 4, 6, 8],
        "min_abs_shot_s": 0.55,
        "min_abs_shot_intro_outro_s": 1.2,
        "max_abs_shot_s": 3.4,
        "max_abs_shot_intro_outro_s": 7.0,
        "accent_cut_score_min": 0.80,
        "accent_min_gap_s": 0.45
    },
    "structure": {
        "window_beats": 8,
        "min_window_s": 2.0,
        "energy_weight": 0.6,
        "density_weight": 0.4,
        "hook_std": 0.45,
        "bridge_std": 0.45,
        "intro_max_frac": 0.20,
        "outro_max_frac": 0.15
    },
    "transitions": {
        "xfade_dur_s": 0.12,
        "xfade_hard_cut_s": 0.02
    },
    "end_spotlight": {
        "duration_s": 0.45,
        "ramp_s": 0.22,
        "vignette_angle": 0.62,
        "push_zoom": 1.06
    },
    "quality": {
        "hd_ready_height": 720,
        "pal_height": 576,
        "default_min_good_bpp": 0.060,
        "default_min_sharpness": 80.0
    },
    "platforms": {
        "TikTok": {"w": 1080, "h": 1920, "fps": 30, "crf": 23, "suffix": "[TikTok-AUTO]", "out_subdir": "9zu16"},
        "YouTube": {"w": 1920, "h": 1080, "fps": 24, "crf": 23, "suffix": "[YouTube-AUTO]", "out_subdir": "16zu9"}
    },
    "stems": {
        "model": "htdemucs",
        "subdir": "stems",
        "mp3_bitrate": "192k",
        "use_drum_for_beat": True
    },
    "flow": {
        "enabled": True,
        "sample_frames": 10
    },
    "llm_planner": {
        "enabled": False,
        "model": "claude-sonnet-4-6",
        "max_tokens": 1200,
        "max_agent_turns": 6,
        "candidates_per_call": 12,
        "min_segment_s": 3.0,
        "max_calls_per_track": 40,
        "request_timeout_s": 30,
        "fallback_on_error": True
    },
    "camera_movement": {
        "profiles": {
            "static": {"dx": 0.0, "dy": 0.0, "amp": 0.00, "zoom": 1.00, "depth": 0.0, "tilt": 0.0},
            "drift_right": {"dx": 1.0, "dy": 0.0, "amp": 0.55, "zoom": 1.00, "depth": 0.02, "tilt": 0.0},
            "drift_left": {"dx": -1.0, "dy": 0.0, "amp": 0.55, "zoom": 1.00, "depth": 0.02, "tilt": 0.0},
            "push_in": {"dx": 0.0, "dy": 0.0, "amp": 0.00, "zoom": 1.045, "depth": 0.05, "tilt": 0.0},
            "pull_out": {"dx": 0.0, "dy": 0.0, "amp": 0.00, "zoom": 0.965, "depth": -0.05, "tilt": 0.0},
            "spatial_flow": {"dx": 0.35, "dy": 0.35, "amp": 0.34, "zoom": 1.00, "depth": 0.03, "tilt": 0.02},
            "aggressive_sweep": {"dx": 1.0, "dy": 0.30, "amp": 0.68, "zoom": 1.015, "depth": 0.04, "tilt": 0.03},
            "orbit": {"dx": 0.0, "dy": 0.0, "amp": 0.20, "zoom": 1.00, "depth": 0.06, "tilt": 0.05},
            "spiral": {"dx": 0.0, "dy": 0.0, "amp": 0.30, "zoom": 1.02, "depth": 0.07, "tilt": 0.04}
        },
        "default": "static"
    }
}

class Config:
    def __init__(self, config_path: Optional[Path] = None):
        self.data = self._load_config(config_path)
        self._apply_env_overrides()
        self._resolve_paths()

    def _load_config(self, config_path: Optional[Path]) -> dict:
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return self._merge(copy.deepcopy(DEFAULT_CONFIG), json.load(f))
            except Exception as e:
                logger.warning(f"Could not load config from {config_path}: {e}, using defaults")
        return copy.deepcopy(DEFAULT_CONFIG)

    def _merge(self, base: dict, override: dict) -> dict:
        for k, v in override.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                base[k] = self._merge(base[k], v)
            else:
                base[k] = v
        return base

    def _apply_env_overrides(self):
        for key in self.data.get("paths", {}):
            env_var = f"OIDASHEIM_{key.upper()}"
            if env_var in os.environ:
                self.data["paths"][key] = os.environ[env_var]

    def _resolve_paths(self):
        home = Path(self.data["paths"]["home"])
        for key in ["music_root", "db_dir", "logs_dir", "temp_dir", "rawvidz_dir"]:
            p = Path(self.data["paths"][key])
            if not p.is_absolute():
                self.data["paths"][key] = str(home / p)
        music_root = Path(self.data["paths"]["music_root"])
        extra = self.data["paths"].get("extra_mp3_dirs", [])
        self.data["paths"]["extra_mp3_dirs_resolved"] = [str(music_root / d) for d in extra]

    def get(self, key_path: str, default=None):
        parts = key_path.split('.')
        cur = self.data
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return default
        return cur

# -----------------------------------------------------------------------------
# Hardware detection (same as before)
# -----------------------------------------------------------------------------
class HardwareProfile:
    def __init__(self, config: Config):
        self.config = config
        self.cpu_cores = self._detect_cpu_cores()
        self.total_memory_gb = self._detect_total_memory_gb()
        self.architecture = platform.machine().lower()
        self.os_system = platform.system().lower()
        self.is_raspberry_pi = self._detect_raspberry_pi()
        self.is_arm = self._detect_arm()
        self.is_32bit = self._detect_32bit()
        self.ffmpeg_version = self._detect_ffmpeg_version()
        self.gpu_info = self._detect_gpu()
        self.hardware_class = self._classify_hardware()
        self.optimized = self._get_optimized_settings()

    def _detect_cpu_cores(self) -> int:
        try:
            return os.cpu_count() or 1
        except:
            return 1

    def _detect_total_memory_gb(self) -> float:
        if HAS_PSUTIL:
            try:
                return psutil.virtual_memory().total / (1024 ** 3)
            except:
                pass
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        return float(line.split()[1]) / (1024 * 1024)
        except:
            pass
        try:
            result = subprocess.run(['sysctl', 'hw.memsize'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return int(result.stdout.split()[-1]) / (1024 ** 3)
        except:
            pass
        return 4.0

    def _detect_arm(self) -> bool:
        return any(arm in self.architecture for arm in ['arm', 'armv6', 'armv7', 'armv8', 'aarch64'])

    def _detect_32bit(self) -> bool:
        return '32' in platform.architecture()[0] or 'i686' in self.architecture or 'i386' in self.architecture

    def _detect_raspberry_pi(self) -> bool:
        try:
            with open('/proc/device-tree/model', 'r') as f:
                return 'raspberry pi' in f.read().lower()
        except:
            pass
        try:
            result = subprocess.run(['uname', '-a'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return any(x in result.stdout.lower() for x in ['raspberry', 'bcm27', 'bcm28'])
        except:
            pass
        return False

    def _detect_ffmpeg_version(self) -> Optional[str]:
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                first = result.stderr.split('\n')[0] if result.stderr else result.stdout.split('\n')[0]
                match = re.search(r'ffmpeg\s+version\s+(\d+\.\d+(\.\d+)?)', first)
                if match:
                    return match.group(1)
        except:
            pass
        return None

    def _detect_gpu(self) -> Dict[str, Any]:
        info = {"nvidia": False, "vaapi": False, "nvenc": False}
        try:
            res = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                info['nvidia'] = True
                try:
                    res2 = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, timeout=5)
                    if 'nvenc' in res2.stdout.lower():
                        info['nvenc'] = True
                except:
                    pass
        except:
            pass
        try:
            res = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                info['vaapi'] = True
        except:
            pass
        return info

    def _classify_hardware(self) -> str:
        if self.is_raspberry_pi:
            if self.total_memory_gb < 2:
                return "raspberry_pi_1_2"
            elif self.total_memory_gb < 4:
                return "raspberry_pi_3"
            else:
                return "raspberry_pi_4"
        if self.is_32bit:
            return "legacy_32bit"
        if self.is_arm:
            if self.total_memory_gb < 2:
                return "arm_low"
            elif self.total_memory_gb < 4:
                return "arm_medium"
            else:
                return "arm_high"
        if self.total_memory_gb < 2:
            return "ultra_low"
        elif self.total_memory_gb < 4:
            return "low"
        elif self.total_memory_gb < 8:
            return "medium"
        elif self.total_memory_gb < 16:
            return "high"
        elif self.total_memory_gb < 32:
            return "very_high"
        else:
            return "workstation"

    def _get_optimized_settings(self) -> Dict[str, Any]:
        base = {
            'render_workers': 2,
            'batch_size': 20,
            'ffmpeg_preset_chunk': 'superfast',
            'ffmpeg_preset_xfade': 'fast',
            'ffmpeg_threads': '2',
            'enable_spotlight': True,
            'enable_beat_pulse': True,
            'enable_xfade': True,
            'memory_threshold_gb': 2.0,
            'description': 'Default'
        }
        # (class-specific tweaks – same as before)
        if self.is_raspberry_pi:
            if self.hardware_class == "raspberry_pi_4":
                base.update({'render_workers':1,'batch_size':10,'ffmpeg_preset_chunk':'ultrafast','ffmpeg_preset_xfade':'superfast','ffmpeg_threads':'1','enable_spotlight':True,'enable_beat_pulse':True,'enable_xfade':True,'memory_threshold_gb':1.0,'description':'Pi4'})
            elif self.hardware_class == "raspberry_pi_3":
                base.update({'render_workers':1,'batch_size':8,'ffmpeg_preset_chunk':'ultrafast','ffmpeg_preset_xfade':'ultrafast','ffmpeg_threads':'1','enable_spotlight':False,'enable_beat_pulse':False,'enable_xfade':True,'memory_threshold_gb':0.5,'description':'Pi3'})
            else:
                base.update({'render_workers':1,'batch_size':5,'ffmpeg_preset_chunk':'ultrafast','ffmpeg_preset_xfade':'ultrafast','ffmpeg_threads':'1','enable_spotlight':False,'enable_beat_pulse':False,'enable_xfade':False,'memory_threshold_gb':0.3,'description':'Pi1/2'})
        elif self.is_arm:
            if self.hardware_class == "arm_low":
                base.update({'render_workers':1,'batch_size':8,'ffmpeg_preset_chunk':'ultrafast','ffmpeg_preset_xfade':'ultrafast','ffmpeg_threads':'1','enable_spotlight':False,'enable_beat_pulse':False,'memory_threshold_gb':0.5,'description':'ARM Low'})
            elif self.hardware_class == "arm_medium":
                base.update({'render_workers':1,'batch_size':10,'ffmpeg_preset_chunk':'superfast','ffmpeg_preset_xfade':'superfast','ffmpeg_threads':'1','enable_spotlight':True,'enable_beat_pulse':True,'memory_threshold_gb':1.0,'description':'ARM Medium'})
            else:
                base.update({'render_workers':2,'batch_size':15,'ffmpeg_preset_chunk':'superfast','ffmpeg_preset_xfade':'fast','ffmpeg_threads':'1','memory_threshold_gb':1.5,'description':'ARM High'})
        elif self.is_32bit:
            base.update({'render_workers':1,'batch_size':10,'ffmpeg_preset_chunk':'superfast','ffmpeg_preset_xfade':'superfast','ffmpeg_threads':'1','enable_spotlight':True,'enable_beat_pulse':True,'memory_threshold_gb':1.0,'description':'Legacy 32-bit'})
        else:
            if self.hardware_class == "ultra_low":
                base.update({'render_workers':1,'batch_size':5,'ffmpeg_preset_chunk':'ultrafast','ffmpeg_preset_xfade':'ultrafast','ffmpeg_threads':'1','enable_spotlight':False,'enable_beat_pulse':False,'memory_threshold_gb':0.5,'description':'Ultra Low'})
            elif self.hardware_class == "low":
                base.update({'render_workers':1,'batch_size':10,'ffmpeg_preset_chunk':'superfast','ffmpeg_preset_xfade':'superfast','ffmpeg_threads':'1','enable_spotlight':True,'enable_beat_pulse':True,'memory_threshold_gb':1.0,'description':'Low'})
            elif self.hardware_class == "medium":
                base.update({'render_workers':2,'batch_size':15,'ffmpeg_preset_chunk':'superfast','ffmpeg_preset_xfade':'fast','ffmpeg_threads':'1','memory_threshold_gb':1.5,'description':'Medium'})
            elif self.hardware_class == "high":
                base.update({'render_workers':2,'batch_size':20,'ffmpeg_preset_chunk':'superfast','ffmpeg_preset_xfade':'fast','ffmpeg_threads':'2','memory_threshold_gb':2.0,'description':'High'})
            elif self.hardware_class == "very_high":
                base.update({'render_workers':3,'batch_size':30,'ffmpeg_preset_chunk':'veryfast','ffmpeg_preset_xfade':'medium','ffmpeg_threads':'2','memory_threshold_gb':3.0,'description':'Very High'})
            else:
                base.update({'render_workers':max(4,self.cpu_cores//2),'batch_size':40,'ffmpeg_preset_chunk':'fast','ffmpeg_preset_xfade':'medium','ffmpeg_threads':'4','memory_threshold_gb':4.0,'description':'Workstation'})
        # Override with config
        cfg = self.config
        for key in ['render_workers','batch_size','ffmpeg_preset_chunk','ffmpeg_preset_xfade','ffmpeg_threads','enable_spotlight','enable_beat_pulse','enable_xfade','memory_threshold_gb']:
            val = cfg.get(f'render.{key}_override')
            if val is not None:
                base[key] = val
        return base

    def print_profile(self):
        logger.info("=" * 60)
        logger.info("HARDWARE PROFILE")
        logger.info("=" * 60)
        logger.info(f"  CPU Cores:        {self.cpu_cores}")
        logger.info(f"  Total Memory:     {self.total_memory_gb:.2f} GB")
        logger.info(f"  Architecture:     {self.architecture}")
        logger.info(f"  OS:               {self.os_system}")
        logger.info(f"  Raspberry Pi:     {self.is_raspberry_pi}")
        logger.info(f"  ARM:              {self.is_arm}")
        logger.info(f"  32-bit:           {self.is_32bit}")
        logger.info(f"  ffmpeg Version:   {self.ffmpeg_version or 'unknown'}")
        logger.info(f"  GPU:              {self.gpu_info}")
        logger.info(f"  Hardware Class:   {self.hardware_class}")
        logger.info("\nOPTIMIZED SETTINGS")
        logger.info("=" * 60)
        for k, v in self.optimized.items():
            logger.info(f"  {k.replace('_',' ').title()}: {v}")
        logger.info("=" * 60)

# -----------------------------------------------------------------------------
# Memory monitoring
# -----------------------------------------------------------------------------
def get_available_memory_gb() -> float:
    if HAS_PSUTIL:
        try:
            return psutil.virtual_memory().available / (1024 ** 3)
        except:
            pass
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    return float(line.split()[1]) / (1024 * 1024)
    except:
        pass
    return 1.0

class MemorySemaphore:
    def __init__(self, threshold_gb: float, max_workers: int):
        self.threshold = threshold_gb
        self.max_workers = max_workers
        self.active = 0

    def can_start(self) -> bool:
        return self.active < self.max_workers and get_available_memory_gb() > self.threshold

    def start(self):
        self.active += 1

    def finish(self):
        self.active = max(0, self.active - 1)

# -----------------------------------------------------------------------------
# Directories and dependencies
# -----------------------------------------------------------------------------
def ensure_dirs(config: Config):
    paths = config.get("paths")
    dirs = [
        Path(paths["music_root"]),
        Path(paths["db_dir"]),
        Path(paths["logs_dir"]),
        Path(paths["temp_dir"]),
        Path(paths["rawvidz_dir"]),
        Path(paths["music_root"]) / "clips_fail",
        Path(paths["music_root"]) / "clips_ugly_quarantine",
        Path(paths["music_root"]) / config.get("stems.subdir", "stems")
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

def check_dependencies():
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        logger.fatal(f"Missing dependencies: {', '.join(missing)}")
        sys.exit(1)

# -----------------------------------------------------------------------------
# Video file integrity check
# -----------------------------------------------------------------------------
def is_video_playable(video_path: Path, config: Config) -> bool:
    """Check if the video file is readable and contains a valid moov atom."""
    # Use ffmpeg to decode a few frames
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(video_path),
        "-frames:v", "5", "-f", "null", "-"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=config.get("render.ffprobe_timeout_s", 25))
        # If stderr contains 'moov atom' or 'error', it's likely corrupt
        if result.returncode != 0:
            return False
        # Also check for typical error messages in stderr
        if "moov atom" in result.stderr.lower() or "error" in result.stderr.lower():
            return False
        return True
    except Exception as e:
        logger.warning(f"Integrity check failed for {video_path}: {e}")
        return False

# -----------------------------------------------------------------------------
# Stem separation
# -----------------------------------------------------------------------------
def separate_stems(audio_path: Path, config: Config) -> Optional[Dict[str, Path]]:
    stems_dir = Path(config.get("paths.music_root")) / config.get("stems.subdir", "stems")
    stems_dir.mkdir(parents=True, exist_ok=True)
    model = config.get("stems.model", "htdemucs")
    if model == "htdemucs" and HAS_DEMUCS:
        out_dir = stems_dir / model
        out_dir.mkdir(exist_ok=True)
        cmd = ["demucs", "-n", model, "-o", str(stems_dir), str(audio_path)]
        logger.info(f"Running demucs: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, timeout=600)
            base = audio_path.stem
            actual_out = stems_dir / model / base
            if actual_out.exists():
                result = {}
                for f in actual_out.glob("*.wav"):
                    result[f.stem] = f
                return result
            else:
                logger.error(f"demucs output not found at {actual_out}")
                return None
        except Exception as e:
            logger.error(f"demucs failed: {e}")
            return None
    else:
        logger.warning("demucs not available – stem separation disabled")
        return None

# -----------------------------------------------------------------------------
# Beat detection
# -----------------------------------------------------------------------------
def detect_beats_from_audio(audio_path: Path, config: Config) -> Tuple[float, List[float], List[float]]:
    if not HAS_LIBROSA:
        return 120.0, [], []

    use_drum = config.get("stems.use_drum_for_beat", True)
    audio_file = audio_path
    if use_drum:
        stems_dir = Path(config.get("paths.music_root")) / config.get("stems.subdir", "stems")
        model = config.get("stems.model", "htdemucs")
        base = audio_path.stem
        drum_path = stems_dir / model / base / "drums.wav"
        if drum_path.exists():
            audio_file = drum_path
            logger.info(f"Using drum stem for beat detection: {drum_path}")
        else:
            possible = list(stems_dir.glob(f"{model}/{base}/*drums*.wav"))
            if possible:
                audio_file = possible[0]
                logger.info(f"Using drum stem: {audio_file}")

    try:
        y, sr = librosa.load(audio_file, sr=None, mono=True)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units='frames')
        if isinstance(tempo, np.ndarray):
            tempo = tempo.item() if tempo.size == 1 else tempo[0]
        bpm = float(tempo)
        if beat_frames is None or len(beat_frames) == 0:
            logger.warning("No beats detected – using BPM-based grid")
            duration = librosa.get_duration(y=y, sr=sr)
            beat_period = 60.0 / bpm if bpm > 0 else 0.5
            beat_times = np.arange(0, duration, beat_period).tolist()
            return bpm, beat_times, []
        else:
            beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onset_times = librosa.times_like(onset_env, sr=sr).tolist()
            return bpm, beat_times, onset_times
    except Exception as e:
        logger.error(f"Beat detection failed: {e}")
        try:
            duration = float(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
            ).decode().strip())
        except:
            duration = 180.0
        bpm = 120.0
        beat_period = 60.0 / bpm
        beat_times = [i * beat_period for i in range(int(duration / beat_period) + 1)]
        return bpm, beat_times, []

# -----------------------------------------------------------------------------
# Optical flow analysis
# -----------------------------------------------------------------------------
def analyze_flow(video_path: Path, config: Config) -> str:
    if not config.get("flow.enabled", True):
        return "static"

    if HAS_CV2:
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return "static"
            ret, prev = cap.read()
            if not ret:
                cap.release()
                return "static"
            prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
            flow_x_sum = 0
            flow_y_sum = 0
            count = 0
            sample_frames = config.get("flow.sample_frames", 10)
            for _ in range(sample_frames):
                ret, next_frame = cap.read()
                if not ret:
                    break
                next_gray = cv2.cvtColor(next_frame, cv2.COLOR_BGR2GRAY)
                flow = cv2.calcOpticalFlowFarneback(prev_gray, next_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                flow_x_sum += np.mean(flow[:,:,0])
                flow_y_sum += np.mean(flow[:,:,1])
                count += 1
                prev_gray = next_gray
            cap.release()
            if count == 0:
                return "static"
            avg_x = flow_x_sum / count
            avg_y = flow_y_sum / count
            threshold = 0.2
            if abs(avg_x) > abs(avg_y) and abs(avg_x) > threshold:
                return "right" if avg_x > 0 else "left"
            else:
                return "static"
        except Exception as e:
            logger.warning(f"OpenCV flow failed: {e}, falling back")
            return "static"
    else:
        return "static"

# -----------------------------------------------------------------------------
# Clip analysis with integrity check
# -----------------------------------------------------------------------------
def analyze_clip(path: Path, config: Config) -> Optional[Dict[str, Any]]:
    # First, check if the file is playable
    if not is_video_playable(path, config):
        logger.warning(f"Skipping corrupt clip: {path}")
        return None

    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "format=duration:stream=width,height,r_frame_rate,bit_rate",
           "-of", "json", str(path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=config.get("render.ffprobe_timeout_s", 25))
        data = json.loads(res.stdout)
    except:
        logger.warning(f"Failed to probe {path}")
        return None

    dur = float(data.get("format", {}).get("duration", 10.0))
    streams = data.get("streams", [{}])
    w = int(streams[0].get("width", 1920))
    h = int(streams[0].get("height", 1080))
    fps_str = streams[0].get("r_frame_rate", "30/1")
    if '/' in fps_str:
        fps = float(fps_str.split('/')[0]) / float(fps_str.split('/')[1])
    else:
        fps = float(fps_str)

    flow = analyze_flow(path, config)
    genome = clip_genome(path, {"flow": flow})
    return {
        "path": str(path),
        "duration": dur,
        "width": w,
        "height": h,
        "fps": fps,
        "flow": flow,
        "themes": genome["themes"] or ["generic"],
        "gender": "neutral",
        "mood": genome["emotion"],
        "genome": genome,
    }

# -----------------------------------------------------------------------------
# LLM Shot Planner
#
# CutClaw-style agentic shot planning layered on top of the existing heuristic
# picker. Instead of asking the model to choose a clip for every single beat
# chunk (expensive and slow), it plans once per *structural segment*
# (intro / verse / hook / bridge / outro): given a compact, locally-retrieved
# shortlist of candidate clips, the model calls tools to explore candidates
# and trim points, then commits an ordered shot list covering the segment.
# The RenderEngine consumes that shot list chunk-by-chunk; beat timing always
# stays governed by the existing polyrhythmic beat logic, so this only
# changes *which clip / which offset* is used, never the beat-sync timing.
# If the SDK/API key/network is unavailable, or the model errors out, this
# silently falls back to the original heuristic `_pick_clip`/`_pick_segment`.
# -----------------------------------------------------------------------------

LLM_PLANNER_TOOLS = [
    {
        "name": "semantic_neighborhood_retrieval",
        "description": (
            "Search the local clip pool for footage matching a theme/mood/flow query. "
            "Returns up to `top_k` candidate clips with their metadata. Call this as many "
            "times as needed with different queries to explore variety before committing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "themes": {"type": "array", "items": {"type": "string"}, "description": "Desired theme tags"},
                "mood": {"type": "string", "description": "Desired mood, e.g. 'hype', 'melancholic', 'neutral'"},
                "flow": {"type": "string", "description": "Desired camera/motion flow: 'left', 'right', or 'static'"},
                "top_k": {"type": "integer", "description": "Max candidates to return (default 8)"}
            },
            "required": []
        }
    },
    {
        "name": "fine_grained_shot_trimming",
        "description": (
            "Given a clip path and a target shot duration, returns a recommended in/out "
            "offset (in seconds) inside that clip that avoids footage already used earlier "
            "in this render, so repeated clips don't show the exact same moment twice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "clip_path": {"type": "string"},
                "target_duration_s": {"type": "number"}
            },
            "required": ["clip_path", "target_duration_s"]
        }
    },
    {
        "name": "commit_shot_plan",
        "description": (
            "Finalize the ordered list of shots for this segment. Must be called exactly "
            "once, as the last step, once the planned shots' durations roughly sum to the "
            "segment's total duration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "shots": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "clip_path": {"type": "string"},
                            "start_s": {"type": "number"},
                            "duration_s": {"type": "number"}
                        },
                        "required": ["clip_path", "start_s", "duration_s"]
                    }
                }
            },
            "required": ["shots"]
        }
    }
]


class LLMShotPlanner:
    def __init__(self, clip_pool: List[Dict], config: Config, used_ranges_by_path: Dict[str, List[Tuple[float, float]]]):
        self.clip_pool = clip_pool
        self.config = config
        self.used_ranges_by_path = used_ranges_by_path
        self.calls_made = 0
        self.client = None
        if HAS_ANTHROPIC:
            try:
                self.client = anthropic.Anthropic()
            except Exception as e:
                logger.warning(f"LLM planner: could not init Anthropic client ({e}) – disabling")
                self.client = None

    @property
    def available(self) -> bool:
        return self.client is not None

    def _budget_left(self) -> bool:
        return self.calls_made < self.config.get("llm_planner.max_calls_per_track", 40)

    def _retrieve(self, themes: List[str], mood: str, flow: str, top_k: int) -> List[Dict]:
        theme_set = frozenset(themes or [])
        scored = []
        for c in self.clip_pool:
            c_themes = frozenset(c.get("themes", []))
            overlap = len(theme_set & c_themes)
            union = len(theme_set | c_themes) or 1
            score = overlap / union
            if mood and c.get("mood") == mood:
                score += 0.3
            if flow and c.get("flow") == flow:
                score += 0.3
            scored.append((score, c))
        scored.sort(key=lambda t: t[0], reverse=True)
        top_k = max(1, min(int(top_k or 8), 20))
        return [
            {
                "clip_path": c["path"],
                "duration_s": round(c.get("duration", 0.0), 2),
                "themes": c.get("themes", []),
                "mood": c.get("mood"),
                "flow": c.get("flow"),
            }
            for _, c in scored[:top_k]
        ]

    def _trim(self, clip_path: str, target_duration_s: float) -> Dict:
        clip = next((c for c in self.clip_pool if c["path"] == clip_path), None)
        total_dur = clip.get("duration", target_duration_s) if clip else target_duration_s
        used = sorted(self.used_ranges_by_path.get(clip_path, []))
        need = max(0.5, float(target_duration_s))
        candidate_start = 0.0
        cursor = 0.0
        for u_start, u_end in used:
            if u_start - cursor >= need:
                candidate_start = cursor
                break
            cursor = max(cursor, u_end)
        else:
            candidate_start = min(cursor, max(0.0, total_dur - need))
        candidate_start = max(0.0, min(candidate_start, max(0.0, total_dur - need)))
        return {"clip_path": clip_path, "start_s": round(candidate_start, 2), "available_s": round(total_dur, 2)}

    def plan_segment(self, role: str, scene_request: Dict, segment_duration_s: float,
                      approx_shot_count: int) -> Optional[List[Dict]]:
        if not self.available or not self._budget_left():
            return None
        if segment_duration_s < self.config.get("llm_planner.min_segment_s", 3.0):
            return None

        shortlist = self._retrieve(
            list(scene_request.get("themes", [])), scene_request.get("emotion", "neutral"),
            None, self.config.get("llm_planner.candidates_per_call", 12)
        )
        system_prompt = (
            "You are the shot-planning agent inside a beat-sync music video editor. "
            "You choose which pre-analyzed video clips fill one structural segment of a song "
            "(e.g. intro, verse, hook, bridge, outro). Use the tools to look up footage and "
            "avoid re-using the same moment of a clip twice. When ready, call commit_shot_plan "
            "exactly once with a list of shots whose durations sum to roughly the segment "
            "duration you were given. Prefer variety across shots. Never invent clip paths "
            "that were not returned by semantic_neighborhood_retrieval."
        )
        user_prompt = (
            f"Segment role: {role}\n"
            f"Segment duration: {segment_duration_s:.2f}s\n"
            f"Approx number of shots needed: {approx_shot_count}\n"
            f"Scene mood/theme request: {json.dumps(scene_request, default=str)}\n"
            f"Initial candidate shortlist:\n{json.dumps(shortlist, indent=2)}"
        )
        messages = [{"role": "user", "content": user_prompt}]
        model = self.config.get("llm_planner.model", "claude-sonnet-4-6")
        max_tokens = self.config.get("llm_planner.max_tokens", 1200)
        max_turns = self.config.get("llm_planner.max_agent_turns", 6)

        try:
            for _ in range(max_turns):
                self.calls_made += 1
                resp = self.client.messages.create(
                    model=model, max_tokens=max_tokens, system=system_prompt,
                    tools=LLM_PLANNER_TOOLS, messages=messages,
                    timeout=self.config.get("llm_planner.request_timeout_s", 30),
                )
                messages.append({"role": "assistant", "content": resp.content})
                tool_uses = [b for b in resp.content if b.type == "tool_use"]
                if not tool_uses:
                    return None
                tool_results = []
                committed = None
                for tu in tool_uses:
                    if tu.name == "semantic_neighborhood_retrieval":
                        result = self._retrieve(
                            tu.input.get("themes", []), tu.input.get("mood", ""),
                            tu.input.get("flow", ""), tu.input.get("top_k", 8)
                        )
                    elif tu.name == "fine_grained_shot_trimming":
                        result = self._trim(tu.input.get("clip_path", ""), tu.input.get("target_duration_s", 1.0))
                    elif tu.name == "commit_shot_plan":
                        committed = tu.input.get("shots", [])
                        result = {"status": "committed", "count": len(committed)}
                    else:
                        result = {"error": f"unknown tool {tu.name}"}
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id,
                        "content": json.dumps(result, default=str)
                    })
                if committed is not None:
                    valid_paths = {c["path"] for c in self.clip_pool}
                    shots = [s for s in committed if s.get("clip_path") in valid_paths and s.get("duration_s", 0) > 0]
                    return shots or None
                messages.append({"role": "user", "content": tool_results})
        except Exception as e:
            logger.warning(f"LLM shot planning failed ({e}) – falling back to heuristic picker")
            return None
        return None


# -----------------------------------------------------------------------------
# RenderEngine (with retry and error-ignoring flags)
# -----------------------------------------------------------------------------
class RenderEngine:
    def __init__(self, clip_pool: List[Dict], config: Config, hardware: HardwareProfile):
        self.clip_pool = clip_pool
        self.config = config
        self.hardware = hardware
        self.blocklist = deque(maxlen=800)
        self.blocklist_set = set()
        self.usage_counter = defaultdict(int)
        self.used_ranges_by_path = defaultdict(list)
        self.last_flow = "static"

        self.render_workers = hardware.optimized['render_workers']
        self.batch_workers = min(2, self.render_workers)
        self.mem_sem = MemorySemaphore(
            threshold_gb=hardware.optimized['memory_threshold_gb'],
            max_workers=self.render_workers
        )
        self.cam_profiles = config.get("camera_movement.profiles", {})
        self.llm_planner_enabled = config.get("llm_planner.enabled", False)
        self.llm_planner = LLMShotPlanner(clip_pool, config, self.used_ranges_by_path) if self.llm_planner_enabled else None
        if self.llm_planner_enabled and not (self.llm_planner and self.llm_planner.available):
            logger.warning("LLM shot planning was requested but is unavailable (missing SDK/API key) – using heuristic picker only")
        self._llm_shot_queue: deque = deque()
        logger.info(f"RenderEngine: {self.render_workers} workers, batch {self.batch_workers}")

    def _record_usage(self, clip_path: str, start_s: float, duration_s: float):
        self.used_ranges_by_path[clip_path].append((start_s, start_s + duration_s))
        if len(self.blocklist) == self.blocklist.maxlen:
            self.blocklist_set.discard(self.blocklist.popleft())
        self.blocklist.append(clip_path)
        self.blocklist_set.add(clip_path)
        self.usage_counter[clip_path] += 1

    def _refill_llm_queue(self, role: str, scene_request: Dict, segment_duration_s: float, approx_shot_count: int):
        if not (self.llm_planner and self.llm_planner.available):
            return
        shots = self.llm_planner.plan_segment(role, scene_request, segment_duration_s, approx_shot_count)
        if shots:
            self._llm_shot_queue.extend(shots)

    def _pick_clip(self, gender: str, theme_set: frozenset, mood: str, role: str,
                   last_path: Optional[Path], desired_flow: str = None,
                   genome_request: Optional[Dict[str, Any]] = None) -> Dict:
        candidates = [c for c in self.clip_pool if c["path"] not in self.blocklist_set] or self.clip_pool
        weights = []
        for c in candidates:
            w = 1.0
            c_themes = frozenset(c.get("themes", []))
            overlap = len(theme_set & c_themes)
            union = len(theme_set | c_themes)
            if union:
                w *= 1.0 + overlap / union * 4.0
            if role == "hook" and c.get("mood") == "hype":
                w *= 2.5
            if gender != "neutral" and c.get("gender") == gender:
                w *= 2.0
            if mood != "neutral" and c.get("mood") == mood:
                w *= 1.8
            if last_path and Path(c["path"]) == last_path:
                w *= 0.05
            if desired_flow and c.get("flow") == desired_flow:
                w *= 3.0
            elif desired_flow and c.get("flow") == "static":
                w *= 1.2
            else:
                w *= 0.8
            ast_request = genome_request or {"themes": theme_set, "emotion": mood}
            w *= 0.65 + semantic_score(ast_request, c.get("genome", {})) * 0.70
            w *= 1.0 / (1.0 + (self.usage_counter.get(c["path"], 0) ** 1.5) * 0.25)
            weights.append(max(0.02, w))
        chosen = random.choices(candidates, weights=weights, k=1)[0]
        return chosen

    def _pick_segment(self, clip: Dict, need_dur: float) -> Tuple[float, float]:
        return 0.0, clip["duration"]

    def _pick_polyrhythmic_beats(self, role: str, bpm: float, beat_times: List[float]) -> int:
        if not beat_times:
            return random.choice([1,2,3,4])
        min_dur = 0.55 if role not in ("intro","outro") else 1.2
        max_dur = 3.4 if role not in ("intro","outro") else 7.0
        beat_period = 60.0 / max(bpm, 1.0)
        choices = [1,2,3,4,6,8]
        best = 2
        best_score = float('inf')
        for b in choices:
            dur = b * beat_period
            if min_dur <= dur <= max_dur:
                score = abs(dur - b * beat_period)
                if score < best_score:
                    best_score = score
                    best = b
        return best

    def _transition_style(self, prev_role: str, next_role: str, prev_energy: float, next_energy: float) -> float:
        xfade = self.config.get('transitions.xfade_dur_s', 0.12)
        hard = self.config.get('transitions.xfade_hard_cut_s', 0.02)
        if next_role == "hook" and prev_role != "hook":
            return hard
        if prev_role == "hook" and next_role == "hook" and prev_energy >= 0.75 and next_energy >= 0.75:
            return hard
        if next_role == "outro":
            return xfade * 3.0
        if prev_role == "bridge" or next_role == "bridge":
            return xfade * 2.0
        if prev_role == "intro":
            return xfade * 1.5
        return xfade

    def build_timeline(self, track: Dict) -> List[Dict]:
        chunks = []
        total_ms = track.get("duration_ms", 120000)
        bpm = track.get("global_bpm", 120)
        beat_times = track.get("beat_times", [])
        beat_period_ms = 60000.0 / max(bpm, 1.0)
        if not beat_times:
            beat_ms = [i * beat_period_ms for i in range(int(total_ms / beat_period_ms) + 2)]
        else:
            beat_ms = [t * 1000.0 for t in beat_times]
        curr_ms = 0.0
        beat_idx = 0
        last_path = None
        chunk_counter = 0
        structure = track.get("structure_segments", [])
        if not structure:
            structure = [(0.0, 0.12, "intro"), (0.12, 0.88, "verse"), (0.88, 1.0, "outro")]
        structure_ms = [(s*1000, e*1000, role) for s,e,role in structure]

        song_theme_set = frozenset(track.get("track_themes", []))
        gender = track.get("global_gender", "neutral")
        mood = track.get("track_mood", "neutral")
        flow = self.last_flow
        genome = track.get("genome", {})
        current_llm_role = None
        avg_chunk_s = max(0.3, 2.0 * beat_period_ms / 1000.0)

        while curr_ms < total_ms - 100.0 and beat_idx < len(beat_ms) - 1:
            p = curr_ms / total_ms
            role = "verse"
            seg_bounds_ms = None
            for s_ms, e_ms, seg_role in structure_ms:
                if s_ms <= curr_ms < e_ms:
                    role = seg_role
                    seg_bounds_ms = (s_ms, e_ms)
                    break
            else:
                if p < 0.12:
                    role = "intro"
                elif 0.45 <= p <= 0.60:
                    role = "bridge"
                elif p > 0.88:
                    role = "outro"

            scene = scene_at(genome, p)
            scene_emotion = genome.get("emotion_curve", {}).get(role, mood)
            scene_request = {
                "themes": song_theme_set | frozenset(filter(None, [scene.get("theme", "")])),
                "emotion": scene_emotion,
                "scene": scene.get("theme", ""),
                "location": scene.get("location", ""),
                "color": scene.get("color", ""),
            }

            if role != current_llm_role:
                current_llm_role = role
                self._llm_shot_queue.clear()
                if self.llm_planner_enabled:
                    if seg_bounds_ms:
                        seg_dur_s = (seg_bounds_ms[1] - seg_bounds_ms[0]) / 1000.0
                    else:
                        seg_dur_s = (total_ms - curr_ms) / 1000.0
                    approx_shots = max(1, int(round(seg_dur_s / avg_chunk_s)))
                    self._refill_llm_queue(role, scene_request, seg_dur_s, approx_shots)

            n_beats = self._pick_polyrhythmic_beats(role, bpm, beat_times)
            chunk_counter += 1
            if chunk_counter % 7 == 0 and role in ("verse","hook"):
                n_beats = 3 if n_beats == 2 else 2

            next_beat = beat_idx + n_beats
            if next_beat >= len(beat_ms):
                next_beat = len(beat_ms) - 1
            end_ms = beat_ms[next_beat]
            if total_ms - end_ms < beat_period_ms * 0.4:
                end_ms = total_ms
                next_beat = len(beat_ms) - 1
            dur_s = (end_ms - curr_ms) / 1000.0

            if dur_s < 0.15:
                if chunks:
                    chunks[-1]["duration_s"] += dur_s
                curr_ms = end_ms
                beat_idx = next_beat
                continue

            if flow == "left":
                desired_flow = "right"
            elif flow == "right":
                desired_flow = "left"
            else:
                desired_flow = random.choice(["left", "right", "static"])

            llm_shot = self._llm_shot_queue.popleft() if self._llm_shot_queue else None
            clip = next((c for c in self.clip_pool if c["path"] == llm_shot["clip_path"]), None) if llm_shot else None

            if clip is not None:
                src_start = max(0.0, min(float(llm_shot.get("start_s", 0.0)), max(0.0, clip["duration"] - dur_s)))
            else:
                clip = self._pick_clip(
                    gender, song_theme_set, mood, role, last_path, desired_flow,
                    genome_request={
                        "themes": scene_request["themes"],
                        "emotion": scene_request["emotion"],
                        "scene": scene_request["scene"],
                        "location": scene_request["location"],
                        "color": scene_request["color"],
                    },
                )
                src_start, _ = self._pick_segment(clip, dur_s)

            src_avail = max(0.0, clip["duration"] - src_start)
            last_path = Path(clip["path"])
            flow = clip.get("flow", "static")
            self.last_flow = flow
            self._record_usage(clip["path"], src_start, dur_s)

            if role == "intro":
                cam = random.choice(["push_in", "aggressive_sweep"])
            elif role == "hook":
                cam = "drift_right" if chunk_counter % 2 == 0 else "drift_left"
                if flow == "left" and random.random() < 0.6:
                    cam = "drift_left"
                elif flow == "right" and random.random() < 0.6:
                    cam = "drift_right"
            elif role == "outro":
                cam = "spatial_flow"
            else:
                cam = random.choice(["drift_right", "drift_left", "push_in", "pull_out", "orbit", "spiral"])
            if cam not in self.cam_profiles:
                cam = "static"

            energy = 0.9 if role == "hook" else 0.5

            chunk = {
                "source_path": clip["path"],
                "start_ms": round(curr_ms, 3),
                "duration_s": round(dur_s, 3),
                "energy": energy,
                "local_bpm": bpm,
                "cam": cam,
                "source_start_s": round(src_start, 3),
                "source_seg_dur": round(src_avail, 3),
                "narrative_role": role,
                "micro_fx": "none",
                "source_duration_s": clip["duration"],
                "scene_id": scene.get("id", ""),
                "scene_theme": scene.get("theme", ""),
                "emotion": scene_emotion,
                "transition_dur_s": self._transition_style(
                    chunks[-1]["narrative_role"] if chunks else "intro",
                    role,
                    chunks[-1]["energy"] if chunks else 0.5,
                    energy
                ) if chunks else 0.0,
                "flow": flow
            }
            chunks.append(chunk)
            curr_ms = end_ms
            beat_idx = next_beat

        if chunks and curr_ms < total_ms - 50.0:
            remaining_s = (total_ms - curr_ms) / 1000.0
            clip = self._pick_clip(gender, song_theme_set, mood, "outro", last_path, "static", genome)
            src_start, src_avail = self._pick_segment(clip, remaining_s)
            self._record_usage(clip["path"], src_start, remaining_s)
            chunks[-1]["transition_dur_s"] = self._transition_style(
                chunks[-1]["narrative_role"], "outro",
                chunks[-1]["energy"], 0.5
            )
            chunks.append({
                "source_path": clip["path"],
                "start_ms": round(curr_ms, 3),
                "duration_s": round(remaining_s, 3),
                "energy": 0.5,
                "local_bpm": bpm,
                "cam": "spatial_flow",
                "source_start_s": round(src_start, 3),
                "source_seg_dur": round(src_avail, 3),
                "narrative_role": "outro",
                "micro_fx": "none",
                "source_duration_s": clip["duration"],
                "scene_id": scene.get("id", ""),
                "scene_theme": scene.get("theme", ""),
                "emotion": scene_emotion,
                "transition_dur_s": 0.0,
                "flow": clip.get("flow", "static")
            })
        elif not chunks and total_ms > 0:
            clip = self._pick_clip(gender, song_theme_set, mood, "hook", None, "static", genome)
            src_start, src_avail = self._pick_segment(clip, total_ms/1000.0)
            self._record_usage(clip["path"], src_start, total_ms/1000.0)
            chunks.append({
                "source_path": clip["path"],
                "start_ms": 0.0,
                "duration_s": round(total_ms/1000.0, 3),
                "energy": 0.5,
                "local_bpm": bpm,
                "cam": "spatial_flow",
                "source_start_s": round(src_start, 3),
                "source_seg_dur": round(src_avail, 3),
                "narrative_role": "hook",
                "micro_fx": "none",
                "source_duration_s": clip["duration"],
                "scene_id": "",
                "scene_theme": "",
                "emotion": mood,
                "transition_dur_s": 0.0,
                "flow": clip.get("flow", "static")
            })
        return chunks

    def _build_viral_vcam_filter(self, tw: int, th: int, duration: float, fps: float,
                                 cam: str, obj_flow: str, bpm: float,
                                 bias_x: float, bias_y: float,
                                 narrative_role: str, energy: float) -> str:
        profiles = self.cam_profiles
        p = profiles.get(cam, profiles.get("static", {"dx":0,"dy":0,"amp":0,"zoom":1,"depth":0,"tilt":0}))
        amp = p.get("amp", 0.0)
        zoom = p.get("zoom", 1.0)
        depth = p.get("depth", 0.0)
        tilt = p.get("tilt", 0.0)
        overscan = 1.35
        mw = int(round(tw * overscan))
        mh = int(round(th * overscan))
        scale = f"scale={mw}:{mh}:force_original_aspect_ratio=increase"
        t_expr = f"min(1,max(0,n/({max(duration,0.1)}*{fps})))"
        ease = f"(({t_expr})*({t_expr})*(3-2*({t_expr})))"
        margin_x = max(0, mw - tw)
        margin_y = max(0, mh - th)

        if obj_flow == "left":
            center_x = f"({margin_x} * 0.8) - ({margin_x} * 0.6 * {ease})"
        elif obj_flow == "right":
            center_x = f"({margin_x} * 0.2) + ({margin_x} * 0.6 * {ease})"
        else:
            center_x = f"({margin_x}/2) + (sin(n/10) * {margin_x * 0.10:.3f})"
        center_y = f"({margin_y}/2)"

        depth_zoom = f"(1 + {depth} * {ease})"
        tilt_expr = f"{tilt} * sin(n/20)"

        shake_x = "0"
        shake_y = "0"
        if self.config.get('render.enable_beat_pulse_override', True) and narrative_role == "hook" and energy >= 0.75:
            t_sec = f"(n/{fps})"
            shake_amp_x = tw * 0.038
            shake_amp_y = th * 0.042
            decay = 7.5
            freq = 38.0
            shake_x = f"({shake_amp_x:.3f} * exp(-{decay} * {t_sec}) * cos({freq} * {t_sec}))"
            shake_y = f"({shake_amp_y:.3f} * exp(-{decay} * {t_sec}) * sin({freq} * {t_sec}))"

        dx = p.get("dx", 0.0)
        dy = p.get("dy", 0.0)
        x_expr = f"{center_x} + ({dx} * {margin_x * amp / 2:.3f} * {ease}) + ({bias_x} * {margin_x * 0.15:.3f}) + {shake_x}"
        y_expr = f"{center_y} + ({dy} * {margin_y * amp / 2:.3f} * {ease}) + ({bias_y} * {margin_y * 0.15:.3f}) + {shake_y}"
        x_clamp = f"min({margin_x}, max(0, {x_expr}))"
        y_clamp = f"min({margin_y}, max(0, {y_expr}))"
        vf = f"{scale},crop={tw}:{th}:x='{x_clamp}':y='{y_clamp}'"

        # Depth zoom
        vf += f",scale=w='iw*{depth_zoom}':h='ih*{depth_zoom}':eval=frame,crop={tw}:{th}:(iw-{tw})/2:(ih-{th})/2"

        # Beat pulse
        if self.config.get('render.enable_beat_pulse_override', True) and bpm > 0:
            phase = f"mod((n/{fps})*({bpm/60.0:.4f}),1)"
            pulse = f"(1+0.010*exp(-6.0*{phase}))"
            vf += f",scale=w='iw*{pulse}':h='ih*{pulse}':eval=frame,crop={tw}:{th}:(iw-{tw})/2:(ih-{th})/2"

        # End spotlight
        if self.config.get('render.enable_spotlight_override', True):
            dur_s = self.config.get('end_spotlight.duration_s', 0.45)
            if duration > dur_s:
                ramp_s = self.config.get('end_spotlight.ramp_s', 0.22)
                angle = self.config.get('end_spotlight.vignette_angle', 0.62)
                zoom_factor = self.config.get('end_spotlight.push_zoom', 1.06)
                spot_start = max(0.0, (duration - dur_s) * fps)
                ramp_frames = max(1.0, ramp_s * fps)
                spot_ease = f"min(1,max(0,(n-{spot_start:.3f})/{ramp_frames:.3f}))"
                spot_zoom = f"(1+{(zoom_factor - 1.0):.4f}*{spot_ease})"
                vf += f",scale=w='iw*{spot_zoom}':h='ih*{spot_zoom}':eval=frame,crop={tw}:{th}:(iw-{tw})/2:(ih-{th})/2"
                vig_angle = f"((PI/2)-((PI/2)-{angle:.4f})*{spot_ease})"
                vf += f",vignette=angle='{vig_angle}':eval=frame"

        return vf

    def _render_chunk(self, idx: int, chunk: Dict, temp_dir: Path,
                      tw: int, th: int, fps: float, crf: int,
                      bias_x: float, bias_y: float) -> Optional[Path]:
        out_f = temp_dir / f"chunk{idx:03d}.mp4"
        # Add error-ignoring flags and retry
        input_args = [
            "-err_detect", "ignore_err",
            "-i", str(chunk["source_path"]),
            "-ss", str(chunk["source_start_s"]),
            "-t", str(chunk["duration_s"] + 0.1)
        ]
        vf = self._build_viral_vcam_filter(
            tw=tw, th=th, duration=chunk["duration_s"], fps=fps,
            cam=chunk["cam"], obj_flow=chunk.get("flow", "static"),
            bpm=chunk["local_bpm"], bias_x=bias_x, bias_y=bias_y,
            narrative_role=chunk["narrative_role"], energy=chunk["energy"]
        )
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-threads", str(self.hardware.optimized["ffmpeg_threads"]),
            *input_args, "-vf", vf,
            "-r", f"{fps:.4f}", "-vsync", "cfr",
            "-c:v", "libx264", "-preset", self.hardware.optimized["ffmpeg_preset_chunk"],
            "-crf", str(crf), "-an", str(out_f)
        ]
        if not self.mem_sem.can_start():
            logger.warning(f"Chunk {idx}: low memory, skipping")
            return None
        self.mem_sem.start()
        try:
            subprocess.run(cmd, check=True, timeout=self.config.get("render.ffmpeg_timeout_s", 120))
            if out_f.exists():
                return out_f
            return None
        except Exception as e:
            logger.warning(f"Chunk {idx} failed: {e}, retrying with -re...")
            # Retry with -re (read as realtime) to force demuxer to keep reading
            cmd_re = cmd.copy()
            cmd_re.insert(1, "-re")  # after -y
            try:
                subprocess.run(cmd_re, check=True, timeout=self.config.get("render.ffmpeg_timeout_s", 120))
                if out_f.exists():
                    return out_f
            except Exception as e2:
                logger.error(f"Chunk {idx} retry failed: {e2}")
            return None
        finally:
            self.mem_sem.finish()

    def _xfade_merge_batch(self, encoded_files: List[Path], batch_chunks: List[Dict],
                           temp_dir: Path, crf: int, batch_idx: int) -> Optional[Path]:
        if len(encoded_files) == 1:
            return encoded_files[0]
        filter_parts = []
        label_prev = "0:v"
        cum_s = float(batch_chunks[0]["duration_s"])
        for i in range(1, len(batch_chunks)):
            requested = max(self.config.get('transitions.xfade_hard_cut_s', 0.02),
                            batch_chunks[i-1].get("transition_dur_s", 0.12))
            max_allowed = 0.4 * min(batch_chunks[i-1]["duration_s"], batch_chunks[i]["duration_s"])
            dur = min(requested, max(self.config.get('transitions.xfade_hard_cut_s', 0.02), max_allowed))
            offset = max(0.0, cum_s - dur)
            filter_parts.append(f"[{label_prev}][{i}:v]xfade=transition=fade:duration={dur:.4f}:offset={offset:.3f}[vx{i}]")
            label_prev = f"vx{i}"
            cum_s = cum_s + batch_chunks[i]["duration_s"] - dur
        script_file = temp_dir / f"xfade_batch{batch_idx:04d}.txt"
        script_file.write_text(";".join(filter_parts), encoding="utf-8")
        out_f = temp_dir / f"batch{batch_idx:04d}.mp4"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-threads", str(self.hardware.optimized["ffmpeg_threads"])
        ]
        for f in encoded_files:
            cmd += ["-i", str(f)]
        cmd += ["-filter_complex_script", str(script_file), "-map", f"[{label_prev}]",
                "-an", "-c:v", "libx264", "-preset", self.hardware.optimized["ffmpeg_preset_xfade"],
                "-crf", str(crf), str(out_f)]
        try:
            subprocess.run(cmd, check=True, timeout=self.config.get("render.concat_timeout_s", 120))
            return out_f if out_f.exists() else None
        except Exception as e:
            logger.error(f"Batch merge {batch_idx} failed: {e}")
            return None

    def assemble(self, chunks: List[Dict], platform: str, track: Dict) -> Optional[Path]:
        plat = self.config.get(f"platforms.{platform}")
        if not plat:
            logger.error(f"Unknown platform: {platform}")
            return None
        tw, th, fps, crf = plat["w"], plat["h"], plat["fps"], plat["crf"]
        out_dir = Path(self.config.get("paths.music_root")) / plat["out_subdir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_title = re.sub(r'[<>:"/\\|?*]', '', track.get("title", "unknown"))
        output = out_dir / f"{safe_title} {plat['suffix']}.mp4"
        temp_dir = out_dir / f"chunks{uuid.uuid4().hex[:6]}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        biases = []
        cx, cy = 0.0, 0.0
        for ch in chunks:
            biases.append((cx, cy))
            p = self.cam_profiles.get(ch["cam"], self.cam_profiles.get("static", {}))
            cx = p.get("dx", 0.0) * p.get("amp", 0.0)
            cy = p.get("dy", 0.0) * p.get("amp", 0.0)

        results = {}
        with ThreadPoolExecutor(max_workers=self.render_workers) as ex:
            futures = {
                ex.submit(self._render_chunk, i, ch, temp_dir, tw, th, fps, crf, biases[i][0], biases[i][1]): i
                for i, ch in enumerate(chunks)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                results[idx] = fut.result()
                logger.debug(f"Chunk {idx} done: {'OK' if results[idx] else 'FAIL'}")

        encoded_files = [results[i] for i in range(len(chunks)) if results[i] is not None]
        if len(encoded_files) != len(chunks):
            logger.error(f"Only {len(encoded_files)}/{len(chunks)} chunks rendered")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        batch_size = self.hardware.optimized["batch_size"]
        batch_ranges = [(i, min(i+batch_size, len(chunks))) for i in range(0, len(chunks), batch_size)]
        batch_outputs = {}
        with ThreadPoolExecutor(max_workers=self.batch_workers) as ex:
            futures = {}
            for b_idx, (start, end) in enumerate(batch_ranges):
                futures[ex.submit(self._xfade_merge_batch, encoded_files[start:end], chunks[start:end],
                                  temp_dir, crf, b_idx)] = b_idx
            for fut in as_completed(futures):
                b_idx = futures[fut]
                batch_outputs[b_idx] = fut.result()
        ordered = [batch_outputs[i] for i in range(len(batch_ranges))]
        if any(b is None for b in ordered):
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        if len(ordered) == 1:
            final_video = ordered[0]
        else:
            concat_txt = temp_dir / "concat.txt"
            lines = [f"file '{str(f.absolute()).replace(chr(92), '/')}'" for f in ordered]
            concat_txt.write_text("\n".join(lines), encoding="utf-8")
            final_video = temp_dir / "final.mp4"
            cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                   "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                   "-c", "copy", str(final_video)]
            try:
                subprocess.run(cmd, check=True, timeout=self.config.get("render.concat_timeout_s", 120))
                if not final_video.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None
            except Exception as e:
                logger.error(f"Concat failed: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

        # Add audio
        audio_input = track.get("path")
        if audio_input and Path(audio_input).exists():
            cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                   "-i", str(final_video), "-i", str(audio_input),
                   "-map", "0:v:0", "-map", "1:a:0",
                   "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                   "-t", f"{track.get('duration_ms', 120000)/1000.0:.3f}", str(output)]
            try:
                subprocess.run(cmd, check=True, timeout=self.config.get("render.audio_mux_timeout_s", 300))
            except Exception as e:
                logger.error(f"Audio mux failed: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
        else:
            shutil.copy2(final_video, output)

        if output.exists():
            logger.info(f"✅ Output: {output}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return output
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

# -----------------------------------------------------------------------------
# Batch processing helper
# -----------------------------------------------------------------------------
def get_music_files(config: Config, batch_dir: Optional[Path] = None) -> List[Path]:
    if batch_dir:
        base_dirs = [batch_dir]
    else:
        music_root = Path(config.get("paths.music_root"))
        extra_dirs = [Path(d) for d in config.get("paths.extra_mp3_dirs_resolved", [])]
        base_dirs = [music_root] + extra_dirs

    mp3s = []
    for d in base_dirs:
        if d.exists():
            mp3s.extend(d.glob("*.mp3"))
    return sorted(mp3s)

# -----------------------------------------------------------------------------
# Process a single track
# -----------------------------------------------------------------------------
def process_track(audio_path: Path, clip_pool: List[Dict], config: Config,
                  hardware: HardwareProfile, platform: str, dry_run: bool) -> bool:
    logger.info(f"Processing track: {audio_path.name}")

    if config.get("stems.use_drum_for_beat", True):
        logger.info("Checking for stems...")
        stems = separate_stems(audio_path, config)
        if not stems:
            logger.warning("Stem separation failed – using full audio for beat detection")

    bpm, beat_times, _ = detect_beats_from_audio(audio_path, config)
    logger.info(f"Detected BPM: {bpm:.1f}, Beat count: {len(beat_times)}")

    if HAS_LIBROSA:
        try:
            duration = int(librosa.get_duration(path=str(audio_path)) * 1000)
        except TypeError:
            duration = int(librosa.get_duration(filename=str(audio_path)) * 1000)
    else:
        try:
            dur_str = subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
            ).decode().strip()
            duration = int(float(dur_str) * 1000)
        except:
            duration = 180000

    genome = load_genome(audio_path, is_track=True)
    track_themes = genome["themes"] or ["generic"]
    track_mood = genome["emotion"] if genome["emotion"] != "neutral" else "neutral"
    track = {
        "path": str(audio_path),
        "title": audio_path.stem,
        "duration_ms": duration,
        "global_bpm": bpm,
        "beat_times": beat_times,
        "global_gender": "neutral",
        "track_themes": track_themes,
        "track_mood": track_mood,
        "genome": genome,
        "structure_segments": [(0.0, 0.12, "intro"), (0.12, 0.88, "verse"), (0.88, 1.0, "outro")]
    }

    engine = RenderEngine(clip_pool, config, hardware)
    chunks = engine.build_timeline(track)
    if not chunks:
        logger.error(f"Failed to build timeline for {audio_path.name}")
        return False

    if dry_run:
        logger.info(f"DRY RUN – timeline for {audio_path.name}:")
        for i, ch in enumerate(chunks):
            logger.info(f"  {i}: {ch['source_path']} @ {ch['start_ms']/1000:.2f}s, dur={ch['duration_s']:.2f}s, role={ch['narrative_role']}, flow={ch.get('flow','?')}")
        return True

    result = engine.assemble(chunks, platform, track)
    if result:
        try:
            write_film_dna(result.with_suffix(".film_dna.json"), track, chunks)
        except OSError as e:
            logger.warning(f"Could not write FilmDNA manifest: {e}")
        logger.info(f"✅ Success: {result}")
        return True
    else:
        logger.error(f"Render failed for {audio_path.name}")
        return False

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Oidasheim V116 – Robust Batch Auto‑Render")
    parser.add_argument("--config", type=Path, help="Path to JSON config file")
    parser.add_argument("--track", type=Path, help="Path to a single audio track file")
    parser.add_argument("--platform", type=str, default="TikTok", choices=["TikTok","YouTube"])
    parser.add_argument("--workers", type=int, help="Override render workers")
    parser.add_argument("--sequential", action="store_true", help="Force single worker")
    parser.add_argument("--scan-only", action="store_true", help="Only scan clips")
    parser.add_argument("--dry-run", action="store_true", help="Print timeline without rendering")
    parser.add_argument("--profile", action="store_true", help="Show hardware profile and exit")
    parser.add_argument("--separate-stems", action="store_true", help="Run stem separation on the track and exit")
    parser.add_argument("--llm-shot-planning", action="store_true",
                         help="Enable CutClaw-style LLM agent shot planning per structural segment "
                              "(requires `pip install anthropic` and ANTHROPIC_API_KEY set). Falls "
                              "back to the heuristic picker automatically on any failure.")

    parser.add_argument("--batch", action="store_true", help="Process all MP3s in music root (and extras)")
    parser.add_argument("--batch-dir", type=Path, help="Override directory for batch mode")
    parser.add_argument("--batch-limit", type=int, default=None, help="Max number of tracks to process")
    parser.add_argument("--batch-parallel", type=int, default=1, help="Number of tracks to process in parallel")

    args = parser.parse_args()

    config = Config(args.config)
    if args.workers is not None:
        config.data["render"]["render_workers_override"] = args.workers
    if args.sequential:
        config.data["render"]["render_workers_override"] = 1
        config.data["render"]["batch_size_override"] = 5
    if args.llm_shot_planning:
        config.data["llm_planner"]["enabled"] = True
        if not HAS_ANTHROPIC:
            logger.warning("--llm-shot-planning set but the `anthropic` package isn't installed; run `pip install anthropic`. Falling back to heuristic picker.")
        elif not os.environ.get("ANTHROPIC_API_KEY"):
            logger.warning("--llm-shot-planning set but ANTHROPIC_API_KEY is not set in the environment. Falling back to heuristic picker.")

    hardware = HardwareProfile(config)
    if args.profile:
        hardware.print_profile()
        sys.exit(0)

    check_dependencies()
    ensure_dirs(config)
    hardware.print_profile()

    if args.separate_stems:
        if not args.track:
            logger.error("Need --track for stem separation")
            sys.exit(1)
        logger.info(f"Separating stems for {args.track}")
        result = separate_stems(args.track, config)
        if result:
            logger.info(f"Stems saved: {result}")
        else:
            logger.error("Stem separation failed")
        sys.exit(0)

    if args.scan_only:
        logger.info("Scan‑only mode: analyzing clips...")
        raw_dir = Path(config.get("paths.rawvidz_dir"))
        clips = []
        for f in raw_dir.glob("*.mp4"):
            meta = analyze_clip(f, config)
            if meta:
                clips.append(meta)
        logger.info(f"Found {len(clips)} valid clips")
        sys.exit(0)

    # Load clip pool with integrity check
    raw_dir = Path(config.get("paths.rawvidz_dir"))
    clip_pool = []
    for f in raw_dir.glob("*.mp4"):
        meta = analyze_clip(f, config)
        if meta:
            clip_pool.append(meta)
    if not clip_pool:
        logger.error("No valid video clips found in rawvidz_dir – check for corrupt files.")
        sys.exit(1)
    logger.info(f"Loaded {len(clip_pool)} playable clips")

    if args.track:
        success = process_track(args.track, clip_pool, config, hardware, args.platform, args.dry_run)
        sys.exit(0 if success else 1)

    elif args.batch:
        mp3_files = get_music_files(config, args.batch_dir)
        if not mp3_files:
            logger.error("No MP3 files found in music directories")
            sys.exit(1)
        if args.batch_limit:
            mp3_files = mp3_files[:args.batch_limit]
        logger.info(f"Batch mode: {len(mp3_files)} tracks to process")

        if args.batch_parallel > 1:
            with ThreadPoolExecutor(max_workers=args.batch_parallel) as ex:
                futures = {
                    ex.submit(process_track, mp3, clip_pool, config, hardware, args.platform, args.dry_run): mp3
                    for mp3 in mp3_files
                }
                for fut in as_completed(futures):
                    mp3 = futures[fut]
                    try:
                        ok = fut.result()
                        logger.info(f"Finished {mp3.name}: {'OK' if ok else 'FAIL'}")
                    except Exception as e:
                        logger.error(f"Track {mp3.name} crashed: {e}")
        else:
            for i, mp3 in enumerate(mp3_files, 1):
                logger.info(f"[{i}/{len(mp3_files)}] Processing {mp3.name}")
                ok = process_track(mp3, clip_pool, config, hardware, args.platform, args.dry_run)
                logger.info(f"Result for {mp3.name}: {'SUCCESS' if ok else 'FAIL'}")
        sys.exit(0)

    else:
        logger.error("Please provide --track <mp3> or --batch to process all tracks.")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()