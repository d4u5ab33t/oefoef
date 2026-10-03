"""STYLE COMPILER - The CSS for Visuals.

Verantwortung:
- Lädt '.style' Definitionen (JSON/YAML).
- Übersetzt abstrakte Begriffe (.drill, .horror) in technische Constraints.
- Implementiert Genome Inheritance (z.B. .hero -> .drill_hero).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).parent
STYLES_DIR = _HERE / "styles"

class StyleCompiler:
    def __init__(self):
        STYLES_DIR.mkdir(parents=True, exist_ok=True)
        self.loaded_styles: dict[str, dict] = {}

    def load_style(self, style_id: str) -> dict[str, Any]:
        """Ladet einen Style und löst Vererbung (Inheritance) rekursiv auf. [Manifest]"""
        style_file = STYLES_DIR / f"{style_id}.style.json"
        
        if not style_file.exists():
            # Check if it's a known internal style
            if style_id == "default":
                return self._get_default_style()
            # Fallback to default to avoid crashing
            print(f"[StyleCompiler] Warning: Style '{style_id}' not found. Falling back to default.")
            return self._get_default_style()

        with open(style_file, "r", encoding="utf-8") as f:
            style_data = json.load(f)

        # Genome Inheritance: Recursive Merge
        if "extends" in style_data:
            parent_style = self.load_style(style_data["extends"])
            # Deep merge for constraints and physics
            merged = {**parent_style}
            for key, value in style_data.items():
                if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                    merged[key] = {**merged[key], **value}
                else:
                    merged[key] = value
            return merged

        return style_data

    def _get_default_style(self) -> dict[str, Any]:
        return {
            "name": "default",
            "constraints": {
                "camera": "static", "transition": "cut", "fx": "none"
            },
            "physics": { "tension": "linear", "release": "slow" },
            "palette": { "primary": "#FFFFFF", "secondary": "#000000" }
        }

    def get_constraint(self, style_id: str, key: str) -> Any:
        """Hole spezifischen Constraint aus einem Style."""
        style = self.load_style(style_id)
        return style.get("constraints", {}).get(key, "none")

# Singleton
style_compiler = StyleCompiler()
