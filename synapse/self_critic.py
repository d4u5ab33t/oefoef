"""SELF-CRITIC - The Quality Guard of SYNAPSE.

Verantwortung laut Konzept:
- Analyse des gerenderten Videos / der EDL auf ästhetische Fehler.
- Berechnung des Multi-Reward-Scores (R) basierend auf Beat-Sync, Flow und Diversität.
- Identifikation von 'Hektik' (Schnittdichte vs. Musikenergie).
- Rückkopplung an den SLK zur Optimierung zukünftiger Policies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Gewichtungsfaktoren laut Konzept [12]
W_BEAT = 0.5
W_FLOW = 0.3
W_PENALTY = 0.2

class SelfCritic:
    def __init__(self):
        pass

    def calculate_reward(self, sync_score: float, flow_score: float,
                        duplicate_penalty: float) -> float:
        """
        Mathematische Reward-Funktion R [12].
        R = w_beat * S_beat + w_flow * S_flow - w_penalty * P_duplicate
        """
        return (W_BEAT * sync_score) + (W_FLOW * flow_score) - (W_PENALTY * duplicate_penalty)

    def analyze_edl(self, edl_path: Path, song_energy_avg: float) -> dict[str, Any]:
        """
        Analysiert die EDL-Datei auf strukturelle Probleme. [14]
        Prüft vor allem die Korrelation zwischen Schnittdichte und Musikenergie.
        """
        if not edl_path.exists():
            return {"error": "EDL not found", "reward": 0.0}

        try:
            with open(edl_path, "r", encoding="utf-8") as f:
                edl = json.load(f)
            
            sequence = edl.get("sequence", [])
            if not sequence:
                return {"error": "Empty sequence", "reward": 0.0}

            # 1. Schnittdichte messen
            total_duration = 0.0
            for seg in sequence:
                total_duration += (seg["end"] - seg["start"])
            
            cut_density = len(sequence) / (total_duration / 60) if total_duration > 0 else 0
            
            # 2. Hektik-Check: Hohe Dichte bei niedriger Energie = schlecht
            # Beispiel: > 2 Schnitte/Sek bei Energie < 0.4 ist "hektisch"
            is_hectic = cut_density > 2.0 and song_energy_avg < 0.4
            
            # 3. Diversitäts-Check (Duplicate Penalty)
            clips = [seg["clip"] for seg in sequence]
            unique_clips = set(clips)
            duplicate_ratio = 1.0 - (len(unique_clips) / len(clips)) if clips else 0.0
            
            # 4. Simulation der Scores (in realer Version via Computer Vision/Audio-Analyse)
            # Hier nutzen wir Heuristiken für den ersten Build
            sync_score = 0.9 if not is_hectic else 0.4
            flow_score = 0.8 if duplicate_ratio < 0.2 else 0.5
            
            reward = self.calculate_reward(sync_score, flow_score, duplicate_ratio)
            
            return {
                "reward": round(reward, 4),
                "metrics": {
                    "cut_density": round(cut_density, 2),
                    "duplicate_ratio": round(duplicate_ratio, 2),
                    "is_hectic": is_hectic,
                    "sync_score": sync_score,
                    "flow_score": flow_score
                },
                "feedback": "Hektisch!" if is_hectic else "Harmonisch."
            }
        except Exception as e:
            return {"error": str(e), "reward": 0.0}

# Singleton-Instanz
critic = SelfCritic()
