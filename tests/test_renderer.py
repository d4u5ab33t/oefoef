"""
test_renderer.py — Tests for v0.8 Professional Renderer components.
"""
import pytest
import json
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment
from genome_engine.renderer.otio_exporter import OTIOExporter
from genome_engine.renderer.ffmpeg_engine import FFmpegRenderEngine


def test_otio_export():
    edl = EditDecisionList(
        track_path="song.mp3",
        total_duration_sec=10.0,
        bpm=120.0,
        style_name="alpine_drill_comedy",
        segments=[
            TimelineSegment(1, 0.0, 5.0, 5.0, "verse", 0.6, "hard_cut", "on_beat", assigned_clip_path="v1.mp4"),
            TimelineSegment(2, 5.0, 10.0, 5.0, "chorus", 0.9, "zoom_push", "on_drop", assigned_clip_path="v2.mp4")
        ]
    )

    otio_json = OTIOExporter.export_otio(edl)
    parsed = json.loads(otio_json)
    
    assert parsed["OTIO_SCHEMA"] == "Timeline.1"
    clips = parsed["tracks"]["children"][0]["children"]
    assert len(clips) == 2
    assert clips[0]["media_reference"]["target_url"] == "v1.mp4"


def test_ffmpeg_engine(tmp_path):
    edl = EditDecisionList(
        track_path="song.mp3",
        total_duration_sec=10.0,
        bpm=120.0,
        style_name="alpine_drill_comedy",
        segments=[TimelineSegment(1, 0.0, 5.0, 5.0, "verse", 0.6, "hard_cut", "on_beat", assigned_clip_path="v1.mp4")]
    )

    engine = FFmpegRenderEngine(use_nvenc=True)
    out_file = str(tmp_path / "out.mp4")
    
    success = engine.render(edl, out_file, dry_run=True)
    assert success is True
