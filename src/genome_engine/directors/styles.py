"""
styles.py — Director presets and visual style definitions.
"""
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class DirectorStyle:
    name: str
    target_cuts_per_min: float
    camera_motions: List[str]
    color_palettes: List[str]
    fx_transitions: List[str]
    preferred_tags: List[str]


STYLES: Dict[str, DirectorStyle] = {
    "alpine_drill_comedy": DirectorStyle(
        name="alpine_drill_comedy",
        target_cuts_per_min=75.0,
        camera_motions=["push_zoom_punch", "3d_wobble_shake", "drone_flyover"],
        color_palettes=["vhs_retro", "mountain_cold_cyan", "gold_chain_shine"],
        fx_transitions=["glitch_datamosh", "flash_cut", "spin_wobble"],
        preferred_tags=["lederhosen", "zugspitze", "gold_chains", "moshpit", "snow"]
    ),
    "boombap_hype": DirectorStyle(
        name="boombap_hype",
        target_cuts_per_min=50.0,
        camera_motions=["low_angle_pan", "slow_zoom_in", "handheld_raw"],
        color_palettes=["warm_contrast", "film_grain", "bronx_sepia"],
        fx_transitions=["hard_cut", "dissolve_smoke", "scratch_cut"],
        preferred_tags=["vinyl", "turntable", "graffiti", "boombox", "street"]
    ),
    "cyberpunk_glitch": DirectorStyle(
        name="cyberpunk_glitch",
        target_cuts_per_min=90.0,
        camera_motions=["whip_pan", "3d_orbit", "fast_tracking"],
        color_palettes=["neon_magenta", "cyan_dark", "high_contrast"],
        fx_transitions=["rgb_split", "digital_noise", "pixelate_drop"],
        preferred_tags=["neon", "hologram", "future_city", "laser", "glitch"]
    )
}


def get_director_style(name: str) -> DirectorStyle:
    return STYLES.get(name, STYLES["alpine_drill_comedy"])
