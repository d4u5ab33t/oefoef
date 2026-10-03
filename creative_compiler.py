#!/usr/bin/env python3
"""
creative_compiler.py — WE.ED.IT Omega & Creative Compiler OS (C+ Engine)
Location: J:\\Oidasheim\\oefoef\\creative_compiler.py

Modern Intermediate Representation (SongIR / SceneIR), Self-Learning Experience Kernel,
and Self-Critic Optimizer for Autonomous Beat-Synchronized Music Video Production.
"""

import os
import sqlite3
import random
import uuid
import time
import math
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union

from config import DATA_DIR, BRAIN_BUG_DIR
import cxx_accel


# ── Intermediate Representations (IR) ─────────────────────────────────────────

@dataclass
class Observation:
    event_type: str
    context: str
    uncertainty: float
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class SongIR:
    """Intermediate representation of an analyzed song."""
    song_id: str
    title: str
    artist: str
    bpm: float
    duration_sec: float
    beat_graph: List[float]
    energy_levels: List[float]
    emotion_tags: List[str]
    sections: List[Dict[str, Any]] = field(default_factory=list)
    mc_gender: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SceneIR:
    """Creative compilation plan prior to rendering."""
    scene_id: str
    intent: str
    director_style: str
    shot_list: List[Dict[str, Any]]
    total_duration_sec: float = 0.0
    average_energy: float = 0.0
    cuts_per_minute: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Self-Learning Kernel (Experience Store) ───────────────────────────────────

