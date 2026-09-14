"""
test_director_council.py — Tests for v0.4 Director Council components.
"""
import pytest
from genome_engine.genome.schema import RhythmGenome, VisualGenome, GenomeData, SectionInfo
from genome_engine.compiler.song_compiler import SongCompiler
from genome_engine.directors.council import DirectorCouncil
from genome_engine.directors.styles import get_director_style


def test_director_style_presets():
    style = get_director_style("alpine_drill_comedy")
    assert style.name == "alpine_drill_comedy"
    assert "lederhosen" in style.preferred_tags
    assert len(style.camera_motions) > 0


def test_director_council_review():
    rhythm = RhythmGenome(
        bpm=140.0,
        duration_sec=30.0,
        beat_times=[i * 0.428 for i in range(70)],
        onset_times=[i * 0.428 for i in range(70)],
        energy_curve=[0.8] * 30,
        sections=[SectionInfo(0.0, 30.0, "chorus", 0.85)],
        drop_timestamps=[10.0]
    )
    visual = VisualGenome(style_name="alpine_drill_comedy")
    genome = GenomeData(audio_path="test.mp3", rhythm=rhythm, visual=visual)

    compiler = SongCompiler()
    edl = compiler.compile(genome)

    council = DirectorCouncil("alpine_drill_comedy")
    enhanced_edl = council.review_and_enhance(edl)

    assert len(enhanced_edl.segments) > 0
    # Confirm director preferred tags injected into segment query tags
    sample_tags = enhanced_edl.segments[0].query_tags
    assert any(t in sample_tags for t in ["lederhosen", "zugspitze", "gold_chains"])
