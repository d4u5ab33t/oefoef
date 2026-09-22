"""
clip_resolver.py — Resolves timeline segment queries into specific media clips.
"""
from typing import List, Set, Optional
import random
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment
from genome_engine.resolver.semantic_index import SemanticIndex, MediaAsset
from genome_engine.rl.user_preferences import UserPreferenceProfile
from genome_engine.rl.bandit import ContextualBandit


class ClipResolver:
    """Assigns optimal media clips to timeline segments using semantic matching, preferences, and RL."""

    def __init__(
        self,
        index: SemanticIndex,
        user_prefs: Optional[UserPreferenceProfile] = None,
        bandit: Optional[ContextualBandit] = None
    ):
        self.index = index
        self.user_prefs = user_prefs or UserPreferenceProfile()
        self.bandit = bandit or ContextualBandit(epsilon=0.1)

    def _score_candidate(self, asset: MediaAsset, segment: TimelineSegment, used_count: int) -> float:
        """Calculates matching score for an asset against a timeline segment."""
        # 1. Base Tag Match
        seg_tag_set = set(t.lower() for t in segment.query_tags)
        asset_tag_set = set(t.lower() for t in asset.tags)
        common_tags = seg_tag_set.intersection(asset_tag_set)
        score = len(common_tags) * 1.5

        # 2. User Preferences Bonus/Penalty
        pref_mod = self.user_prefs.get_score_modifier(asset.tags)
        score += pref_mod

        # 3. Duration Fit Bonus
        if asset.duration_sec >= segment.duration_sec:
            score += 1.0
        else:
            score -= 2.0  # Penalty for too-short clips

        # 4. Duplicate Penalty
        score -= (used_count * 2.5)

        return score

    def resolve_edl(self, edl: EditDecisionList) -> EditDecisionList:
        used_counts: dict[str, int] = {}

        for seg in edl.segments:
            candidates = self.index.search_by_tags(seg.query_tags)
            
            # If index is empty, use placeholder
            if not candidates:
                seg.assigned_clip_path = "placeholder_clip.mp4"
                seg.clip_in_sec = 0.0
                seg.clip_out_sec = seg.duration_sec
                continue

            # Score each candidate
            scored = [
                (cand, self._score_candidate(cand, seg, used_counts.get(cand.clip_path, 0)))
                for cand in candidates
            ]
            scored.sort(key=lambda item: item[1], reverse=True)

            chosen_asset: MediaAsset = scored[0][0]
            clip_path = chosen_asset.clip_path
            used_counts[clip_path] = used_counts.get(clip_path, 0) + 1

            # Determine dynamic sub-clip in-point / out-point
            available_dur = max(0.5, chosen_asset.duration_sec)
            needed_dur = seg.duration_sec

            if available_dur > needed_dur + 0.5:
                # Randomize start point within the safe boundary
                max_start = available_dur - needed_dur
                clip_in = round(random.uniform(0.0, max_start * 0.7), 2)
            else:
                clip_in = 0.0

            clip_out = min(available_dur, round(clip_in + needed_dur, 2))

            seg.assigned_clip_path = clip_path
            seg.clip_in_sec = clip_in
            seg.clip_out_sec = clip_out

            # Apply bandit strategy if drop
            if seg.sync_type == "on_drop":
                action = self.bandit.select_action()
                seg.cut_style = action

        return edl