class SelfLearningKernel:
    """SQLite-backed persistent experience storage for Creative Compiler decisions."""
    
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            db_path = DATA_DIR / "experience_omega_v2.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS experiences (
                uuid TEXT PRIMARY KEY,
                episode INTEGER,
                song_hash TEXT,
                clip_id TEXT,
                energy_level REAL,
                sync_score REAL,
                flow_score REAL,
                duplicate_penalty REAL,
                reward REAL,
                metadata TEXT,
                created_at REAL
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_exp_song ON experiences(song_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_exp_clip ON experiences(clip_id)')
        self.conn.commit()

    def save_experience(self, exp_data: Dict[str, Any]):
        """Store a single decision + its outcome in the experience database."""
        self.save_experiences_batch([exp_data])

    def save_experiences_batch(self, exp_list: List[Dict[str, Any]]):
        """Batch store multiple decisions + outcomes in a single transaction."""
        if not exp_list:
            return
        now = time.time()
        rows = [
            (
                str(uuid.uuid4()),
                int(exp.get('episode', 1)),
                str(exp.get('song_hash', '')),
                str(exp.get('clip_id', '')),
                float(exp.get('energy', 0.0)),
                float(exp.get('sync_score', 0.0)),
                float(exp.get('flow_score', 0.0)),
                float(exp.get('duplicate_penalty', 0.0)),
                float(exp.get('reward', 0.0)),
                str(exp.get('metadata', '')),
                now
            )
            for exp in exp_list
        ]
        cursor = self.conn.cursor()
        cursor.executemany('''
            INSERT INTO experiences
                (uuid, episode, song_hash, clip_id, energy_level, sync_score,
                 flow_score, duplicate_penalty, reward, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows)
        self.conn.commit()

    def get_best_clip(self, song_hash: str, energy: float, exclude: Optional[set] = None) -> Optional[str]:
        """Look up highest-average-reward clip for a similar energy level."""
        exclude = exclude or set()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT clip_id, AVG(reward) as avg_reward, COUNT(*) as n
            FROM experiences
            WHERE song_hash = ? AND ABS(energy_level - ?) < 0.25
            GROUP BY clip_id
            ORDER BY avg_reward DESC
        ''', (song_hash, energy))
        for row in cursor.fetchall():
            clip_id = row[0]
            if clip_id not in exclude:
                return clip_id
        return None

    def get_stats(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*), AVG(reward) FROM experiences')
        count, avg_reward = cursor.fetchone()
        return {
            "total_experiences": count or 0,
            "avg_reward": round(avg_reward or 0.0, 4),
            "db_path": str(self.db_path)
        }

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


# ── Optimizer / Self-Critic (C+ Engine Kernel) ────────────────────────────────

class OptimizerKernel:
    """Evaluates timeline harmony, cut density, and multi-factor rewards."""
    
    def __init__(self, slk: Optional[SelfLearningKernel] = None):
        self.slk = slk

    def calculate_reward(self, sync_score: float, flow_score: float, penalty: float,
                         weights: tuple = (0.5, 0.35, 0.15)) -> float:
        """Weighted multi-reward function R = w_beat*S_beat + w_flow*S_flow - w_penalty*P"""
        w_beat, w_flow, w_penalty = weights
        raw = (w_beat * sync_score) + (w_flow * flow_score) - (w_penalty * penalty)
        return round(max(0.0, min(1.0, raw)), 4)

    def self_critic(self, scene: SceneIR, song: SongIR) -> Dict[str, Any]:
        """Deep heuristic self-critic evaluating pacing, energy distribution, and flow."""
        cxx_engine = cxx_accel.get_cxx_engine()
        avg_energy = sum(song.energy_levels) / max(1, len(song.energy_levels))
        eval_res = cxx_engine.evaluate_scene_metrics(
            scene.shot_list,
            total_duration_sec=song.duration_sec,
            target_energy_avg=avg_energy
        )
        eval_res["average_energy"] = round(avg_energy, 4)
        eval_res["total_shots"] = len(scene.shot_list)
        eval_res["notes"] = "Harmonisch abgestimmt" if eval_res["rating"] != "SUBOPTIMAL" else "Hektisch/Suboptimal korrigiert"
        return eval_res


# ── Main Creative Compiler Engine ─────────────────────────────────────────────

class CreativeCompilerOS:
    """Central C+ Engine coordinator for SongIR & SceneIR compilation."""
    
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.slk = SelfLearningKernel(db_path)
        self.optimizer = OptimizerKernel(self.slk)

    def compile(self, mp3_path: str) -> SceneIR:
        """Standalone compilation pass for a single audio file."""
        song_ir = SongIR(
            song_id=hashlib_sha(mp3_path),
            title=Path(mp3_path).stem,
            artist="Unknown Artist",
            bpm=120.0,
            duration_sec=60.0,
            beat_graph=[0.5, 1.0, 1.5, 2.0],
            energy_levels=[0.3, 0.7, 0.8, 0.5],
            emotion_tags=["Cinematic", "Bass"],
        )

        shots = []
        for idx, energy in enumerate(song_ir.energy_levels):
            best_clip = self.slk.get_best_clip(song_ir.song_id, energy)
            clip_to_use = best_clip if best_clip else f"clip_gen_{idx + 1:03d}.mp4"
            shots.append({
                "clip": clip_to_use,
                "energy": energy,
                "cut_style": "hard_cut" if energy > 0.6 else "dissolve",
                "rhythm_pattern": "buildup" if idx == 1 else "steady",
            })

        scene_ir = SceneIR(
            scene_id=f"scene_{uuid.uuid4().hex[:8]}",
            intent="Cinematic Dynamic",
            director_style="cunningham",
            shot_list=shots,
            total_duration_sec=song_ir.duration_sec,
            average_energy=sum(song_ir.energy_levels) / len(song_ir.energy_levels),
            cuts_per_minute=len(shots) / (song_ir.duration_sec / 60.0),
        )

        critic = self.optimizer.self_critic(scene_ir, song_ir)
        for shot in shots:
            reward = self.optimizer.calculate_reward(critic["sync_score"], critic["flow_score"], critic["duplicate_penalty"])
            self.slk.save_experience({
                "episode": 1,
                "song_hash": song_ir.song_id,
                "clip_id": shot["clip"],
                "energy": shot["energy"],
                "sync_score": critic["sync_score"],
                "flow_score": critic["flow_score"],
                "duplicate_penalty": critic["duplicate_penalty"],
                "reward": reward,
                "metadata": {"intent": scene_ir.intent},
            })

        return scene_ir

    def close(self):
        self.slk.close()


def hashlib_sha(text: str, length: int = 16) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


# ── Pipeline Interface ────────────────────────────────────────────────────────

_GLOBAL_COMPILER: Optional[CreativeCompilerOS] = None

def get_creative_compiler(db_path: Optional[Union[str, Path]] = None) -> CreativeCompilerOS:
    global _GLOBAL_COMPILER
    if _GLOBAL_COMPILER is None:
        _GLOBAL_COMPILER = CreativeCompilerOS(db_path=db_path)
    return _GLOBAL_COMPILER


def compile_creative_ir(
    song: Any,
    audio: Any,
    timeline: List[Any],
    style: Any,
    semantics: Optional[Dict[str, Any]] = None,
    db_path: Optional[Union[str, Path]] = None,
    log_fn: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Kanonische Pipeline-Brücke für main.py:
    Kompiliert SongInfo + AudioAnalysis + Timeline in SongIR & SceneIR,
    führt die C+ Self-Critic-Bewertung durch, loggt die Experience und liefert
    das serialisierbare C+ Engine Manifest.
    """
    compiler = get_creative_compiler(db_path)
    semantics = semantics or {}
    
    # 1. SongIR konstruieren
    song_path_str = str(getattr(song, "path", "unknown_song"))
    song_id = hashlib_sha(song_path_str)
    
    raw_sections = getattr(audio, "sections", []) or []
    sections_list = []
    for s in raw_sections:
        if isinstance(s, (tuple, list)):
            start_s = float(s[0]) if len(s) > 0 else 0.0
            end_s = float(s[1]) if len(s) > 1 else 0.0
            lbl = str(s[2]) if len(s) > 2 else "mid"
            nrg = 0.8 if lbl == "high" else (0.2 if lbl == "low" else 0.5)
            sections_list.append({"start": start_s, "end": end_s, "label": lbl, "energy": nrg})
        elif isinstance(s, dict):
            sections_list.append(s)
        else:
            sections_list.append({
                "start": getattr(s, "start_sec", 0.0),
                "end": getattr(s, "end_sec", 0.0),
                "label": getattr(s, "label", "mid"),
                "energy": getattr(s, "energy", 0.5)
            })

    energy_curve = [round(float(s["energy"]), 3) for s in sections_list]
    if not energy_curve:
        raw_energy = getattr(audio, "energy", []) or []
        if raw_energy:
            step = max(1, len(raw_energy) // 64)
            energy_curve = [round(float(e), 3) for e in raw_energy[::step]]
    if not energy_curve:
        energy_curve = [round(float(getattr(seg, "target_energy", 0.5)), 3) for seg in timeline] or [0.5]

    mood_tags = list(semantics.get("mood_tags") or [])
    if not mood_tags and hasattr(song, "tag_vector") and isinstance(song.tag_vector, dict):
        mood_tags = list(song.tag_vector.keys())[:5]

    beat_times = list(getattr(audio, "beat_times", []) or [])

    song_ir = SongIR(
        song_id=song_id,
        title=str(getattr(song, "title", Path(song_path_str).stem) or Path(song_path_str).stem),
        artist=str(getattr(song, "artist", "Unknown Artist") or "Unknown Artist"),
        bpm=round(float(getattr(audio, "bpm", 120.0)), 2),
        duration_sec=round(float(getattr(audio, "duration_sec", 0.0)), 2),
        beat_graph=beat_times[:128],  # First 128 beats for concise IR
        energy_levels=energy_curve,
        emotion_tags=mood_tags,
        sections=sections_list,
        mc_gender=str(getattr(audio, "mc_gender", "unknown"))
    )

    # 2. SceneIR aus Timeline erzeugen
    shots = []
    for idx, seg in enumerate(timeline):
        shots.append({
            "index": idx + 1,
            "clip": str(getattr(seg, "clip_path", "")),
            "start_sec": round(float(getattr(seg, "start_sec", 0.0)), 3),
            "end_sec": round(float(getattr(seg, "end_sec", 0.0)), 3),
            "duration": round(float(getattr(seg, "end_sec", 0.0) - getattr(seg, "start_sec", 0.0)), 3),
            "energy": round(float(getattr(seg, "target_energy", 0.5)), 3),
            "cut_style": str(getattr(seg, "cut_style", "hard_cut")),
            "rhythm_pattern": str(getattr(seg, "rhythm_pattern", "steady")),
            "sync_type": str(getattr(seg, "sync_type", "on_beat")),
            "speed_factor": round(float(getattr(seg, "speed_factor", 1.0)), 3),
            "on_structure_boundary": bool(getattr(seg, "on_structure_boundary", False)),
            "section": str(getattr(seg, "section_label", "mid")),
            "theme": str(getattr(seg, "theme", "general")),
        })

    director_name = getattr(style, "name", "cinematic") if style else "cinematic"
    cuts_pm = (len(shots) / (song_ir.duration_sec / 60.0)) if song_ir.duration_sec > 0 else 0.0
    avg_e = sum(s["energy"] for s in shots) / max(1, len(shots))

    scene_ir = SceneIR(
        scene_id=f"scene_{song_id[:8]}_{int(time.time())}",
        intent=f"C+ Compiler: {director_name.upper()} RHYTHM LOCK",
        director_style=director_name,
        shot_list=shots,
        total_duration_sec=song_ir.duration_sec,
        average_energy=round(avg_e, 4),
        cuts_per_minute=round(cuts_pm, 2),
    )

    # 3. Self-Critic Auswertung
    critic_report = compiler.optimizer.self_critic(scene_ir, song_ir)

    # 4. Lern-Experience im Kernel sichern
    compiler.slk.save_experiences_batch([
        {
            "episode": 1,
            "song_hash": song_ir.song_id,
            "clip_id": shot["clip"],
            "energy": shot["energy"],
            "sync_score": critic_report["sync_score"],
            "flow_score": critic_report["flow_score"],
            "duplicate_penalty": critic_report["duplicate_penalty"],
            "reward": critic_report["quality_score"],
            "metadata": {"director": director_name, "cut_style": shot["cut_style"]},
        }
        for shot in shots
    ])

    kernel_stats = compiler.slk.get_stats()

    if log_fn:
        log_fn(
            f"  🧠 C+ Creative Compiler: Score={critic_report['quality_score']:.2f} "
            f"({critic_report['rating']}) | Flow={critic_report['flow_score']:.2f} | "
            f"Sync={critic_report['sync_score']:.2f} (Experiences: {kernel_stats['total_experiences']})"
        )

    return {
        "compiler_version": "Creative Compiler OS v2 (C+ Engine)",
        "timestamp": time.time(),
        "song_ir": song_ir.to_dict(),
        "scene_ir": scene_ir.to_dict(),
        "self_critic": critic_report,
        "kernel_stats": kernel_stats,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Creative Compiler OS (C+ Engine)")
    parser.add_argument("--test", action="store_true", help="Führe einen schnellen Test-Compile durch")
    args = parser.parse_args()

    engine = CreativeCompilerOS()
    try:
        res = engine.compile("test_song.mp3")
        print(f"✅ Creative Compiler C+ Test erfolgreich:")
        print(f"  • Scene-ID: {res.scene_id}")
        print(f"  • Shots: {len(res.shot_list)}")
        print(f"  • Cuts/Min: {res.cuts_per_minute:.1f}")
    finally:
        engine.close()
