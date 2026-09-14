"""
user_preferences.py — Manages user preferences and retention feedback weights.
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class UserPreferenceProfile:
    liked_tags: List[str] = field(default_factory=lambda: ["high_energy", "snow", "moshpit"])
    disliked_tags: List[str] = field(default_factory=lambda: ["boring", "static"])
    tag_weights: Dict[str, float] = field(default_factory=dict)

    def get_score_modifier(self, tags: List[str]) -> float:
        modifier = 0.0
        for tag in tags:
            tag_clean = tag.lower().strip()
            if tag_clean in self.liked_tags:
                modifier += 0.2
            if tag_clean in self.disliked_tags:
                modifier -= 0.3
            if tag_clean in self.tag_weights:
                modifier += self.tag_weights[tag_clean]
        return modifier

    def update_feedback(self, tag: str, reward: float):
        cur = self.tag_weights.get(tag, 0.0)
        self.tag_weights[tag] = cur + 0.1 * (reward - cur)
