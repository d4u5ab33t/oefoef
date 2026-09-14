"""
council.py — Multi-agent Director Council for visual style orchestration.
"""
import random
from typing import List
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment
from genome_engine.directors.styles import get_director_style, DirectorStyle


class DirectorCouncil:
    """Orchestrates director directives across an EditDecisionList."""

    def __init__(self, style_name: str = "alpine_drill_comedy"):
        self.style: DirectorStyle = get_director_style(style_name)

    def review_and_enhance(self, edl: EditDecisionList) -> EditDecisionList:
        enhanced_segments: List[TimelineSegment] = []

        for seg in edl.segments:
            # Inject preferred style tags
            tags = list(set(seg.query_tags + self.style.preferred_tags[:2]))
            
            # Select specific camera motion
            if seg.sync_type == "on_drop":
                camera = "push_zoom_punch"
                fx = "glitch_datamosh"
            elif seg.energy_level > 0.7:
                camera = self.style.camera_motions[0]
                fx = self.style.fx_transitions[0]
            else:
                camera = self.style.camera_motions[1] if len(self.style.camera_motions) > 1 else "static"
                fx = "hard_cut"

            # Enhance segment query tags and cut style
            seg.query_tags = tags
            seg.cut_style = fx
            enhanced_segments.append(seg)

        edl.segments = enhanced_segments
        return edl
