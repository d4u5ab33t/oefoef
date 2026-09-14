"""
bandit.py — Contextual Bandit for online editing decision optimization.
"""
import random
import numpy as np
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class EditDecisionReward:
    beat_sync: float
    novelty: float
    flow: float
    duplicate_penalty: float
    total_reward: float
    chosen_strategy: str


class ContextualBandit:
    """Contextual multi-armed bandit for edit decisions."""

    def __init__(self, epsilon: float = 0.1):
        self.epsilon = epsilon
        self.arms = ["zoom_push", "glitch_transition", "hard_cut", "flash_cut"]
        self.counts: Dict[str, int] = {a: 0 for a in self.arms}
        self.values: Dict[str, float] = {a: 0.0 for a in self.arms}

    def select_action(self) -> str:
        if random.random() < self.epsilon:
            return random.choice(self.arms)
        
        best_arm = max(self.values.keys(), key=lambda a: self.values[a])
        return best_arm

    def update(self, action: str, reward: float):
        if action not in self.counts:
            self.arms.append(action)
            self.counts[action] = 0
            self.values[action] = 0.0

        self.counts[action] += 1
        n = self.counts[action]
        val = self.values[action]
        self.values[action] = val + (1.0 / n) * (reward - val)

    def evaluate_decision(self, beat_precision: float, novelty: float, flow: float) -> EditDecisionReward:
        action = self.select_action()
        reward = 0.4 * beat_precision + 0.3 * novelty + 0.3 * flow
        self.update(action, reward)

        return EditDecisionReward(
            beat_sync=beat_precision,
            novelty=novelty,
            flow=flow,
            duplicate_penalty=0.0,
            total_reward=round(reward, 3),
            chosen_strategy=action
        )
