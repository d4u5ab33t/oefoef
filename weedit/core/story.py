"""
weedit.core.story — AI Story Arc Generator, Visual Continuity & Viral Scoring Engine
"""
from dataclasses import dataclass, field
import numpy as np

@dataclass
class ViralScoreResult:
    score: float
    breakdown: dict
    tips: list

class StoryEngine:
    def __init__(self):
        self.narrative_arcs = ["intro", "environment", "characters", "conflict", "build", "drop", "outro"]

    def plan_story_pacing(self, audio_analysis) -> list:
        duration = getattr(audio_analysis, "duration_sec", 180.0)
        sections = getattr(audio_analysis, "sections", [])
        
        timeline_plan = []
        current_time = 0.0
        
        # Segment length target based on BPM (faster BPM = tighter cuts)
        bpm = getattr(audio_analysis, "bpm", 120.0)
        base_cut_len = max(1.5, min(4.0, 60.0 / bpm * 2))

        while current_time < duration:
            # Determine narrative arc stage
            progress = current_time / duration
            if progress < 0.15:
                arc = "intro"
                shot_type = "wide"
            elif progress < 0.35:
                arc = "environment"
                shot_type = "medium"
            elif progress < 0.55:
                arc = "characters"
                shot_type = "close_up"
            elif progress < 0.75:
                arc = "build"
                shot_type = "medium"
            elif progress < 0.90:
                arc = "drop"
                shot_type = "action"
            else:
                arc = "outro"
                shot_type = "wide"

            seg_len = base_cut_len * np.random.uniform(0.8, 1.2)
            if current_time + seg_len > duration:
                seg_len = duration - current_time

            timeline_plan.append({
                "start_sec": current_time,
                "end_sec": current_time + seg_len,
                "arc_stage": arc,
                "shot_type": shot_type,
                "target_energy": 0.8 if arc in ("build", "drop") else 0.4
            })
            current_time += seg_len

        return timeline_plan

    def calculate_viral_score(self, timeline_segments: list, audio_analysis) -> ViralScoreResult:
        if not timeline_segments:
            return ViralScoreResult(score=50.0, breakdown={}, tips=["Erstelle zuerst eine Timeline"])

        total_segs = len(timeline_segments)
        face_cuts = sum(1 for s in timeline_segments if getattr(s, "confidence", 0.5) > 0.6)
        fast_cuts = sum(1 for s in timeline_segments if (s.end_sec - s.start_sec) < 2.2)

        face_ratio = face_cuts / max(1, total_segs)
        rhythm_sync_score = min(100.0, 70.0 + (fast_cuts / max(1, total_segs)) * 30.0)
        visual_variety_score = min(100.0, 65.0 + min(35.0, total_segs * 1.5))

        overall_score = round(face_ratio * 30.0 + rhythm_sync_score * 0.4 + visual_variety_score * 0.3, 1)

        tips = []
        if face_ratio < 0.4:
            tips.append("🎯 Mehr Face-Cuts im Drop & Chorus einbauen (+15% Viral-Potential)")
        if rhythm_sync_score < 80:
            tips.append("⚡ Schnellere Schnitte in Verse-Passagen erzwingen (+8% Engagement)")
        if visual_variety_score < 75:
            tips.append("🎨 Bessere Farb- & Visual-Kontinuität (+12% Watchtime)")

        if not tips:
            tips.append("🚀 Hervorragendes Video-Pacing! Bereits optimal für Viral-Reichweite.")

        breakdown = {
            "face_cut_potency": f"{round(face_ratio*100)}%",
            "rhythm_sync_precision": f"{round(rhythm_sync_score)}%",
            "visual_variety": f"{round(visual_variety_score)}%"
        }

        return ViralScoreResult(score=overall_score, breakdown=breakdown, tips=tips)
