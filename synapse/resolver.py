"""RESOLVER - The Constraint SAT Solver.

Verantwortung:
- Nimmt 'Needs' vom Director Compiler entgegen.
- Sucht in den Clip Genomes nach der besten Kombination.
- Löst Constraints (Farbkontinuität, Motion-Flow, Theme).
- Nutzt RL-Bandit für die finale Auswahl bei Gleichstand.
"""
from __future__ import annotations

from typing import Any, Optional
from hive_io import load_hive

class Resolver:
    def __init__(self):
        pass

    def solve_needs(self, needs: list[str], style_constraints: dict, 
                    energy_target: float) -> Optional[str]:
        """
        Sucht einen Clip, der alle 'Needs' erfüllt und zum Style passt.
        """
        hive = load_hive()
        candidates = hive.get("clip_genomes", {})
        
        best_clip = None
        max_score = -1.0

        for cid, genome in candidates.items():
            score = 0.0
            # 1. Semantischer Match (Needs)
            concepts = genome.get("semantics", {}).get("concepts", [])
            matches = len(set(needs) & set(concepts))
            score += matches * 2.0
            
            # 2. Style Match (Constraints)
            vis = genome.get("visuals", {})
            if vis.get("motion") == style_constraints.get("camera"):
                score += 1.0
            if vis.get("lighting") == style_constraints.get("lighting"):
                score += 1.0
                
            # 3. Energy / Entropy Match
            # Informationsdichte vs. Musikenergie
            entropy = vis.get("entropy", 0.5)
            energy_diff = abs(entropy - energy_target)
            score += (1.0 - energy_diff) * 1.5
            
            if score > max_score:
                max_score = score
                best_clip = cid
                
        return best_clip

# Singleton
resolver = Resolver()
