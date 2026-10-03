"""VISUAL BREATHING & DENSITY ENGINE - The Rhythm of Information.

Verantwortung:
- Steuerung der Informationsdichte (Visual Breathing).
- Verhindert 'Dauerfeuer' durch strategische Pausen.
- Koppelt die visuelle Komplexität an die musikalische Spannung.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from hive_io import load_hive

class VisualBreathingEngine:
    def __init__(self):
        pass

    def calculate_required_density(self, energy_curve: list[float], 
                                 current_index: int, 
                                 style_constraints: dict) -> float:
        """
        Berechnet die benötigte Informationsdichte für einen Frame/Schnitt.
        Implementiert 'Visual Breathing': Beat-Beat-Beat-Pause-Beat.
        """
        # 1. Basis-Energie aus der Musik
        base_energy = energy_curve[current_index] if current_index < len(energy_curve) else 0.5
        
        # 2. Breathing-Logik: Erzeugt künstliche Täler (Pausen)
        # Alle 4-6 Beats ein "Atmen" einbauen, um Spannung aufzubauen
        breathing_cycle = (current_index + 1) % 5
        if breathing_cycle == 0:
            # Pause/Atmen: Dichte massiv senken, egal wie hoch die Musikenergie ist
            return base_energy * 0.3
        
        # 3. Style-Modifikator (z.B. .drill will höhere Dichte als .ambient)
        style_mod = style_constraints.get("motion_density", 1.0)
        
        return base_energy * style_mod

    def evaluate_density_fit(self, clip_entropy: float, target_density: float) -> float:
        """
        Bewertet, wie gut die Informationsdichte eines Clips 
        zur gewünschten Dichte passt.
        """
        return 1.0 - abs(clip_entropy - target_density)

# Singleton
breathing_engine = VisualBreathingEngine()
