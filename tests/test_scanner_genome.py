"""
test_scanner_genome.py — Tests for v0.2 Scanner & Genome components.
"""
import pytest
import os
from genome_engine.genome.schema import RhythmGenome, VisualGenome, GenomeData, SectionInfo
from genome_engine.scanner.audio_analyzer import AudioScanner


def test_genome_schema_serialization():
    rhythm = RhythmGenome(
        bpm=140.0,
        duration_sec=120.0,
        beat_times=[0.0, 0.428, 0.857, 1.285],
        onset_times=[0.0, 0.428],
        energy_curve=[0.2, 0.5, 0.8, 0.9],
        sections=[SectionInfo(0.0, 15.0, "intro", 0.3)],
        drop_timestamps=[30.0]
    )
    visual = VisualGenome(
        style_name="alpine_drill_comedy",
        target_cuts_per_min=90.0,
        camera_motion=["push_zoom", "3d_pan"],
        color_palette=["high_contrast"],
        fx_tags=["glitch"],
        transition_policy="rhythm_quantized"
    )
    genome = GenomeData(audio_path="test.mp3", rhythm=rhythm, visual=visual)
    
    json_str = genome.to_json()
    assert "alpine_drill_comedy" in json_str
    assert "test.mp3" in json_str
    
    restored = GenomeData.from_dict(genome.to_dict())
    assert restored.rhythm.bpm == 140.0
    assert restored.visual.style_name == "alpine_drill_comedy"
    assert len(restored.rhythm.sections) == 1
    assert restored.rhythm.sections[0].label == "intro"


def test_audio_scanner_fallback(tmp_path):
    # Create dummy audio file path
    dummy_audio = tmp_path / "sample.mp3"
    dummy_audio.write_bytes(b"dummy mp3 data header")

    scanner = AudioScanner()
    rhythm = scanner.scan_file(str(dummy_audio))

    assert rhythm.bpm > 0
    assert rhythm.duration_sec > 0
    assert len(rhythm.beat_times) > 0
    assert len(rhythm.sections) == 5
    assert rhythm.sections[0].label == "intro"
    assert rhythm.sections[2].label == "chorus"
