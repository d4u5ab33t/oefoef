#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oidasheim_OneClick_V37.20_FINAL.py
====================================
Version 37.20 – ULTIMATE COMPLETE RELEASE
- Complete Clip-Pool Semantic Vector indexing and matching
- Continuous LibSync scoring with song mood alignment
- Enhanced 4-stage Speed-Rampage filters for peak energy
- Line- and Song-Part-aware GenderTracker with hysteresis (m/w flipflop)
- Full visual storytelling alignment matching lyrics and semantic topics
- Perfect A/V sync, zero black borders, optimized NVENC/libx264 encoding
"""
import os
import sys
import sqlite3
import json
import random
import re
import subprocess
import shutil
import functools
import tempfile
from pathlib import Path
from collections import deque, defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import librosa

try:
    import oidasheim_config as CFG
    CFG.ensure_dirs()
except Exception as _cfg_err:
    CFG = None
    print(f"⚠️ oidasheim_config.py nicht geladen ({_cfg_err}) – nutze Fallback-Pfade")

MP3_ORDNER = CFG.MUSIC_ROOT if CFG else Path(r"J:\Oidasheim\Musik\FAVs\Ein Hubschrauber-Rotor")
DB_ORDNER = (CFG.DEFAULT_CLIP_DB.parent if CFG else Path(r"J:\Oidasheim\jopta\data"))
VERSION = "V37.20_FINAL"

XFADE_MIN_S = getattr(CFG, "XFADE_MIN_S", 0.3) if CFG else 0.3
XFADE_MAX_S = getattr(CFG, "XFADE_MAX_S", 1.0) if CFG else 1.0
XFADE_MAX_FRACTION = getattr(CFG, "XFADE_MAX_FRACTION", 0.4) if CFG else 0.4
MAX_XFADE_CHUNKS = getattr(CFG, "MAX_XFADE_CHUNKS", 10) if CFG else 10

PLATFORMS = {
    "TikTok": {"width": 1080, "height": 1920, "fps": 30, "bitrate": "4M", "maxrate": "6M", "bufsize": "12M", "crf": 23, "preset": "medium", "suffix": "[TikTok]", "audio_bitrate": "320k", "extra_filters": [], "target_aspect_ratio": 9/16, "aspect_tolerance": 0.2, "fill_mode": "crop"},
    "YouTube": {"width": 1920, "height": 1080, "fps": 24, "bitrate": "12M", "maxrate": "18M", "bufsize": "36M", "crf": 18, "preset": "slow", "suffix": "[YouTube]", "audio_bitrate": "320k", "extra_filters": ["unsharp=5:5:1.0:5:5:0.0"], "target_aspect_ratio": 16/9, "aspect_tolerance": 0.2, "fill_mode": "scale"}
}

BEATSYNC_CMD = r"F:\raz\BeatSync-Engine\beatsync.exe"

CULTURE_LEXICON = {
    "gender_f": ["she","her","she's","sie","ihr","mädchen","girl","queen","göttin","sistah","frau","bitch","shawty","chick","lady","diva"],
    "gender_m": ["he","him","he's","er","ihm","junge","boy","king","alter","mann","bruder","bro","dude","homie","mc","rapper","emcee","lyricist","flow","spitter"],
}

GENRE_KW_SEED = {
    "electronic": ["techno","house","electro","synth","cyberpunk","drum","bass","dnb","edm","rave","club","bpm","beatdrop","laser","strobe","neon","robot","machine","kick","snare","sub","glitch","future","digital"],
    "hiphop": ["hiphop","hip-hop","rap","trap","drill","underground","beat","flow","street","bavaria","munich","minga","corner","ganja","sesh","block","hood","grind","hustle","respekt","gang","crew","mic","freestyle","money","cash","kette","auto","bling","real","game","boss","szene"],
    "pop": ["pop","chart","dance","synthpop","radio","hit","catchy","mainstream","party","tanzen","feiern","sommer","sonne"],
    "soul": ["soul","rnb","blues","funk","jazz","groove","herz","seele","gefuehl","gefühl","zaertlich","zärtlich","sanft","warm"],
    "rock": ["rock","metal","punk","guitar","grunge","indie","gitarre","riff","band","stage","buehne","bühne","distortion","wild","laut","rebell"],
}

MOOD_KW_SEED = {
    "happy": ["happy","bright","vibrant","fun","summer","love","high","joy","smile","sunshine","free","freedom","dance","celebrate","party","together","gluecklich","glücklich","froh","freude","lachen","liebe","frei","freiheit","sonne","sommer","tanzen","feiern","zusammen","hoffnung","hope","licht","light","fly","flying","fliegen","leicht","schoen","schön","strahlen","shine","gold","hell","farben","colors","juhu","yeah"],
    "intense": ["intense","dark","aggressive","hard","heavy","evil","gothic","combat","battle","ruthless","insane","firewall","hass","hate","wut","anger","kampf","fight","krieg","war","blut","blood","schmerz","pain","angst","fear","dunkel","dark","schwarz","black","feuer","fire","brennen","burn","zerbrochen","broken","allein","alone","einsam","lonely","schrei","scream","wild","chaos","gefahr","danger","messer","gun","waffe","toedlich","tödlich","rache","revenge","stolz","pride","macht","power","hart","cold","kalt","eiskalt","brutal","laut","loud"],
    "calm": ["calm","chill","atmospheric","slow","ambient","melancholic","peaceful","dreamy","ruhig","stille","still","traurig","sad","tears","traenen","tränen","weinen","cry","regen","rain","nacht","night","mond","moon","sterne","stars","himmel","sky","meer","ocean","see","wolken","clouds","erinnerung","memory","vermissen","miss","sehnsucht","longing","nostalgie","langsam","leise","quiet","frieden","peace","atmen","breathe","warten","waiting","zeit","time","zuhause","home"],
}

@dataclass
class DirectorStyle:
    name: str
    description: str
    transient_sensitivity: float = 1.0
    stutter_frac: float = 0.22
    stutter_reps: int = 2
    stutter_every: int = 4
    preferred_effects: List[str] = field(default_factory=list)
    effect_intensity: float = 1.0
    motion_sync_strength: float = 0.45
    motion_speed_range: Tuple[float, float] = (0.72, 1.45)
    zoom_sensitivity: float = 0.25
    hold_beats: Tuple[int, int] = (6, 12)
    chroma_preference: float = 0.0

DIRECTOR_STYLES = {
    "cunningham": DirectorStyle("cunningham","Chris Cunningham – Präziser Audio-Sync",0.8,0.10,2,6,["glitch_rgb","stutter_strong","flash_white","vinyl_scratch","glitch_strong"],0.3,0.5,(0.8,1.3),0.2,(8,16),0.3),
    "gondry": DirectorStyle("gondry","Michel Gondry – Handgemachte Illusionen",0.6,0.06,2,8,["pixelate","stop_motion","fisheye","vignette","slowmo"],0.2,0.3,(0.85,1.15),0.15,(12,20),0.1),
    "jonze": DirectorStyle("jonze","Spike Jonze – Physisches Pacing",0.7,0.05,2,7,["whip_pan","flash_cut","speed_ramp","hq_sharp","cinema_grade"],0.3,0.6,(0.75,1.4),0.25,(8,14),0.2),
    "hype_williams": DirectorStyle("hype_williams","Hype Williams – Neon-Farben, Hip-Hop",0.7,0.08,2,6,["neon_flash","colorshift","fisheye","overexpose","mirror_hue","pulse_glow"],0.3,0.4,(0.8,1.3),0.3,(8,14),0.4),
    "rl_director": DirectorStyle("rl_director","RL-Bandit AI Director",0.7,0.10,2,6,[],0.3,0.4,(0.8,1.3),0.2,(8,14),0.2),
}

GENRE_DIRECTOR_PRIORITIES = {
    "electronic": ["cunningham","jonze","hype_williams","gondry","rl_director"],
    "hiphop": ["hype_williams","jonze","cunningham","rl_director","gondry"],
    "pop": ["gondry","hype_williams","jonze","cunningham","rl_director"],
    "soul": ["gondry","jonze","cunningham","hype_williams","rl_director"],
    "rock": ["jonze","cunningham","gondry","hype_williams","rl_director"],
    "other": ["rl_director","jonze","cunningham","gondry","hype_williams"],
}

CAMERA_MOVES = {
    "dolly_in": {"zoom_start":1.0,"zoom_end":1.25,"x_start":0.5,"y_start":0.5,"suitable":["verse","chorus","intro"],"energy_min":0.3,"energy_max":0.9},
    "dolly_out": {"zoom_start":1.25,"zoom_end":1.0,"x_start":0.5,"y_start":0.5,"suitable":["verse","outro","bridge"],"energy_min":0.2,"energy_max":0.8},
    "dolly_zoom": {"zoom_start":1.0,"zoom_end":1.4,"scale_start":1.0,"scale_end":0.85,"suitable":["chorus","bridge"],"energy_min":0.7,"energy_max":1.0},
    "crane_up": {"zoom_start":1.2,"zoom_end":1.0,"x_start":0.5,"y_start":0.7,"x_end":0.5,"y_end":0.3,"suitable":["chorus","outro"],"energy_min":0.5,"energy_max":1.0},
    "crane_down": {"zoom_start":1.0,"zoom_end":1.2,"x_start":0.5,"y_start":0.3,"x_end":0.5,"y_end":0.7,"suitable":["intro","verse"],"energy_min":0.2,"energy_max":0.7},
    "orbital_left": {"zoom_start":1.15,"zoom_end":1.15,"x_start":0.6,"y_start":0.5,"x_end":0.4,"y_end":0.5,"orbit":True,"suitable":["chorus","verse"],"energy_min":0.4,"energy_max":0.9},
    "orbital_right": {"zoom_start":1.15,"zoom_end":1.15,"x_start":0.4,"y_start":0.5,"x_end":0.6,"y_end":0.5,"orbit":True,"suitable":["chorus","verse"],"energy_min":0.4,"energy_max":0.9},
    "whip_pan_left": {"zoom_start":1.0,"zoom_end":1.0,"x_start":0.8,"y_start":0.5,"x_end":0.2,"y_end":0.5,"blur":8,"speed":3.0,"suitable":["chorus","bridge"],"energy_min":0.6,"energy_max":1.0},
    "whip_pan_right": {"zoom_start":1.0,"zoom_end":1.0,"x_start":0.2,"y_start":0.5,"x_end":0.8,"y_end":0.5,"blur":8,"speed":3.0,"suitable":["chorus","bridge"],"energy_min":0.6,"energy_max":1.0},
    "dutch_angle": {"rotation":8,"suitable":["bridge","chorus"],"energy_min":0.5,"energy_max":1.0},
    "rack_focus_near": {"blur_start":3.0,"blur_end":0.0,"suitable":["verse","bridge"],"energy_min":0.2,"energy_max":0.7},
    "rack_focus_far": {"blur_start":0.0,"blur_end":3.0,"suitable":["verse","bridge"],"energy_min":0.2,"energy_max":0.7},
    "tilt_shift": {"strength":0.6,"suitable":["intro","outro"],"energy_min":0.1,"energy_max":0.5},
    "perspective_tilt": {"warp_strength":0.15,"suitable":["chorus","bridge"],"energy_min":0.5,"energy_max":0.9},
    "parallax_3d": {"zoom_start":1.1,"zoom_end":1.15,"warp_strength":0.1,"suitable":["verse","chorus"],"energy_min":0.3,"energy_max":0.8},
    "hero_static": {"zoom_start":1.05,"zoom_end":1.06,"x_start":0.5,"y_start":0.5,"suitable":["intro","outro","bridge"],"energy_min":0.1,"energy_max":0.6}
}

_CODEC_CANDIDATES = ["h264_nvenc","h264_amf","h264_qsv","libx264"]

@functools.lru_cache(maxsize=1)
def detect_video_codec():
    for codec in _CODEC_CANDIDATES:
        cmd = ["ffmpeg","-y","-hide_banner","-loglevel","error","-f","lavfi","-i","color=c=black:s=320x240:d=0.3","-frames:v","3","-c:v",codec,"-f","null","-"]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=15)
            if r.returncode == 0:
                print(f"🎮 Codec: {codec}")
                return codec
        except Exception:
            continue
    print("⚠️ libx264")
    return "libx264"

@functools.lru_cache(maxsize=4096)
def probe_duration(src: str) -> float:
    try:
        out = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",src], capture_output=True, text=True, timeout=10)
        val = float(out.stdout.strip())
        return val if val > 0 else 0.1
    except Exception:
        return 0.1

def check_ffmpeg():
    for tool in ["ffmpeg","ffprobe"]:
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} nicht gefunden.")
    print("✅ ffmpeg/ffprobe")

class LibSync:
    def __init__(self):
        self.data = {}
        self.data_by_name = {}
        candidates = []
        if CFG and getattr(CFG, "LIBSYNC_JSON_PATH", None):
            candidates.append(CFG.LIBSYNC_JSON_PATH)
        candidates += [
            DB_ORDNER / "libsync-flat-globe.db.json",
            Path(r"J:\Oidasheim\jopta\data") / "libsync-flat-globe.db.json",
            Path(r"J:\Oidasheim\jopta") / "libsync-flat-globe.db.json",
        ]
        for test in candidates:
            if test and Path(test).exists():
                try:
                    with open(test, 'r', encoding='utf-8') as f:
                        self.data = json.load(f)
                    print(f"📚 LibSync: {test} ({len(self.data)} Einträge)")
                    break
                except Exception:
                    continue
        if not self.data:
            print("ℹ️ Keine libsync.json")
            return
        for k, v in self.data.items():
            try:
                self.data_by_name[Path(k).name.lower()] = v
            except Exception:
                continue
    def get_metadata(self, clip_path):
        if clip_path in self.data:
            return self.data[clip_path]
        return self.data_by_name.get(Path(clip_path).name.lower(), {})
    def score_clip(self, clip_path, energy, phase, song_mood=None):
        meta = self.get_metadata(clip_path)
        if not meta:
            return 0.0
        score = 0.0
        clip_mood = meta.get("mood")
        if song_mood and clip_mood:
            if clip_mood == song_mood:
                score += 0.35
            elif {clip_mood, song_mood} <= {"happy", "energetic"}:
                score += 0.15
            elif {clip_mood, song_mood} <= {"calm", "intense"}:
                score += 0.1
        if phase == "peak" and clip_mood == "energetic":
            score += 0.2
        if phase in ("early", "late") and clip_mood == "calm":
            score += 0.15
        intensity = meta.get("intensity", 0.5)
        try:
            intensity = float(intensity)
        except (TypeError, ValueError):
            intensity = 0.5
        score += max(0.0, 0.25 - abs(intensity - energy) * 0.25)
        return min(score, 1.0)

class SemanticMatcher:
    def __init__(self, clips):
        self.enabled = False
        self.model = None
        self.embeddings = {}
        if not CFG or getattr(CFG, "SEMANTIC_DISABLED", False):
            print("ℹ️ Semantisches Matching deaktiviert (WEEDIT_DISABLE_SEMANTIC=1)")
            return
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as ex:
            print(f"ℹ️ sentence-transformers nicht installiert ({ex}) – semantisches Matching aus")
            return
        try:
            self.model = SentenceTransformer(CFG.SEMANTIC_MODEL_NAME)
        except Exception as ex:
            print(f"⚠️ CLIP-Modell '{CFG.SEMANTIC_MODEL_NAME}' nicht ladbar: {ex}")
            return
        self.enabled = True
        self._load_cache()
        self._migrate_legacy_cache()
        if getattr(CFG, "SEMANTIC_BUILD_MISSING", False):
            self._build_missing(clips)
        print(f"🧠 SemanticMatcher: {len(self.embeddings)}/{len(clips)} Clips im Pool mit Embeddings ('aktiv' if getattr(CFG,'SEMANTIC_BUILD_MISSING',False) else 'Cache-only, WEEDIT_SEMANTIC_BUILD_MISSING=1 setzen zum Nachbauen')")
    def _load_cache(self):
        f = getattr(CFG, "SEMANTIC_CACHE_FILE", None)
        if f and Path(f).exists():
            try:
                data = np.load(f, allow_pickle=True)
                self.embeddings = {str(p): v for p, v in zip(data["paths"], data["vecs"])}
                print(f"🗄️ Semantik-Cache geladen: {len(self.embeddings)} Einträge")
            except Exception as ex:
                print(f"⚠️ Semantik-Cache defekt ({ex}) – wird neu aufgebaut")
    def _migrate_legacy_cache(self):
        if self.embeddings:
            return
        for cand in getattr(CFG, "LEGACY_SEMANTIC_CACHE_CANDIDATES", []) or []:
            if Path(cand).exists():
                try:
                    data = np.load(cand, allow_pickle=True)
                    self.embeddings = {str(p): v for p, v in zip(data["paths"], data["vecs"])}
                    print(f"🗄️ Legacy-Semantik-Cache übernommen: {cand} ({len(self.embeddings)})")
                    self._save_cache()
                    return
                except Exception:
                    continue
    def _save_cache(self):
        try:
            paths = np.array(list(self.embeddings.keys()), dtype=object)
            vecs = np.array(list(self.embeddings.values()), dtype=np.float32)
            np.savez(CFG.SEMANTIC_CACHE_FILE, paths=paths, vecs=vecs)
        except Exception as ex:
            print(f"⚠️ Semantik-Cache konnte nicht gespeichert werden: {ex}")
    def _extract_thumbs(self, path, duration):
        thumbs = []
        for frac in CFG.SEMANTIC_THUMB_FRACS:
            ts = max(0.05, (duration or 1.0) * frac)
            tmp = Path(tempfile.gettempdir()) / f"semthumb_{abs(hash((str(path), frac)))}.jpg"
            sz = CFG.SEMANTIC_FRAME_SIZE
            cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(ts), "-i", str(path), "-frames:v", "1", "-vf", f"scale={sz}:{sz}:force_original_aspect_ratio=increase,crop={sz}:{sz}", str(tmp)]
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=15)
                if r.returncode == 0 and tmp.exists():
                    thumbs.append(tmp)
            except Exception:
                continue
        return thumbs
    def _encode_clip(self, path, duration):
        try:
            from PIL import Image
        except Exception:
            return None
        thumbs = self._extract_thumbs(path, duration)
        if not thumbs:
            return None
        imgs = []
        for t in thumbs:
            try:
                imgs.append(Image.open(t).convert("RGB"))
            except Exception:
                continue
            finally:
                try:
                    t.unlink()
                except Exception:
                    pass
        if not imgs:
            return None
        try:
            vecs = self.model.encode(imgs, convert_to_numpy=True, show_progress_bar=False)
            return np.mean(vecs, axis=0)
        except Exception as ex:
            print(f"⚠️ Embedding-Fehler für {path}: {ex}")
            return None
    def _build_missing(self, clips):
        missing = [c for c in clips if c["path"] not in self.embeddings]
        if not missing:
            return
        print(f"🧠 Baue Semantik-Embeddings für {len(missing)}/{len(clips)} fehlende Clips (kompletter Pool wird erschlossen)...")
        done = 0
        flush_every = getattr(CFG, "SEMANTIC_CACHE_FLUSH_EVERY", 400)
        workers = getattr(CFG, "SEMANTIC_EXTRACT_WORKERS", 8)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(self._encode_clip, c["path"], c.get("duration_sec") or probe_duration(c["path"])): c["path"] for c in missing}
            for f in as_completed(futures):
                p = futures[f]
                try:
                    vec = f.result()
                except Exception:
                    vec = None
                if vec is not None:
                    self.embeddings[p] = vec
                done += 1
                if done % flush_every == 0:
                    self._save_cache()
                    print(f"   ...{done}/{len(missing)} Clips embedded, Cache zwischengespeichert")
        self._save_cache()
    def score(self, clip_path, query_text):
        if not self.enabled or not query_text or len(query_text.strip()) < getattr(CFG, "SEMANTIC_MIN_VOCAL_CHARS", 5):
            return 0.0
        vec = self.embeddings.get(clip_path)
        if vec is None:
            return 0.0
        try:
            qvec = self.model.encode([query_text], convert_to_numpy=True, show_progress_bar=False)[0]
            denom = (np.linalg.norm(vec) * np.linalg.norm(qvec)) + 1e-9
            return max(0.0, float(np.dot(vec, qvec) / denom))
        except Exception:
            return 0.0

class BeatSyncEngineCLI:
    def __init__(self):
        self.cmd = None
        self.available = False
        if BEATSYNC_CMD and Path(BEATSYNC_CMD).exists():
            try:
                test_cmd = [BEATSYNC_CMD, "--help"]
                r = subprocess.run(test_cmd, capture_output=True, timeout=2)
                if r.returncode == 0:
                    self.cmd = BEATSYNC_CMD
                    self.available = True
                    print(f"✅ BeatSync-Engine gefunden: {BEATSYNC_CMD}")
            except Exception:
                pass
        if not self.available:
            print("ℹ️ Keine BeatSync-Engine – verwende libROSA")
    def analyze(self, audio_path):
        if not self.available:
            raise RuntimeError("BeatSync-Engine nicht verfügbar.")
        cmd = [self.cmd, "--input", str(audio_path), "--format", "json"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                raise RuntimeError(f"Engine-Fehler: {r.stderr}")
            data = json.loads(r.stdout)
            return {
                "bpm": data.get("bpm", 90.0),
                "duration_ms": data.get("duration_ms", 0),
                "energy_map": data.get("energy", []),
                "bass_energy": data.get("bass_energy", 0.0),
                "onsets_ms": data.get("onsets", []),
                "beat_times_ms": data.get("beats", []),
                "section_bounds_ms": data.get("sections", []),
                "bpm_times_ms": data.get("bpm_times", []),
                "bpm_values": data.get("bpm_values", []),
                "repetition_times_ms": data.get("repetitions", []),
                "slide_times_ms": data.get("slides", []),
            }
        except Exception as e:
            raise RuntimeError(f"Engine-Aufruf fehlgeschlagen: {e}")

class Analyzer:
    def __init__(self):
        self.engine = BeatSyncEngineCLI()
        self.use_engine = self.engine.available
    def analyze(self, path):
        if self.use_engine:
            try:
                return self.engine.analyze(path)
            except Exception as e:
                print(f"⚠️ BeatSync-Engine Fehler: {e}, Fallback libROSA")
                return self._analyze_librosa(path)
        else:
            return self._analyze_librosa(path)
    def _analyze_librosa(self, path):
        y, sr = librosa.load(path, sr=22050, mono=True)
        rms = librosa.feature.rms(y=y)[0]
        stft = np.abs(librosa.stft(y))
        bass_energy = float(np.mean(stft[:10,:]))
        duration_ms = int(len(y) / sr * 1000)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=False)
        bpm = float(np.atleast_1d(tempo)[0]) if tempo > 0 else 90.0
        beat_times_ms = (librosa.frames_to_time(beat_frames, sr=sr) * 1000).tolist()
        if len(beat_times_ms) < 4:
            step = 60000.0 / bpm
            beat_times_ms = list(np.arange(0, duration_ms, step))
        if not beat_times_ms or beat_times_ms[-1] < duration_ms:
            beat_times_ms.append(float(duration_ms))
        hop = int(sr * 0.5)
        try:
            tempo_frames = librosa.feature.rhythm.tempo(y=y, sr=sr, hop_length=hop, aggregate=None)
        except Exception:
            tempo_frames = librosa.beat.tempo(y=y, sr=sr, hop_length=hop, aggregate=None)
        bpm_times_ms = (np.arange(len(tempo_frames)) * hop + int(sr*1)) / sr * 1000
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
        onset_times_ms = librosa.frames_to_time(onsets, sr=sr) * 1000
        rep, slides = self._accents(y, sr, onset_times_ms, duration_ms)
        sections = self._sections(y, sr, duration_ms)
        return {
            "bpm": round(bpm, 1),
            "duration_ms": duration_ms,
            "energy_map": (rms / (np.max(rms)+1e-9)).tolist(),
            "bass_energy": bass_energy,
            "onsets_ms": onset_times_ms.tolist(),
            "beat_times_ms": beat_times_ms,
            "section_bounds_ms": sections,
            "bpm_times_ms": bpm_times_ms.tolist(),
            "bpm_values": tempo_frames.tolist(),
            "repetition_times_ms": rep,
            "slide_times_ms": slides,
        }
    def _sections(self, y, sr, dur):
        try:
            hop=512
            chroma=librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
            mfcc=librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop)
            feats=np.vstack([chroma,mfcc])
            n=max(3,min(12,int(dur/1000/22)))
            bounds=librosa.segment.agglomerative(feats, n)
            bt=(librosa.frames_to_time(bounds, sr=sr, hop_length=hop)*1000).tolist()
            return sorted(set([0.0]+bt+[float(dur)]))
        except Exception:
            return [0.0, dur*0.25, dur*0.75, float(dur)]
    def _accents(self, y, sr, onsets_ms, dur):
        hop=512
        chroma=librosa.feature.chroma_stft(y=y, sr=sr, hop_length=hop)
        ct=librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop)*1000
        oi=np.searchsorted(ct, onsets_ms)
        oi=np.clip(oi,0,len(ct)-1)
        rep=[]
        for i in range(1,len(oi)):
            p=oi[i-1]
            c=oi[i]
            if p<len(ct) and c<len(ct):
                corr=np.corrcoef(chroma[:,p], chroma[:,c])[0,1]
                if corr>0.8 and (onsets_ms[i]-onsets_ms[i-1])<500:
                    rep.append((onsets_ms[i-1]+onsets_ms[i])/2.0)
        sc=librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
        st=librosa.frames_to_time(np.arange(len(sc)), sr=sr, hop_length=hop)*1000
        slides=[]
        for i in range(1,len(sc)):
            if (st[i]-st[i-1])<1000:
                diff=sc[i]-sc[i-1]
                rel=abs(diff)/(sc[i-1]+1e-6)
                if rel>0.3:
                    slides.append(st[i])
        return rep, slides

class LyricAligner:
    def __init__(self, lyrics):
        self.lines = [l.strip() for l in (lyrics or "").split("\n") if l.strip()]
        self.n = len(self.lines)
    def line_index(self, ms, dur):
        if self.n == 0 or dur <= 0:
            return -1
        prog = min(1.0, max(0.0, ms / dur))
        return min(self.n - 1, int(prog * self.n))
    def window_text(self, ms, dur, span=2):
        idx = self.line_index(ms, dur)
        if idx < 0:
            return ""
        lo = max(0, idx - span)
        hi = min(self.n, idx + span + 1)
        return " ".join(self.lines[lo:hi])

class GenderTracker:
    def __init__(self, aligner):
        self.aligner = aligner
        self.last_gender = "neutral"
        self.last_song_part = None
        self.streak = 0
    def update(self, ms, dur, song_part):
        if self.aligner.n == 0 or dur <= 0:
            return "neutral"
        seg = self.aligner.window_text(ms, dur, span=2).lower()
        f = sum(1 for k in CULTURE_LEXICON["gender_f"] if re.search(r'\b' + re.escape(k) + r'\b', seg))
        m = sum(1 for k in CULTURE_LEXICON["gender_m"] if re.search(r'\b' + re.escape(k) + r'\b', seg))
        mc = any(re.search(r'\b' + t + r'\b', seg) for t in ["mc", "emcee", "rapper", "lyricist"])
        if mc and f == 0:
            candidate = "male"
        elif f > m:
            candidate = "female"
        elif m > f:
            candidate = "male"
        else:
            candidate = self.last_gender
        part_changed = song_part != self.last_song_part
        if part_changed:
            self.last_gender = candidate
            self.streak = 1
        elif candidate != self.last_gender:
            self.streak += 1
            if self.streak >= 2:
                self.last_gender = candidate
                self.streak = 0
        else:
            self.streak = 0
        self.last_song_part = song_part
        return self.last_gender

def section_idx(ms, bounds):
    for i in range(len(bounds)-1):
        if bounds[i]<=ms<bounds[i+1]:
            return i
    return max(0,len(bounds)-2)

def phase(si,n):
    return "early" if si<=0 else "late" if si>=n-1 else "peak"

def onset_density(ms,dur,onsets):
    return sum(1 for t in onsets if ms<=t<ms+dur) / max(0.1,dur/1000)

def energy_slope(seg):
    n=len(seg)
    if n<3:
        return 0.0
    x=np.arange(n)
    y=np.array(seg)
    return np.clip(np.cov(x,y,ddof=0)[0,1]/np.var(x) if np.var(x)>0 else 0.0, -0.1, 0.1)

def bpm_at(ms, times, vals, default):
    if not times:
        return default
    idx=np.searchsorted(times, ms)-1
    idx=max(0,min(idx,len(vals)-1))
    return vals[idx]

def get_clip_aspect_ratio(clip):
    w = clip.get("width", 0)
    h = clip.get("height", 0)
    if w > 0 and h > 0:
        return w / h
    meta = clip.get("metadata")
    if meta:
        try:
            info = json.loads(meta)
            w = info.get("width", 0)
            h = info.get("height", 0)
            if w > 0 and h > 0:
                return w / h
        except Exception:
            pass
    return 1.7778

def aspect_ratio_score(clip, target_ratio, tolerance):
    ratio = get_clip_aspect_ratio(clip)
    diff = abs(ratio - target_ratio) / max(target_ratio, 0.001)
    if diff <= tolerance:
        return 1.0 - (diff / tolerance)
    return 0.0

class ELFDirector:
    def __init__(self, base):
        self.base=base
        self.fps=24
        self.learning_file=base/"elf_learning.json"
        self.learning_data=self._load()
        self.style = None
    def _load(self):
        if self.learning_file.exists():
            try:
                with open(self.learning_file,'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"genre": defaultdict(int), "mood": defaultdict(int), "total": 0}
    def _save(self):
        try:
            with open(self.learning_file,'w') as f:
                json.dump(self.learning_data, f, indent=2)
        except Exception:
            pass
    def extract(self, lyrics):
        if not lyrics:
            return "other","calm"
        words=set(re.findall(r'\b[a-zäöüß]+\b', lyrics.lower()))
        gs={g:0 for g in GENRE_KW_SEED}
        for g,kw in GENRE_KW_SEED.items():
            for k in kw:
                if k in words:
                    gs[g]+=1
        genre=max(gs,key=gs.get) if any(gs.values()) else "other"
        ms={m:0 for m in MOOD_KW_SEED}
        for m,kw in MOOD_KW_SEED.items():
            for k in kw:
                if k in words:
                    ms[m]+=1
        mood=max(ms,key=ms.get) if any(ms.values()) else "calm"
        return genre, mood
    def select_style(self, genre, mood):
        priority=GENRE_DIRECTOR_PRIORITIES.get(genre, GENRE_DIRECTOR_PRIORITIES["other"])
        gs=self.learning_data["genre"].get(genre,{})
        ms=self.learning_data["mood"].get(mood,{})
        weights={s: gs.get(s,0)+ms.get(s,0)+1 for s in priority}
        styles=list(weights.keys())
        w=list(weights.values())
        if random.random()<0.2:
            return random.choice(priority)
        return random.choices(styles, weights=w, k=1)[0]
    def update(self, genre, mood, style):
        self.learning_data["genre"].setdefault(genre,{}).setdefault(style,0)
        self.learning_data["genre"][genre][style]+=1
        self.learning_data["mood"].setdefault(mood,{}).setdefault(style,0)
        self.learning_data["mood"][mood][style]+=1
        self.learning_data["total"]+=1
        self._save()
    def plan_camera(self, phase, energy, dur, prev=None, song_part=None, max_zoom=1.5):
        cand=[]
        for name,p in CAMERA_MOVES.items():
            if phase not in p.get("suitable",[]):
                continue
            if not (p["energy_min"]<=energy<=p["energy_max"]):
                continue
            if prev and name==prev and random.random()<0.6:
                continue
            if song_part == "chorus" and name in ["dolly_zoom","crane_up","whip_pan_left","whip_pan_right"]:
                cand.append((name,p))
            elif song_part == "verse" and name in ["dolly_in","dolly_out","orbital_left","orbital_right"]:
                cand.append((name,p))
            elif song_part == "bridge" and name in ["dutch_angle","rack_focus_near","rack_focus_far","hero_static"]:
                cand.append((name,p))
            elif song_part == "intro" and name in ["dolly_in","hero_static","tilt_shift"]:
                cand.append((name,p))
            elif song_part == "outro" and name in ["dolly_out","crane_down","hero_static"]:
                cand.append((name,p))
            else:
                cand.append((name,p))
        if not cand:
            return None
        name,p=random.choice(cand)
        frames=max(1,int(dur/1000*self.fps))
        zs=p.get("zoom_start",1.0)
        ze=p.get("zoom_end",zs)
        ze = min(ze, max_zoom)
        if ze < zs:
            ze = zs
        xs=p.get("x_start",0.5)
        xe=p.get("x_end",xs)
        ys=p.get("y_start",0.5)
        ye=p.get("y_end",ys)
        ease = "(3*pow(on/{f},2)-2*pow(on/{f},3))".format(f=frames)
        return {
            "z_expr": f"{zs}+({ze}-{zs})*{ease}",
            "z_end": ze,
            "x": f"iw/2-(iw/zoom/2)+(({xe}-{xs})*iw/2)*{ease}",
            "y": f"ih/2-(ih/zoom/2)+(({ye}-{ys})*ih/2)*{ease}",
            "dir": (1 if xe>xs else -1, 1 if ye>ys else -1),
            "move_name": name,
            "rotation_deg": p.get("rotation"),
            "warp_strength": p.get("warp_strength"),
            "pan_blur": p.get("blur"),
            "pan_speed": p.get("speed"),
            "rack_blur_start": p.get("blur_start"),
            "rack_blur_end": p.get("blur_end"),
            "tilt_strength": p.get("strength"),
        }
    def plan_motion(self, action, phase, energy, dur, pzoom, pdir, changed, prev, song_part=None, max_zoom=1.5):
        if not (action and phase=="peak" and energy>0.8 and dur>1500):
            if not (phase=="peak" and energy>0.5 and dur>2000):
                return None
        move=self.plan_camera(phase, energy, dur, prev, song_part, max_zoom=max_zoom)
        if not move:
            return None
        zs=max(1.0, pzoom)
        ze=min(move["z_end"], max_zoom)
        if ze<zs and not changed:
            ze=min(zs+0.02, max_zoom)
        frames=max(1,int(dur/1000*self.fps))
        ease = "(3*pow(on/{f},2)-2*pow(on/{f},3))".format(f=frames)
        move["z_expr"]=f"{zs}+({ze}-{zs})*{ease}"
        move["z_end"]=ze
        return move

class OidasheimMultiPlatform:
    def __init__(self):
        check_ffmpeg()
        self.version = VERSION
        self.codec = detect_video_codec()
        self.libsync = LibSync()
        self.analyzer = Analyzer()
        db = self._find_db()
        print(f"📀 DB: {db}")
        self.conn = sqlite3.connect(str(db))
        self.conn.row_factory = sqlite3.Row
        self.clips = [dict(r) for r in self.conn.execute("SELECT * FROM clips").fetchall()]
        for c in self.clips:
            if "duration_sec" not in c:
                meta = c.get("metadata")
                if meta:
                    try:
                        info = json.loads(meta)
                        c["duration_sec"] = info.get("duration", 0.0)
                        c["width"] = info.get("width", 0)
                        c["height"] = info.get("height", 0)
                    except Exception:
                        c["duration_sec"] = 0.0
                        c["width"] = 0
                        c["height"] = 0
                else:
                    c["duration_sec"] = 0.0
                    c["width"] = 0
                    c["height"] = 0
        self.semantic = SemanticMatcher(self.clips)
        self.elf = ELFDirector(MP3_ORDNER)
        self.temp = Path(os.environ.get("TEMP", ".")) / "render_final"
        if self.temp.exists():
            shutil.rmtree(self.temp)
        self.temp.mkdir(parents=True, exist_ok=True)
        print(f"🎯 MP3: {MP3_ORDNER}")
        self.skipped_clips = 0
    def _find_db(self):
        override = os.environ.get("WEEDIT_DB_OVERRIDE")
        if override and Path(override).exists():
            return Path(override)
        if CFG:
            for cand in [getattr(CFG, "DEFAULT_CLIP_DB", None), getattr(CFG, "DB_PATH", None)]:
                if cand and Path(cand).exists():
                    return Path(cand)
        dbs = []
        for p in [DB_ORDNER, Path(r"J:\Oidasheim\jopta\data"), Path(r"I:\Oidasheim\abfuck\honestly")]:
            if p.exists():
                dbs.extend(p.glob("*.db"))
        if not dbs:
            raise FileNotFoundError("Keine Clip-Datenbank gefunden.")
        dbs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return dbs[0]
    def _pick(self, gender, phase, energy, recent, avoid, needed_duration, song_part=None, platform=None, song_mood=None, topic_text=None):
        pool = [c for c in self.clips if (c.get("gender") or "neutral") == gender] or self.clips
        candidates = [c for c in pool if c.get("duration_sec", 0) >= needed_duration]
        if not candidates:
            candidates = pool
        cand = [c for c in candidates if c["path"] not in recent] or candidates
        if avoid:
            key = "scene" if cand and "scene" in cand[0] else ("tag" if cand and "tag" in cand[0] else None)
            if key:
                varied = [c for c in cand if c.get(key) not in avoid]
                if varied:
                    cand = varied
        sem_weight = (getattr(CFG, "SEMANTIC_SCORE_WEIGHT", 30.0) if CFG else 30.0) / 100.0
        scored = []
        for c in cand:
            base_score = 0.0
            if self.libsync.data:
                base_score += self.libsync.score_clip(c["path"], energy, phase, song_mood=song_mood)
            if platform:
                plat = PLATFORMS[platform]
                ar_score = aspect_ratio_score(c, plat["target_aspect_ratio"], plat["aspect_tolerance"])
                base_score += ar_score * 0.3
            meta = self.libsync.get_metadata(c["path"])
            if song_part == "chorus" and meta.get("mood") == "energetic":
                base_score += 0.3
            elif song_part == "verse" and meta.get("mood") in ["calm", "neutral"]:
                base_score += 0.2
            elif song_part == "bridge" and meta.get("mood") in ["intense", "calm"]:
                base_score += 0.25
            if self.semantic.enabled and topic_text:
                base_score += self.semantic.score(c["path"], topic_text) * sem_weight
            base_score += random.uniform(0, 0.1)
            scored.append((base_score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = max(1, int(len(scored) * 0.3))
        clip = random.choice([c for _, c in scored[:top]])
        recent.append(clip["path"])
        return clip
    def _plan(self, mp3, lyrics, platform=None):
        print(f"📝 Planning: {mp3.name} für {platform or 'All'}")
        data = self.analyzer.analyze(mp3)
        genre, mood = self.elf.extract(lyrics)
        style = self.elf.select_style(genre, mood)
        print(f"🎬 {genre}/{mood} → {style}")
        plan = {
            "title": mp3.stem,
            "mp3": str(mp3),
            "bpm": data["bpm"],
            "duration_ms": data["duration_ms"],
            "fade_in_ms": 100,
            "fade_out_ms": 100,
            "timeline": [],
            "genre": genre,
            "mood": mood,
            "director": style,
            "version": self.version
        }
        recent = deque(maxlen=20)
        aligner = LyricAligner(lyrics)
        gender_tracker = GenderTracker(aligner)
        beat = data["beat_times_ms"]
        sections = data["section_bounds_ms"]
        n = len(sections) - 1
        emap = data["energy_map"]
        bpmt = data.get("bpm_times_ms", [])
        bpmv = data.get("bpm_values", [])
        base = data["bpm"]
        first = None
        pzoom = 1.0
        pdir = (0, 0)
        pphase = None
        pkeys = set()
        ckeys = set()
        pmove = None
        b = 0
        curr = 0.0
        while curr < data["duration_ms"] and b < len(beat) - 1:
            idx = min(int(curr / data["duration_ms"] * len(emap)), len(emap) - 1)
            energy = float(emap[idx])
            si = section_idx(curr, sections)
            ph = phase(si, n)
            action = energy > 0.70 or ph == "peak"
            changed = (ph != pphase) if pphase else False
            if pphase is not None and ph != pphase:
                pkeys = ckeys
                ckeys = set()
            if si == 0:
                song_part = "intro"
            elif si == n - 1:
                song_part = "outro"
            else:
                if energy > 0.7 and ph == "peak":
                    song_part = "chorus"
                elif energy < 0.5 and ph != "early":
                    song_part = "bridge"
                else:
                    song_part = "verse"
            cbpm = bpm_at(curr, bpmt, bpmv, base)
            sf = max(0.7, min(1.5, cbpm / base))
            if song_part == "chorus":
                base_beats = 1 if energy > 0.85 else 2
            elif song_part == "bridge":
                base_beats = 3 if energy < 0.6 else 2
            elif song_part in ["intro", "outro"]:
                base_beats = 4
            else:
                base_beats = 2 if energy > 0.6 else 3
            se = min(int(curr / data["duration_ms"] * len(emap)), len(emap) - 1)
            ee = min(int(((curr + 2 * 60000 / base) / data["duration_ms"]) * len(emap)), len(emap) - 1)
            if ee <= se:
                ee = min(se + 2, len(emap) - 1)
            es = emap[se:ee + 1]
            sl = energy_slope(es) if len(es) > 2 else 0.0
            if abs(sl) > 0.03:
                adjustment = -1 if sl > 0.03 else 1
                base_beats = max(1, base_beats + adjustment)
            n_beats = max(1, int(round(base_beats * sf)))
            n_beats = max(1, min(6, n_beats))
            eb = min(b + n_beats, len(beat) - 1)
            nc = beat[eb]
            dur = nc - curr
            if energy > 0.35 and random.random() < 0.35:
                dur = max(120.0, dur + dur * random.uniform(-0.06, 0.06))
            if curr + dur > data["duration_ms"]:
                dur = data["duration_ms"] - curr
            if dur < 80:
                b = eb if eb > b else b + 1
                if b >= len(beat) - 1:
                    break
                continue
            needed_duration = dur / 1000.0
            dens = onset_density(curr, dur, data["onsets_ms"])
            roll = dens > 6.0
            gender = gender_tracker.update(curr, data["duration_ms"], song_part)
            topic_text = aligner.window_text(curr, data["duration_ms"], span=3)
            accent = None
            if ph == "peak" and energy > 0.7:
                for t in data.get("repetition_times_ms", []):
                    if abs(curr - t) < 200:
                        accent = "repeat"
                        break
            if not accent:
                for t in data.get("slide_times_ms", []):
                    if abs(curr - t) < 200:
                        accent = "slide"
                        break
            if ph == "late" and si == n - 1 and first is not None and random.random() < 0.5:
                clip = first
            else:
                clip = self._pick(gender, ph, energy, recent, pkeys if changed else None, needed_duration, song_part, platform, song_mood=mood, topic_text=topic_text)
            if first is None:
                first = clip
            ckeys.add(clip.get("scene") or clip.get("tag") or clip["path"])
            src_w = clip.get("width", 0) or 0
            src_h = clip.get("height", 0) or 0
            if platform and src_w and src_h:
                tw, th = PLATFORMS[platform]["width"], PLATFORMS[platform]["height"]
                upscale = max(tw / src_w, th / src_h)
            else:
                upscale = 1.0
            if upscale <= 1.15:
                max_zoom = 1.5
            elif upscale <= 1.6:
                max_zoom = 1.25
            else:
                max_zoom = 1.1
            cam = self.elf.plan_motion(action, ph, energy, dur, pzoom, pdir, changed, pmove, song_part, max_zoom=max_zoom)
            if cam:
                pzoom = cam["z_end"]
                pdir = cam["dir"]
                pmove = cam.get("move_name")
            else:
                pzoom = 1.0
                pdir = (0, 0)
                pmove = None
            plan["timeline"].append({
                "src": clip["path"],
                "duration": round(dur / 1000, 3),
                "ms": curr,
                "energy": energy,
                "phase": ph,
                "is_action": action,
                "has_roll": roll,
                "density": dens,
                "section": si,
                "cam": cam,
                "energy_slope": sl,
                "accent_type": accent,
                "song_part": song_part,
                "mood": mood,
                "genre": genre,
                "src_w": src_w,
                "src_h": src_h,
                "tempo_factor": sf,
                "bpm": cbpm,
            })
            curr += dur
            b = eb
            pphase = ph
        self.elf.update(genre, mood, style)
        return plan
    def _build_beatsync_filters(self, e, dur, total_frames):
        filters = []
        sl = e.get("energy_slope", 0.0)
        if sl > 0.015 and e.get("phase") == "peak" and dur > 0.8:
            steps = 4
            seg = max(1, total_frames // steps)
            boost = min(0.5, sl * 6.0)
            expr = "PTS"
            for s in reversed(range(steps)):
                s0 = s * seg
                s1 = s0 + seg
                speed = 1.0 + (s / (steps - 1)) * boost
                expr = f"if(between(N,{s0},{s1}),PTS*{speed:.3f},{expr})"
            filters.append(f"setpts='{expr}'")
        elif abs(sl) > 0.01 and dur > 1.0:
            filters.append(f"setpts='PTS*(1+{sl*0.08}*(N/{total_frames}))'")
        if e.get("has_roll") and e["phase"] == "peak" and e["energy"] > 0.8 and dur > 1.0:
            stutter_len = max(2, int(total_frames * 0.08))
            stutter_start = int(total_frames * 0.3)
            filters.append(f"setpts='if(gt(N,{stutter_start})*lt(N,{stutter_start+stutter_len}),PTS*0.85,PTS)'")
        if e.get("accent_type") == "repeat" and e["phase"] == "peak" and e["energy"] > 0.7 and dur > 1.0:
            dens = e.get("density", 6.0)
            reps = 2 if dens < 8 else (3 if dens < 14 else 4)
            seg_len = max(2, int(total_frames * 0.07))
            start = int(total_frames * 0.15)
            expr = "PTS"
            for r in reversed(range(reps)):
                s0 = start + r * seg_len
                s1 = s0 + seg_len
                speed = 0.55 if r % 2 == 0 else 1.75
                expr = f"if(between(N,{s0},{s1}),PTS*{speed},{expr})"
            filters.append(f"setpts='{expr}'")
            shift = min(6, 2 + int(dens * 0.3))
            filters.append(f"chromashift=crh={shift}:crv=-{shift}")
            filters.append(f"tblend=all_mode=grainextract:all_opacity={min(0.5, 0.15 + dens * 0.02):.2f}")
        return filters
    def _render_chunk(self, platform, i, e):
        plat = PLATFORMS[platform]
        out = self.temp / f"{platform}_{i:05d}.mp4"
        dur = float(e["duration"])
        src = str(e["src"])
        cl = probe_duration(src)
        if cl < 0.1 or cl < dur:
            self.skipped_clips += 1
            return None
        max_ss = max(0.0, cl - dur - 0.2)
        ss = random.uniform(0, max_ss) if max_ss > 0 else 0.0
        total_frames = max(1, int(dur * plat["fps"]))
        cam = e.get("cam")
        song_part = e.get("song_part", "verse")
        mood = e.get("mood", "calm")
        src_w = e.get("src_w", 0) or 0
        src_h = e.get("src_h", 0) or 0
        vf = []
        vf.extend(self._build_beatsync_filters(e, dur, total_frames))
        needs_prescale = bool(src_w and src_h and (src_w < plat["width"] or src_h < plat["height"]))
        if needs_prescale:
            vf.append(f"scale={plat['width']}:{plat['height']}:force_original_aspect_ratio=increase:flags=lanczos")
        if cam:
            z_expr = cam['z_expr']
            x_expr = cam['x'] or "iw/2-(iw/zoom/2)"
            y_expr = cam['y'] or "ih/2-(ih/zoom/2)"
            vf.append(f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s=iw:ih:fps={plat['fps']}")
        if cam.get("rotation_deg"):
            vf.append(f"rotate={cam['rotation_deg']}*PI/180:c=black@0")
        if cam.get("warp_strength"):
            w = min(0.18, cam["warp_strength"])
            vf.append(f"perspective=x0=0:y0=(ih*{w*0.4}):x1=iw:y1=0:x2=0:y2=ih:x3=iw:y3=(ih-(ih*{w*0.4})):interpolation=linear")
        if needs_prescale:
            vf.append(f"crop={plat['width']}:{plat['height']}")
        elif plat.get("fill_mode") == "crop":
            vf.append(f"scale={plat['width']}:{plat['height']}:force_original_aspect_ratio=increase:flags=lanczos")
            vf.append(f"crop={plat['width']}:{plat['height']}")
        else:
            vf.append(f"scale={plat['width']}:{plat['height']}:flags=lanczos")
        vf.append("format=yuv420p")
        vcodec = ["-c:v", self.codec, "-preset", "p4", "-cq", str(plat["crf"]), "-b:v", plat["bitrate"], "-maxrate", plat["maxrate"], "-bufsize", plat["bufsize"]] if self.codec != "libx264" else ["-c:v", "libx264", "-preset", plat["preset"], "-crf", str(plat["crf"]), "-b:v", plat["bitrate"], "-maxrate", plat["maxrate"], "-bufsize", plat["bufsize"]]
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(ss), "-i", src, "-t", str(dur), "-vf", ",".join(vf), *vcodec, "-c:a", "aac", "-b:a", plat["audio_bitrate"], "-r", str(plat["fps"]), str(out)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0 or not out.exists():
                return None
            return out
        except Exception:
            return None
    def _sanitize_title(self, title):
        return re.sub(r'[\\/*?:"<>|]', '', title).strip()
    def _output_path(self, title, platform):
        return MP3_ORDNER / f"{self._sanitize_title(title)} {PLATFORMS[platform]['suffix']} [BeatSync-{self.version}].mp4"
    def _dynamic_xfade_duration(self, e_prev, e_next, dur_prev, dur_next):
        energy = ((e_prev.get("energy", 0.5) if e_prev else 0.5) + (e_next.get("energy", 0.5) if e_next else 0.5)) / 2.0
        tf = ((e_prev.get("tempo_factor", 1.0) if e_prev else 1.0) + (e_next.get("tempo_factor", 1.0) if e_next else 1.0)) / 2.0
        fast_factor = min(1.0, max(0.0, energy * 0.6 + max(0.0, (tf - 0.7) / 0.8) * 0.4))
        raw = XFADE_MAX_S - (XFADE_MAX_S - XFADE_MIN_S) * fast_factor
        return max(0.08, min(XFADE_MAX_S, raw, min(dur_prev, dur_next) * XFADE_MAX_FRACTION))
    def _pick_transition(self, e):
        cam = (e or {}).get("cam") or {}
        move = cam.get("move_name")
        if (e or {}).get("accent_type") == "repeat":
            return "pixelize"
        mapping = {"whip_pan_left": "wipeleft", "whip_pan_right": "wiperight", "crane_up": "slideup", "crane_down": "slidedown", "dolly_in": "zoomin"}
        return mapping.get(move, "dissolve")
    def _xfade_chain(self, platform, video_paths, transitions, durations, out_path):
        plat = PLATFORMS[platform]
        video_paths = [Path(p) for p in video_paths]
        if len(video_paths) == 1:
            shutil.copy(video_paths[0], out_path)
            return out_path
        durs = [probe_duration(str(p)) for p in video_paths]
        inputs = []
        for p in video_paths:
            inputs += ["-i", str(p)]
        filter_parts = []
        running = durs[0]
        last_label = "0:v"
        for idx in range(1, len(video_paths)):
            xfd = durations[idx - 1] if idx - 1 < len(durations) else XFADE_MIN_S
            offset = max(0.0, running - xfd)
            trans = transitions[idx - 1] if idx - 1 < len(transitions) else "dissolve"
            out_label = f"vx{idx}"
            filter_parts.append(f"[{last_label}][{idx}:v]xfade=transition={trans}:duration={xfd:.3f}:offset={offset:.3f}[{out_label}]")
            running = offset + xfd + max(0.0, durs[idx] - xfd)
            last_label = out_label
        filter_complex = ";".join(filter_parts)
        vcodec = ["-c:v", self.codec, "-preset", "p4", "-cq", str(plat["crf"]), "-b:v", plat["bitrate"], "-maxrate", plat["maxrate"], "-bufsize", plat["bufsize"]] if self.codec != "libx264" else ["-c:v", "libx264", "-preset", plat["preset"], "-crf", str(plat["crf"]), "-b:v", plat["bitrate"], "-maxrate", plat["maxrate"], "-bufsize", plat["bufsize"]]
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", filter_complex, "-map", f"[{last_label}]", *vcodec, "-an", str(out_path)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if r.returncode == 0 and out_path.exists():
                return out_path
        except Exception:
            pass
        return video_paths[0]
    def _merge_for_platform(self, plan, platform):
        out = self._output_path(plan["title"], platform)
        print(f"⚔️ Rendering {platform}: {plan['title']} ({len(plan['timeline'])} Chunks)")
        chunk_map = {}
        self.skipped_clips = 0
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = {ex.submit(self._render_chunk, platform, i, e): i for i, e in enumerate(plan["timeline"])}
            for f in as_completed(futures):
                r = f.result()
                if r and r.exists():
                    chunk_map[futures[f]] = r
        if not chunk_map:
            return None
        indices = sorted(chunk_map.keys())
        chunks = [chunk_map[i] for i in indices]
        timeline = plan["timeline"]
        xfade_durs, xfade_types = [], []
        for k in range(len(indices) - 1):
            i_a, i_b = indices[k], indices[k + 1]
            e_a = timeline[i_a] if i_a < len(timeline) else {}
            e_b = timeline[i_b] if i_b < len(timeline) else {}
            xfade_durs.append(self._dynamic_xfade_duration(e_a, e_b, float(e_a.get("duration", 1.0) or 1.0), float(e_b.get("duration", 1.0) or 1.0)))
            xfade_types.append(self._pick_transition(e_a))
        final_video = self._xfade_chain(platform, chunks, xfade_types, xfade_durs, self.temp / f"{platform}_full_video.mp4")
        if not final_video or not Path(final_video).exists():
            return None
        total_dur = probe_duration(str(final_video))
        fi = plan["fade_in_ms"] / 1000
        fo = plan["fade_out_ms"] / 1000
        fos = max(0, total_dur - fo)
        vf = f"fade=t=in:st=0:d={fi},fade=t=out:st={fos}:d={fo}"
        af = f"afade=t=in:st=0:d={fi},afade=t=out:st={fos}:d={fo}"
        plat = PLATFORMS[platform]
        vcodec = ["-c:v", self.codec, "-preset", "p4", "-cq", str(plat["crf"]), "-b:v", plat["bitrate"], "-maxrate", plat["maxrate"], "-bufsize", plat["bufsize"]] if self.codec != "libx264" else ["-c:v", "libx264", "-preset", plat["preset"], "-crf", str(plat["crf"]), "-b:v", plat["bitrate"], "-maxrate", plat["maxrate"], "-bufsize", plat["bufsize"]]
        cmd = ["ffmpeg", "-y", "-i", str(final_video), "-i", plan["mp3"], "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]", "-map", "[v]", "-map", "[a]", *vcodec, "-c:a", "aac", "-b:a", plat["audio_bitrate"], "-shortest", str(out)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.temp), timeout=600)
            if r.returncode == 0:
                print(f"✅ {platform}: {out.name}")
                return out
        except Exception:
            pass
        return None
    def run(self):
        mp3s = list(MP3_ORDNER.glob("*.mp3"))
        if not mp3s:
            print(f"❌ Keine MP3s in {MP3_ORDNER}")
            return
        print(f"🎵 {len(mp3s)} MP3s gefunden – verarbeite ALLE (RESET)")
        for mp3 in mp3s:
            lyrics = ""
            txt = mp3.with_suffix(".txt")
            if txt.exists():
                try:
                    with open(txt, 'r', encoding='utf-8') as f:
                        lyrics = f.read()
                    print(f"📜 Lyrics: {txt.name}")
                except Exception:
                    pass
            for platform in PLATFORMS.keys():
                print(f"\n🎬 Plane für {platform}")
                plan = self._plan(mp3, lyrics, platform)
                self._merge_for_platform(plan, platform)
        print("\n🏁 ALLE EXPORTE FERTIG")

if __name__ == "__main__":
    OidasheimMultiPlatform().run()
