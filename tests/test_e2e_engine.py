"""
test_e2e_engine.py — Full End-to-End integration test for Native Genome Engine v1.0.
"""
import pytest
import os
import json
from genome_engine.scanner.audio_analyzer import AudioScanner
from genome_engine.genome.schema import GenomeData, VisualGenome
from genome_engine.compiler.song_compiler import SongCompiler
from genome_engine.directors.council import DirectorCouncil
from genome_engine.resolver.semantic_index import SemanticIndex, MediaAsset
from genome_engine.resolver.clip_resolver import ClipResolver
from genome_engine.camera.kinematics import KinematicsEngine
from genome_engine.renderer.otio_exporter import OTIOExporter
from genome_engine.renderer.ffmpeg_engine import FFmpegRenderEngine
from genome_engine.learning.synapse_loop import AestheticGenomeLearner
from genome_engine.cli import main


def test_full_genome_pipeline(tmp_path):
    # 1. Create test audio file
    dummy_audio = tmp_path / "test_track.mp3"
    dummy_audio.write_bytes(b"dummy audio data")

    # 2. Audio Scanner -> Rhythm Genome
    scanner = AudioScanner()
    rhythm = scanner.scan_file(str(dummy_audio))
    assert rhythm.bpm > 0

    # 3. Create Visual Genome & GenomeData
    visual = VisualGenome(style_name="alpine_drill_comedy")
    genome = GenomeData(audio_path=str(dummy_audio), rhythm=rhythm, visual=visual)

    # 4. Song Compiler -> EDL
    compiler = SongCompiler()
    edl = compiler.compile(genome)
    assert len(edl.segments) > 0

    # 5. Director Council
    council = DirectorCouncil("alpine_drill_comedy")
    enhanced_edl = council.review_and_enhance(edl)

    # 6. Genome Resolver
    index = SemanticIndex()
    index.add_asset(MediaAsset("clip_zugspitze.mp4", tags=["snow", "zugspitze", "lederhosen"]))
    index.add_asset(MediaAsset("clip_moshpit.mp4", tags=["gold_chains", "moshpit"]))
    resolver = ClipResolver(index)
    resolved_edl = resolver.resolve_edl(enhanced_edl)

    # 7. Cinematic Camera Trajectory
    traj = KinematicsEngine.generate_push_zoom(duration=resolved_edl.segments[0].duration_sec)
    assert traj.sample_at(0.5).zoom_scale >= 1.0

    # 8. OTIO & FFmpeg Exporter
    otio_json = OTIOExporter.export_otio(resolved_edl)
    assert "GenomeEngine_alpine_drill_comedy" in otio_json

    ffmpeg_engine = FFmpegRenderEngine(use_nvenc=True)
    out_mp4 = str(tmp_path / "final.mp4")
    render_success = ffmpeg_engine.render(resolved_edl, out_mp4, dry_run=True)
    assert render_success is True

    # 9. Aesthetic Learner Closed Loop
    learner = AestheticGenomeLearner()
    ref_profile = learner.analyze_reference("ref_sample.mp4")
    adapted_visual = learner.adapt_visual_genome(visual, ref_profile)
    assert adapted_visual.target_cuts_per_min == 63.0



def test_cli_e2e_compile(tmp_path):
    dummy_audio = tmp_path / "song.mp3"
    dummy_audio.write_bytes(b"dummy audio data")
    out_edl = tmp_path / "edl.json"

    ret = main(["compile", "--song", str(dummy_audio), "--output", str(out_edl), "--dry-run"])
    assert ret == 0
    assert os.path.exists(out_edl)
