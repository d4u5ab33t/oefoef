"""
clip_resolver.py — Resolves timeline segment queries into specific media clips.
"""
from typing import List, Set
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment
from genome_engine.resolver.semantic_index import SemanticIndex, MediaAsset


class ClipResolver:
    """Assigns optimal media clips to timeline segments."""

    def __init__(self, index: SemanticIndex):
        self.index = index

    def resolve_edl(self, edl: EditDecisionList) -> EditDecisionList:
        used_clips: Set[str] = set()

        for seg in edl.segments:
            candidates = self.index.search_by_tags(seg.query_tags)
            
            # Prefer unused clip first
            chosen_asset: MediaAsset | None = None
            for cand in candidates:
                if cand.clip_path not in used_clips:
                    chosen_asset = cand
                    break

            if not chosen_asset and candidates:
                chosen_asset = candidates[0]  # Fallback to best match if all used

            if chosen_asset:
                seg.assigned_clip_path = chosen_asset.clip_path
                seg.clip_in_sec = 0.0
                seg.clip_out_sec = min(chosen_asset.duration_sec, seg.duration_sec)
                used_clips.add(chosen_asset.clip_path)

        return edl
