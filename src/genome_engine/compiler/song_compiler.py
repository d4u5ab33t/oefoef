"""
song_compiler.py — Compiles GenomeData into an actionable EditDecisionList.
"""
from typing import List
from genome_engine.genome.schema import GenomeData
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment


class SongCompiler:
    """Compiles rhythm & visual genome into timed video segments."""

    def compile(self, genome: GenomeData) -> EditDecisionList:
        rhythm = genome.rhythm
        visual = genome.visual
        
        segments: List[TimelineSegment] = []
        beat_times = rhythm.beat_times if rhythm.beat_times else [0.0]
        duration = rhythm.duration_sec
        bpm = rhythm.bpm

        # Determine target segment length in beats based on visual style / target cuts per min
        target_cuts_per_min = visual.target_cuts_per_min or 60.0
        sec_per_cut = 60.0 / target_cuts_per_min
        
        cur_time = 0.0
        segment_id = 1
        
        while cur_time < duration:
            # Find current section
            cur_section = "main"
            cur_energy = 0.5
            for sec in rhythm.sections:
                if sec.start_sec <= cur_time < sec.end_sec:
                    cur_section = sec.label
                    cur_energy = sec.energy
                    break
            
            # Check for drop
            is_drop = any(abs(cur_time - d) < 1.0 for d in rhythm.drop_timestamps)
            
            # Select cut style & sync type
            if is_drop:
                cut_style = "glitch_transition"
                sync_type = "on_drop"
                seg_dur = min(sec_per_cut * 0.5, duration - cur_time)
            elif cur_energy > 0.7:
                cut_style = "zoom_push"
                sync_type = "on_beat"
                seg_dur = min(sec_per_cut * 0.75, duration - cur_time)
            elif cur_section == "intro":
                cut_style = "fade_black"
                sync_type = "ambient"
                seg_dur = min(sec_per_cut * 1.5, duration - cur_time)
            else:
                cut_style = "hard_cut"
                sync_type = "on_beat"
                seg_dur = min(sec_per_cut, duration - cur_time)

            seg_dur = max(0.5, round(seg_dur, 3))
            end_time = min(duration, cur_time + seg_dur)

            # Query tags based on section & style
            query_tags = [cur_section, visual.style_name]
            if is_drop:
                query_tags.append("drop_energy")
            if cur_energy > 0.7:
                query_tags.append("high_energy")

            segment = TimelineSegment(
                segment_id=segment_id,
                start_sec=round(cur_time, 3),
                end_sec=round(end_time, 3),
                duration_sec=round(end_time - cur_time, 3),
                section_name=cur_section,
                energy_level=round(cur_energy, 2),
                cut_style=cut_style,
                sync_type=sync_type,
                query_tags=query_tags
            )
            segments.append(segment)
            segment_id += 1
            cur_time = end_time

        return EditDecisionList(
            track_path=genome.audio_path,
            total_duration_sec=duration,
            bpm=bpm,
            style_name=visual.style_name,
            segments=segments
        )
