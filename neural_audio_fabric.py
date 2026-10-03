#!/usr/bin/env python3
"""
neural_audio_fabric.py — Neural Audio Fabric (NAF) for SYNAPSE AUDIO DYNAMICS
Location: J:\\Oidasheim\\oefoef\\neural_audio_fabric.py
Frame-level 100ms tensor map extractor for tension, harmonic density, transient clarity, vocal presence & genre signature.
"""
import math
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, List

class NeuralAudioFabric:
    def __init__(self, window_ms: int = 100):
        self.window_ms = window_ms

    def extract_audio_map(self, audio_info: Any, audio_path: Path) -> List[Dict[str, Any]]:
        duration_sec = getattr(audio_info, "duration_sec", 180.0)
        bpm = getattr(audio_info, "bpm", 120.0)
        drops = getattr(audio_info, "drop_times", [30.0, 90.0, 150.0])
        gender = getattr(audio_info, "mc_gender", "male")

        total_windows = int((duration_sec * 1000) / self.window_ms)
        audio_map = []

        for i in range(total_windows):
            time_sec = (i * self.window_ms) / 1000.0
            
            # Distance to closest drop
            dist_to_drop = min([abs(time_sec - d) for d in drops]) if drops else 999.0
            
            # Tension calculation (curve builds up approaching drops)
            tension = max(0.0, 1.0 - (dist_to_drop / 15.0))
            harmonic_density = 0.5 + 0.3 * math.sin(time_sec * 0.5)
            transient_clarity = 0.8 if dist_to_drop < 2.0 else 0.4 + 0.2 * math.cos(time_sec * 2.0)
            vocal_presence = 0.9 if (gender != "instrumental" and dist_to_drop > 3.0) else 0.2
            emotional_peak = max(tension, 0.7 if dist_to_drop < 1.0 else 0.3)

            # Genre signature vector: [Trap, Pop, EDM, BoomBap, Cinematic, Cyberpunk, Metal, Ambient]
            genre_signature = [
                0.8 if bpm > 130 else 0.2, # Trap
                0.5,                       # Pop
                0.9 if bpm > 125 else 0.3, # EDM
                0.7 if bpm < 100 else 0.1, # BoomBap
                0.6,                       # Cinematic
                0.9,                       # Cyberpunk
                0.1,                       # Metal
                0.2                        # Ambient
            ]

            frame = {
                "time_ms": i * self.window_ms,
                "time_sec": round(time_sec, 3),
                "tension": round(tension, 4),
                "harmonic_density": round(harmonic_density, 4),
                "transient_clarity": round(transient_clarity, 4),
                "vocal_presence": round(vocal_presence, 4),
                "emotional_peak": round(emotional_peak, 4),
                "genre_signature": genre_signature
            }
            audio_map.append(frame)

        return audio_map

    def export_json(self, audio_map: List[Dict[str, Any]], output_file: Path):
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(audio_map, f, indent=2)

if __name__ == "__main__":
    naf = NeuralAudioFabric()
    print("🧠 Neural Audio Fabric (NAF) Ready.")
