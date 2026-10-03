#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_orchestrator.py — Neural Render Orchestrator

Nutzt Timeline + Song/Clip-Semantik, um Render-Parameter
(FX-Intensität, Color-Grading, Stabilizer, Preset) dynamisch zu setzen.

Integration:
    from render_orchestrator import build_orchestrator_context, decide_render_profile

    ctx = build_orchestrator_context(song, audio, timeline, globe)
    profile = decide_render_profile(ctx)
    # profile an renderer.render_music_video(...) übergeben
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Dict, Optional
import psutil  # optional, für CPU/RAM-Load; bei Bedarf aus requirements entfernen

# ---------------------------------------------------------------------------

@dataclass
class OrchestratorContext:
    avg_motion: float = 0.0
    avg_semantic: float = 0.0
    avg_energy: float = 0.0
    avg_tension: float = 0.0
    cut_density: float = 0.0
    gpu_load: float = 0.0
    cpu_load: float = 0.0
    mem_usage: float = 0.0
    song_title: str = ""
    platform: str = "tiktok"

@dataclass
class RenderProfile:
    fx_strength: float
    color_grade_level: float
    stabilizer_enabled: bool
    speed_preset: str          # "ultrafast", "fast", "medium"
    max_parallel_jobs: int
    notes: str

# ---------------------------------------------------------------------------

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default

def _estimate_gpu_load() -> float:
    # Placeholder: falls du später echte GPU-Metriken hast, hier ersetzen.
    return 0.0

def _system_load() -> tuple[float, float]:
    try:
        cpu = psutil.cpu_percent(interval=0.1) / 100.0
        mem = psutil.virtual_memory().percent / 100.0
        return cpu, mem
    except Exception:
        return 0.0, 0.0

# ---------------------------------------------------------------------------

def build_orchestrator_context(
    song: Any,
    audio: Any,
    timeline: List[Any],
    globe: Optional[Dict[str, Dict[str, Any]]] = None,
    platform: str = "tiktok",
) -> OrchestratorContext:
    """Aggregiert alle relevanten Signale aus Timeline + Audio + Globe
    zu einem kompakten OrchestratorContext."""
    if not timeline:
        return OrchestratorContext(song_title=getattr(song, "title", "") or Path(song.path).stem,
                                   platform=platform)

    # Energie + Schnittdichte
    total_duration = sum(seg.end_sec - seg.start_sec for seg in timeline)
    avg_energy = sum(seg.target_energy for seg in timeline) / len(timeline)
    cut_density = len(timeline) / (total_duration / 60.0) if total_duration > 0 else 0.0

    # Motion/Semantik aus Globe (falls vorhanden)
    motions: List[float] = []
    semantics: List[float] = []
    if globe:
        for seg in timeline:
            meta = globe.get(seg.clip_path)
            if isinstance(meta, dict):
                motions.append(_safe_float(meta.get("motion", 0.0)))
                semantics.append(_safe_float(meta.get("semantic_score", 0.0)))
    avg_motion = sum(motions) / len(motions) if motions else 0.0
    avg_semantic = sum(semantics) / len(semantics) if semantics else 0.0

    # Tension aus Audio (falls vorhanden)
    avg_tension = _safe_float(getattr(audio, "tension", 0.0))

    cpu_load, mem_usage = _system_load()
    gpu_load = _estimate_gpu_load()

    return OrchestratorContext(
        avg_motion=avg_motion,
        avg_semantic=avg_semantic,
        avg_energy=avg_energy,
        avg_tension=avg_tension,
        cut_density=cut_density,
        gpu_load=gpu_load,
        cpu_load=cpu_load,
        mem_usage=mem_usage,
        song_title=getattr(song, "title", "") or Path(song.path).stem,
        platform=platform,
    )

# ---------------------------------------------------------------------------

def decide_render_profile(ctx: OrchestratorContext) -> RenderProfile:
    """Leitet aus dem OrchestratorContext konkrete Render-Parameter ab."""
    # Basiswerte
    fx_strength = 0.6
    color_grade_level = 0.5
    stabilizer_enabled = False
    speed_preset = "fast"
    max_parallel_jobs = 2
    notes_parts: List[str] = []

    # Motion → Stabilizer + FX
    if ctx.avg_motion > 0.7:
        stabilizer_enabled = True
        fx_strength = min(1.0, fx_strength + 0.2)
        notes_parts.append("hohe Motion → Stabilizer + mehr FX")

    # Semantik → Color-Grading
    if ctx.avg_semantic > 0.7:
        color_grade_level = min(1.0, color_grade_level + 0.3)
        notes_parts.append("hohe Semantik → stärkeres Color-Grading")

    # Energie + Schnittdichte → FX/Speed
    if ctx.avg_energy > 0.7 and ctx.cut_density > 80.0:
        fx_strength = min(1.0, fx_strength + 0.2)
        speed_preset = "ultrafast"
        notes_parts.append("hektische, energiegeladene Timeline → mehr FX, schneller Encode")
    elif ctx.avg_energy < 0.4 and ctx.cut_density < 40.0:
        fx_strength = max(0.2, fx_strength - 0.2)
        color_grade_level = min(1.0, color_grade_level + 0.1)
        speed_preset = "medium"
        notes_parts.append("ruhige Timeline → weniger FX, mehr Color-Grading")

    # System-Load → Parallelität/Preset
    if ctx.cpu_load > 0.8 or ctx.mem_usage > 0.8 or ctx.gpu_load > 0.8:
        max_parallel_jobs = 1
        if speed_preset == "ultrafast":
            speed_preset = "fast"
        notes_parts.append("hohe Systemlast → weniger Parallelität, moderater Encode")

    notes = "; ".join(notes_parts) if notes_parts else "Standard-Profil ohne besondere Anpassungen."

    return RenderProfile(
        fx_strength=round(fx_strength, 3),
        color_grade_level=round(color_grade_level, 3),
        stabilizer_enabled=stabilizer_enabled,
        speed_preset=speed_preset,
        max_parallel_jobs=max_parallel_jobs,
        notes=notes,
    )
