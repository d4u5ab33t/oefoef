import json
import random
import numpy as np
from dataclasses import dataclass
from typing import List
from config import BRAIN_RL_BANDIT_STATE

@dataclass
class Decision:
    beat_sync: float
    novelty: float
    flow: float
    duplicate_penalty: float
    total_reward: float
    strategy: str

class RLBanditCouncil:
    """
    Simulates the Director Council in WE.ED.IT Omega.
    Balances Rhythm Director (Beat-Sync) vs Style Director (Novelty).
    Connects to persistent brain bandit state in rl_bandit_state.json.
    """
    def __init__(self, policy="Cinematic"):
        self.policy = policy
        # Default Weights based on the Omega Spec
        if policy == "Cinematic":
            self.weights = {"beat": 0.40, "novelty": 0.30, "flow": 0.20, "penalty": -0.10}
        elif policy == "Trap":
            self.weights = {"beat": 0.60, "novelty": 0.20, "flow": 0.10, "penalty": -0.10}
        else:
            self.weights = {"beat": 0.30, "novelty": 0.30, "flow": 0.30, "penalty": -0.10}

        self.state = self.load_bandit_state()

    def load_bandit_state(self) -> dict:
        if BRAIN_RL_BANDIT_STATE.exists():
            try:
                with open(BRAIN_RL_BANDIT_STATE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"counts": {}, "rewards": {}, "total_pulls": 0}

    def save_bandit_state(self):
        try:
            with open(BRAIN_RL_BANDIT_STATE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception:
            pass

    def calculate_reward(self, beat, novelty, flow, penalty) -> float:
        return (self.weights["beat"] * beat + 
                self.weights["novelty"] * novelty + 
                self.weights["flow"] * flow + 
                self.weights["penalty"] * penalty)

    def decide(self, current_beat_precision: float) -> Decision:
        # Rhythm Director's demand
        beat_score = current_beat_precision
        
        # Style Director's push for Novelty
        # If beat_sync is > 0.9, we allow a 'Novelty Spike'
        if beat_score > 0.9:
            novelty_score = random.uniform(0.7, 1.0)
            strategy = "Novelty Spike (High Sync Budget)"
        else:
            novelty_score = random.uniform(0.1, 0.5)
            strategy = "Safe Flow (Low Sync Budget)"

        flow_score = random.uniform(0.5, 0.9)
        penalty = random.uniform(0.0, 0.3)
        
        reward = self.calculate_reward(beat_score, novelty_score, flow_score, penalty)
        
        return Decision(beat_score, novelty_score, flow_score, penalty, reward, strategy)

def simulate_production(iterations=50):
    council = RLBanditCouncil(policy="Cinematic")
    history = []

    print(f"Starting Simulation with Policy: {council.policy}")
    print("-" * 60)
    print(f"{'Step':<6} | {'Beat':<6} | {'Nov':<6} | {'Reward':<8} | {'Strategy'}")
    print("-" * 60)

    for i in range(iterations):
        # Simulate incoming beat precision from the Music Kernel
        beat_precision = random.uniform(0.6, 1.0)
        decision = council.decide(beat_precision)
        history.append(decision)
        
        print(f"{i+1:<6} | {decision.beat_sync:.2f} | {decision.novelty:.2f} | {decision.total_reward:.3f} | {decision.strategy}")

    return history

if __name__ == "__main__":
    results = simulate_production()
    
    # Final Analysis
    avg_reward = np.mean([d.total_reward for d in results])
    print("-" * 60)
    print(f"Simulation Complete. Average Global Reward: {avg_reward:.3f}")
    print("Observation: Notice how high Beat-Sync allows for high Novelty spikes.")
