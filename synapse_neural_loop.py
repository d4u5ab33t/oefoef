#!/usr/bin/env python3
"""
optimization_feedback_loop.py
Das neuronale Gedächtnis der Synapse. 
Verarbeitet Performance-Daten und adaptiert die DirectorBrain-Parameter.
"""

import json
from pathlib import Path
from brain_feedback_loop import BrainFeedbackLoop

# Pfade zur Feedback-Schleife
METRICS_PATH = Path("data/metrics_history.json")
BRAIN_CONFIG = Path("core/director_config.json")

def process_viral_feedback():
    """
    Analysiert letzte Performance-Daten.
    Triggers BrainFeedbackLoop data sync & parameter shift.
    """
    fb_loop = BrainFeedbackLoop()
    fb_loop.run_feedback_cycle()

    if not METRICS_PATH.exists():
        return

    with open(METRICS_PATH, "r") as f:
        data = json.load(f)
    
    if not data:
        return

    # Letzter Batch-Performance-Schnitt
    recent_performance = data[-1].get("viral_score", 0.7)
    
    if recent_performance < 0.6:
        print("[!] Neural Loop: Performance niedrig. Initiiere Parameter-Shift...")
        adjust_brain_parameters(shift="aggressive")
    elif recent_performance > 0.9:
        print("[+] Neural Loop: Performance peak. Stabilisiere Parameter.")
        adjust_brain_parameters(shift="stable")

def adjust_brain_parameters(shift):
    if not BRAIN_CONFIG.exists():
        return
    with open(BRAIN_CONFIG, "r+") as f:
        config = json.load(f)
        if shift == "aggressive":
            config["cut_tempo"] = config.get("cut_tempo", 1.0) + 0.15
            config["vfx_intensity"] = config.get("vfx_intensity", 1.0) + 0.2
        f.seek(0)
        json.dump(config, f, indent=4)
        f.truncate()
        print("[✓] DirectorBrain rekalibriert für nächste Iteration.")

if __name__ == "__main__":
    process_viral_feedback()