"""
song_compiler.py — Compiles GenomeData into an actionable EditDecisionList.
"""
from typing import List, Optional
import bisect
from genome_engine.genome.schema import GenomeData
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment


class SongCompiler:
    """Compiles rhythm & visual genome into timed video segments snapped to beat grid."""

    def compile(self, genome: GenomeData) -> EditDecisionList:
        rhythm = genome.rhythm
        visual = genome.visual
        
        duration = max(0.5, float(rhythm.duration_sec))
        bpm = max(30.0, float(rhythm.bpm))
        beat_times = sorted([b for b in rhythm.beat_times if 0.0 <= b <= duration])
        
        # If no beat times provided, synthesize regular beat grid
        if len(beat_times) < 2:
            beat_interval = 60.0 / bpm
            beat_times = [round(i * beat_interval, 3) for i in range(int(duration / beat_interval) + 1)]

        # Ensure starting with 0.0 and ending near duration
        if not beat_times or beat_times[0] > 0.1:
            beat_times.insert(0, 0.0)

        # Determine target segment length in seconds (from cuts per min)
        target_cuts_per_min = visual.target_cuts_per_min or 60.0
        nominal_sec_per_cut = 60.0 / max(1.0, target_cuts_per_min)
        
        segments: List[TimelineSegment] = []
        cur_time = 0.0
        segment_id = 1
        
        # Helper: snap time to nearest future beat
        def snap_to_future_beat(target_time: float, min_gap: float = 0.3) -> float:
            idx = bisect.bisect_left(beat_times, target_time)
            if idx < len(beat_times):
                cand = beat_times[idx]
                if cand - cur_time >= min_gap:
                    return min(duration, cand)
            # Fallback
            return min(duration, round(target_time, 3))

        while cur_time < duration - 0.1:
            # Find current section
            cur_section = "verse"
            cur_energy = 0.5
            for sec in rhythm.sections:
                if sec.start_sec <= cur_time < sec.end_sec:
                    cur_section = sec.label
                    cur_energy = sec.energy
                    break
            
            # Check for drop within nearby window
            is_drop = any(abs(cur_time - d) < 0.75 for d in rhythm.drop_timestamps)
            
            # Select cut style, sync type, and target duration
            if is_drop:
                cut_style = "glitch_transition"
                sync_type = "on_drop"
                target_dur = nominal_sec_per_cut * 0.5
            elif cur_energy > 0.75:
                cut_style = "zoom_push"
                sync_type = "on_beat"
                target_dur = nominal_sec_per_cut * 0.75
            elif cur_section in ("intro", "outro"):
                cut_style = "fade_black" if cur_section == "intro" and segment_id == 1 else "hard_cut"
                sync_type = "ambient"
                target_dur = nominal_sec_per_cut * 1.5
            elif cur_section == "chorus":
                cut_style = "flash_cut"
                sync_type = "on_beat"
                target_dur = nominal_sec_per_cut * 0.8
            else:
                cut_style = "hard_cut"
                sync_type = "on_beat"
                target_dur = nominal_sec_per_cut

            # Minimum segment duration 0.25s
            target_dur = max(0.25, target_dur)
            raw_end = cur_time + target_dur
            
            if raw_end >= duration - 0.2:
                end_time = duration
            else:
                end_time = snap_to_future_beat(raw_end, min_gap=0.25)
                if end_time <= cur_time:
                    end_time = min(duration, round(cur_time + target_dur, 3))

            actual_dur = round(end_time - cur_time, 3)
            if actual_dur <= 0.05:
                # Force finish
                end_time = duration
                actual_dur = round(end_time - cur_time, 3)

            # Query tags based on section, style & energy
            query_tags = [cur_section, visual.style_name]
            if is_drop:
                query_tags.append("drop_energy")
            if cur_energy > 0.7:
                query_tags.append("high_energy")

            segment = TimelineSegment(
                segment_id=segment_id,
                start_sec=round(cur_time, 3),
                end_sec=round(end_time, 3),
                duration_sec=actual_dur,
                section_name=cur_section,
                energy_level=round(cur_energy, 2),
                cut_style=cut_style,
                sync_type=sync_type,
                query_tags=query_tags,
                motion_directive="push_zoom" if cur_energy > 0.7 else "static"
            )
            segments.append(segment)
            segment_id += 1
            cur_time = end_time

        # Ensure last segment reaches exact duration
        if segments and segments[-1].end_sec < duration:
            segments[-1].end_sec = round(duration, 3)
            segments[-1].duration_sec = round(segments[-1].end_sec - segments[-1].start_sec, 3)

        return EditDecisionList(
            track_path=genome.audio_path,
            total_duration_sec=round(duration, 3),
            bpm=bpm,
            style_name=visual.style_name,
            segments=segments
        )
