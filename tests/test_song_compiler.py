"""
test_song_compiler.py — Tests for v0.3 Song Compiler components.
"""
import pytest
from genome_engine.genome.schema import RhythmGenome, VisualGenome, GenomeData, SectionInfo
from genome_engine.compiler.song_compiler import SongCompiler


def test_song_compiler():
    rhythm = RhythmGenome(
        bpm=120.0,
        duration_sec=60.0,
        beat_times=[i * 0.5 for i in range(120)],
        onset_times=[i * 0.5 for i in range(120)],
        energy_curve=[0.5] * 50,
        sections=[
            SectionInfo(0.0, 10.0, "intro", 0.3),
            SectionInfo(10.0, 30.0, "verse", 0.6),
            SectionInfo(30.0, 50.0, "chorus", 0.9),
            SectionInfo(50.0, 60.0, "outro", 0.4),
        ],
        drop_timestamps=[30.0]
    )
    visual = VisualGenome(style_name="alpine_drill_comedy", target_cuts_per_min=60.0)
    genome = GenomeData(audio_path="test_track.mp3", rhythm=rhythm, visual=visual)

    compiler = SongCompiler()
    edl = compiler.compile(genome)

    assert edl.track_path == "test_track.mp3"
    assert edl.total_duration_sec == 60.0
    assert edl.bpm == 120.0
    assert len(edl.segments) > 0

    # Verify segment sequence covers full duration
    assert edl.segments[0].start_sec == 0.0
    assert edl.segments[-1].end_sec == 60.0
    
    # Check drop segment cut style
    drop_segs = [s for s in edl.segments if s.sync_type == "on_drop"]
    assert len(drop_segs) > 0
    assert drop_segs[0].cut_style == "glitch_transition"
