"""self_learning.py — Stetiges & Adaptives Self-Learning & Reinforcement Learning System.

Erweitert das neuronale Gedächtnis und die Entscheidungslogik des Gesamtsystems:
1. Contextual Multi-Armed Bandit (UCB1 + Thompson Sampling):
   - Wählt und optimiert Regie-Stile (Director Styles: Cunningham, Gondry, Hype Williams, Jonze, Oida Raw)
   - Passt Schnitttempo-Multiplikatoren, VFX-Intensität und Scratch-Wahrscheinlichkeiten stetig an
2. Transition Flow Graph (Markov Transition Success Matrix):
   - Lernt erfolgreiche Clip-zu-Clip-Übergänge (z.B. Flow-Kontinuität, Whip Pan -> Drop Hit, etc.)
3. Audio-Semantische Resonanz-Matrix:
   - Verknüpft BPM-Bereiche und Song-Moods mit den historisch wirksamsten visuellen Konzepten
4. Stetige Belohnungs-Propagierung:
   - Integriert mit HierarchicalVectorTree (vector_tree.py) und libsync-flat-globe
   - Schreibt atomar in data/self_learning_state.json und synchronisiert mit ../brain.bug
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import (
    BRAIN_BUG_DIR,
    BRAIN_RL_BANDIT_STATE,
    DATA_DIR,
    TAG_VOCAB,
)
from cxx_accel.bridge import get_cxx_engine
from vector_tree import get_global_vector_tree

SELF_LEARNING_STATE_FILE = DATA_DIR / "self_learning_state.json"
TRANSITION_MATRIX_FILE = DATA_DIR / "transition_flow_matrix.json"


def _bpm_bracket(bpm: float) -> str:
    if bpm < 85:
        return "SLOW_BOOMBAP"
    elif bpm < 110:
        return "MID_GROOVE"
    elif bpm < 135:
        return "TRAP_DRILL"
    else:
        return "FAST_HARDCORE"


@dataclass
class BanditArm:
    name: str
    pulls: int = 0
    total_reward: float = 0.0
    reward_history: list[float] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)

    @property
    def mean_reward(self) -> float:
        return (self.total_reward / self.pulls) if self.pulls > 0 else 0.5

    def ucb1_score(self, total_pulls: int, c: float = 1.414) -> float:
        if self.pulls == 0:
            return 999.0  # Unbesuchte Arme zuerst testen (Exploration)
        bonus = c * math.sqrt(math.log(total_pulls) / self.pulls)
        return self.mean_reward + bonus

    def sample_thompson(self) -> float:
        """C++20 beschleunigte Beta-Verteilung für Thompson Sampling."""
        return get_cxx_engine().bandit_sample_thompson(self.total_reward, self.pulls)


class SelfLearningEngine:
    """Zentrale Engine für adaptives Self-Learning und stetige Parameter-Optimierung."""

    def __init__(
        self,
        state_file: Optional[Path] = None,
        transition_file: Optional[Path] = None,
        decay_factor: float = 0.98,
    ):
        self.state_file = Path(state_file or SELF_LEARNING_STATE_FILE)
        self.transition_file = Path(transition_file or TRANSITION_MATRIX_FILE)
        self.decay_factor = decay_factor

        # 1. Bandit Arms für Director Styles
        self.director_arms: dict[str, BanditArm] = {
            "cunningham": BanditArm(name="cunningham"),
            "gondry": BanditArm(name="gondry"),
            "hype_williams": BanditArm(name="hype_williams"),
            "jonze": BanditArm(name="jonze"),
            "oida_raw": BanditArm(name="oida_raw"),
        }

        # 2. Pacing Multiplier Bandit (Schnitt-Dynamik)
        self.pacing_arms: dict[str, BanditArm] = {
            "ultra_fast": BanditArm(name="ultra_fast"),   # 0.7x Intervall
            "beat_locked": BanditArm(name="beat_locked"), # 1.0x Intervall
            "narrative": BanditArm(name="narrative"),     # 1.3x Intervall
            "syncopated": BanditArm(name="syncopated"),   # Unregelmäßig / Polyrhythmisch
        }

        # 3. Transition Flow Graph: {(from_domain, to_domain): {"count": n, "reward_sum": r}}
        self.transition_graph: dict[str, dict[str, float]] = {}

        # 4. BPM & Audio Mood Resonance Memory
        # {bpm_bracket: {tag: {"score": s, "count": c}}}
        self.audio_resonance: dict[str, dict[str, dict[str, float]]] = {}

        # 5. Globale Metriken
        self.total_renders_learned: int = 0
        self.last_render_reward: float = 0.0
        self.last_sync_time: float = 0.0

        # Lade Zustand falls vorhanden
        self.load_state()

    # ── Entscheidungsprozesse (Exploration vs Exploitation) ─────────────────────
    def choose_director_style(self, strategy: str = "thompson") -> str:
        """Wählt den optimalen Regie-Stil mittels nativem C++ Thompson Sampling oder UCB1."""
        arms_list = list(self.director_arms.values())
        arm_dicts = [{"total_reward": a.total_reward, "pulls": a.pulls} for a in arms_list]
        best_idx = get_cxx_engine().bandit_select_best_arm(arm_dicts, strategy=strategy)
        return arms_list[best_idx].name

    def choose_pacing_strategy(self, strategy: str = "thompson") -> str:
        """Wählt das adaptiv gelernte Schnitttempo."""
        arms_list = list(self.pacing_arms.values())
        arm_dicts = [{"total_reward": a.total_reward, "pulls": a.pulls} for a in arms_list]
        best_idx = get_cxx_engine().bandit_select_best_arm(arm_dicts, strategy=strategy)
        return arms_list[best_idx].name

    def get_transition_flow_bonus(self, from_domain: str, to_domain: str, same_motion_direction: bool = True) -> float:
        """Liefert einen gelernten Bonus für einen Szenenübergang zwischen zwei Domänen."""
        key = f"{from_domain}->{to_domain}"
        entry = self.transition_graph.get(key)
        if not entry:
            return 0.05 if same_motion_direction else 0.0

        count = int(entry.get("count", 0))
        reward_sum = float(entry.get("reward_sum", 0.0))
        return get_cxx_engine().markov_transition_bonus(reward_sum, count, same_motion_direction)


    def get_audio_resonance_bonus(self, bpm: float, tags: list[str]) -> float:
        """Liefert einen Resonanz-Bonus für Tags, die bei dieser BPM historisch gut abschnitten."""
        if not tags:
            return 0.0
        bracket = _bpm_bracket(bpm)
        bracket_mem = self.audio_resonance.get(bracket)
        if not bracket_mem:
            return 0.0

        bonuses = []
        for t in tags:
            tag_data = bracket_mem.get(t.lower())
            if tag_data and tag_data.get("count", 0) > 0:
                mean_s = tag_data["score"] / tag_data["count"]
                bonuses.append((mean_s - 0.5) * 0.1)

        if not bonuses:
            return 0.0
        return round(sum(bonuses) / len(bonuses), 4)

    # ── Feedback-Ingestion & Stetiges Lernen ──────────────────────────────────
    def record_render_outcome(
        self,
        song: Any,
        audio: Any,
        timeline: list[Any],
        reward: float,
        director: str = "cunningham",
        pacing_strategy: str = "beat_locked",
        globe: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Verarbeitet das vollständige Feedback eines Video-Renders stetig und adaptiv."""
        now = time.time()
        self.total_renders_learned += 1
        self.last_render_reward = reward

        # 1. Update Director Bandit
        d_key = director.lower().replace(" ", "_")
        if d_key in self.director_arms:
            arm = self.director_arms[d_key]
            arm.pulls += 1
            arm.total_reward += reward
            arm.reward_history.append(round(reward, 4))
            if len(arm.reward_history) > 100:
                arm.reward_history = arm.reward_history[-100:]
            arm.last_updated = now

        # 2. Update Pacing Bandit
        p_key = pacing_strategy.lower()
        if p_key in self.pacing_arms:
            p_arm = self.pacing_arms[p_key]
            p_arm.pulls += 1
            p_arm.total_reward += reward
            p_arm.reward_history.append(round(reward, 4))
            if len(p_arm.reward_history) > 100:
                p_arm.reward_history = p_arm.reward_history[-100:]
            p_arm.last_updated = now

        # 3. Update Transition Flow Graph
        tree = get_global_vector_tree()
        for i in range(len(timeline) - 1):
            seg_a = timeline[i]
            seg_b = timeline[i + 1]
            path_a = getattr(seg_a, "clip_path", "")
            path_b = getattr(seg_b, "clip_path", "")

            dom_a = "GENERAL"
            dom_b = "GENERAL"
            if path_a in tree.leaves:
                dom_a = getattr(tree.leaves[path_a], "gender", "GENERAL")
            if path_b in tree.leaves:
                dom_b = getattr(tree.leaves[path_b], "gender", "GENERAL")

            key = f"{dom_a}->{dom_b}"
            entry = self.transition_graph.setdefault(key, {"count": 0, "reward_sum": 0.0})
            entry["count"] += 1
            entry["reward_sum"] += reward

        # 4. Update BPM & Audio Mood Resonance
        bpm_val = getattr(audio, "bpm", 120.0)
        bracket = _bpm_bracket(bpm_val)
        bracket_mem = self.audio_resonance.setdefault(bracket, {})

        song_tags = getattr(song, "mood_tags", []) or []
        for tag in song_tags:
            t_key = tag.lower()
            tag_entry = bracket_mem.setdefault(t_key, {"count": 0, "score": 0.0})
            tag_entry["count"] += 1
            tag_entry["score"] += reward

        # 5. Propagiere Reward in den Vektor-Baum
        for seg in timeline:
            path = getattr(seg, "clip_path", "")
            if path:
                tree.reinforce_path(path, reward)

        # Speichere aktualisierten Zustand
        self.save_state()
        tree.save_tree()

        return {
            "total_renders": self.total_renders_learned,
            "director": d_key,
            "director_mean_reward": self.director_arms.get(d_key, BanditArm("")).mean_reward,
            "reward": reward,
            "status": "learned_and_persisted",
        }

    # ── Persistenz & Brain-Synchronisation ─────────────────────────────────────
    def save_state(self) -> bool:
        """Speichert den Self-Learning-Zustand atomar."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")

        try:
            data = {
                "version": "self_learning_v2",
                "total_renders_learned": self.total_renders_learned,
                "last_render_reward": round(self.last_render_reward, 4),
                "last_sync_time": time.time(),
                "director_arms": {
                    k: {
                        "name": a.name,
                        "pulls": a.pulls,
                        "total_reward": round(a.total_reward, 4),
                        "mean_reward": round(a.mean_reward, 4),
                        "reward_history": a.reward_history,
                        "last_updated": a.last_updated,
                    }
                    for k, a in self.director_arms.items()
                },
                "pacing_arms": {
                    k: {
                        "name": a.name,
                        "pulls": a.pulls,
                        "total_reward": round(a.total_reward, 4),
                        "mean_reward": round(a.mean_reward, 4),
                        "reward_history": a.reward_history,
                        "last_updated": a.last_updated,
                    }
                    for k, a in self.pacing_arms.items()
                },
                "transition_graph": self.transition_graph,
                "audio_resonance": self.audio_resonance,
            }
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            if self.state_file.exists():
                bak = self.state_file.with_suffix(".bak")
                try:
                    self.state_file.replace(bak)
                except OSError:
                    pass
            tmp.replace(self.state_file)

            # Sync auch zu BRAIN_RL_BANDIT_STATE
            self._sync_to_brain_bandit()
            return True
        except Exception as e:
            print(f"[self_learning] Fehler beim Speichern von {self.state_file}: {e}")
            return False

    def _sync_to_brain_bandit(self):
        """Synchronisiert aggregierte Bandit-Daten mit BRAIN_RL_BANDIT_STATE."""
        try:
            counts = {k: a.pulls for k, a in self.director_arms.items()}
            rewards = {k: round(a.total_reward, 4) for k, a in self.director_arms.items()}
            total_pulls = sum(counts.values())

            brain_data = {
                "counts": counts,
                "rewards": rewards,
                "total_pulls": total_pulls,
                "updated_at": time.time(),
            }
            if BRAIN_RL_BANDIT_STATE.parent.exists():
                with open(BRAIN_RL_BANDIT_STATE, "w", encoding="utf-8") as f:
                    json.dump(brain_data, f, indent=2)
        except Exception:
            pass

    def load_state(self) -> bool:
        """Lädt den Self-Learning-Zustand."""
        if not self.state_file.exists():
            return False

        try:
            with self.state_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            self.total_renders_learned = int(data.get("total_renders_learned", 0))
            self.last_render_reward = float(data.get("last_render_reward", 0.0))
            self.last_sync_time = float(data.get("last_sync_time", 0.0))

            if "director_arms" in data:
                for k, ad in data["director_arms"].items():
                    self.director_arms[k] = BanditArm(
                        name=ad.get("name", k),
                        pulls=int(ad.get("pulls", 0)),
                        total_reward=float(ad.get("total_reward", 0.0)),
                        reward_history=ad.get("reward_history", []),
                        last_updated=float(ad.get("last_updated", time.time())),
                    )

            if "pacing_arms" in data:
                for k, ad in data["pacing_arms"].items():
                    self.pacing_arms[k] = BanditArm(
                        name=ad.get("name", k),
                        pulls=int(ad.get("pulls", 0)),
                        total_reward=float(ad.get("total_reward", 0.0)),
                        reward_history=ad.get("reward_history", []),
                        last_updated=float(ad.get("last_updated", time.time())),
                    )

            self.transition_graph = data.get("transition_graph", {})
            self.audio_resonance = data.get("audio_resonance", {})
            return True
        except Exception as e:
            print(f"[self_learning] Fehler beim Laden von {self.state_file}: {e}")
            return False

    def stats(self) -> dict[str, Any]:
        """Diagnose-Übersicht des Self-Learning-Systems."""
        return {
            "total_renders_learned": self.total_renders_learned,
            "last_render_reward": self.last_render_reward,
            "directors": {
                k: {
                    "pulls": a.pulls,
                    "mean_reward": round(a.mean_reward, 4),
                }
                for k, a in self.director_arms.items()
            },
            "pacing": {
                k: {
                    "pulls": a.pulls,
                    "mean_reward": round(a.mean_reward, 4),
                }
                for k, a in self.pacing_arms.items()
            },
            "transition_count": len(self.transition_graph),
            "resonance_brackets": list(self.audio_resonance.keys()),
        }


# Globales Singleton
_GLOBAL_LEARNER: Optional[SelfLearningEngine] = None


def get_global_learner() -> SelfLearningEngine:
    global _GLOBAL_LEARNER
    if _GLOBAL_LEARNER is None:
        _GLOBAL_LEARNER = SelfLearningEngine()
    return _GLOBAL_LEARNER


get_global_learning_engine = get_global_learner

