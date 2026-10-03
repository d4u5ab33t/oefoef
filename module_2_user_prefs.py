import random
import numpy as np
import yaml
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

@dataclass
class Decision:
    beat_sync: float
    novelty: float
    flow: float
    duplicate_penalty: float
    user_reward: float
    total_reward: float
    strategy: str

class RLBanditCouncil:
    """
    Simulates the Director Council in WE.ED.IT Omega.
    Now integrated with the User Preference Model (UPM).
    """
    def __init__(self, pref_path=r"J:\Oidasheim\oefoef\user_preferences.yaml", policy="Cinematic"):
        self.policy = policy
        self.load_preferences(pref_path)
        
        if policy == "Cinematic":
            self.weights = {"beat": 0.40, "novelty": 0.30, "flow": 0.20, "penalty": -0.10}
        elif policy == "Trap":
            self.weights = {"beat": 0.60, "novelty": 0.20, "flow": 0.10, "penalty": -0.10}
        else:
            self.weights = {"beat": 0.30, "novelty": 0.30, "flow": 0.30, "penalty": -0.10}

    def load_preferences(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.prefs = yaml.safe_load(f)
            print(f"Successfully loaded preferences from {path}")
        except Exception as e:
            print(f"Preference file not found or error: {e}. Using default neutral profile.")
            self.prefs = {"user_profile": {"global_weight": 0.0}, "preferences": {"likes": [], "dislikes": []}}

    def calculate_user_reward(self, tags: List[str]) -> float:
        user_score = 0.0
        likes = self.prefs.get("preferences", {}).get("likes", [])
        dislikes = self.prefs.get("preferences", {}).get("dislikes", [])

        for tag_info in likes:
            if tag_info["tag"] in tags:
                user_score += tag_info["weight"]
        
        for tag_info in dislikes:
            if tag_info["tag"] in tags:
                user_score += tag_info["weight"]
        
        return user_score

    def calculate_global_reward(self, beat, novelty, flow, penalty, user_score) -> float:
        tech_reward = (self.weights["beat"] * beat + 
                      self.weights["novelty"] * novelty + 
                      self.weights["flow"] * flow + 
                      self.weights["penalty"] * penalty)
        
        global_weight = self.prefs.get("user_profile", {}).get("global_weight", 0.0)
        return (1 - global_weight) * tech_reward + global_weight * user_score

    def decide(self, current_beat_precision: float, clip_tags: List[str]) -> Decision:
        beat_score = current_beat_precision
        
        if beat_score > 0.9:
            novelty_score = random.uniform(0.7, 1.0)
            strategy = "Novelty Spike (High Sync Budget)"
        else:
            novelty_score = random.uniform(0.1, 0.5)
            strategy = "Safe Flow (Low Sync Budget)"

        flow_score = random.uniform(0.5, 0.9)
        penalty = random.uniform(0.0, 0.3)
        
        user_score = self.calculate_user_reward(clip_tags)
        total_reward = self.calculate_global_reward(beat_score, novelty_score, flow_score, penalty, user_score)
        
        return Decision(beat_score, novelty_score, flow_score, penalty, user_score, total_reward, strategy)

def simulate_personalized_production(iterations=20):
    council = RLBanditCouncil()
    
    clip_library = [
        ["night", "cyberpunk", "slow_zoom"], # User loves this (0.2 + 0.1 + 0.15 = 0.45)
        ["rapid_cut", "flash"],               # User hates this (-0.4 - 0.3 = -0.7)
        ["drone", "orange", "nature"],       # User likes some (0.1 + 0.1 = 0.2)
        ["urban", "static", "day"]            # Neutral (0.0)
    ]

    print(f"\nStarting Personalized Simulation...")
    print("-" * 75)
    print(f"{'Step':<6} | {'Beat':<6} | {'Tags':<25} | {'UserR':<8} | {'TotalR':<8} | {'Strategy'}")
    print("-" * 75)

    for i in range(iterations):
        beat_precision = random.uniform(0.6, 1.0)
        tags = random.choice(clip_library)
        decision = council.decide(beat_precision, tags)
        
        tags_str = ",".join(tags)
        print(f"{i+1:<6} | {decision.beat_sync:.2f} | {tags_str:<25} | {decision.user_reward:.2f} | {decision.total_reward:.3f} | {decision.strategy}")

if __name__ == "__main__":
    simulate_personalized_production()
