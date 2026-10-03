"""
test_renderer.py — Tests for v0.8 Professional Renderer components.
"""
import pytest
import json
from pathlib import Path
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment as GenomeSegment
from genome_engine.renderer.otio_exporter import OTIOExporter
from genome_engine.renderer.ffmpeg_engine import FFmpegRenderEngine

from renderer import (
    _color_grade_filter,
    _semantic_motif_grade_filter,
    _fx_filter,
    _plan_segment_filter,
)
from timeline_builder import TimelineSegment


def test_otio_export():
    edl = EditDecisionList(
        track_path="song.mp3",
        total_duration_sec=10.0,
        bpm=120.0,
        style_name="alpine_drill_comedy",
        segments=[
            GenomeSegment(1, 0.0, 5.0, 5.0, "verse", 0.6, "hard_cut", "on_beat", assigned_clip_path="v1.mp4"),
            GenomeSegment(2, 5.0, 10.0, 5.0, "chorus", 0.9, "zoom_push", "on_drop", assigned_clip_path="v2.mp4")
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
        segments=[GenomeSegment(1, 0.0, 5.0, 5.0, "verse", 0.6, "hard_cut", "on_beat", assigned_clip_path="v1.mp4")]
    )

    engine = FFmpegRenderEngine(use_nvenc=True)
    out_file = str(tmp_path / "out.mp4")
    
    success = engine.render(edl, out_file, dry_run=True)
    assert success is True


def test_color_grade_disabled_by_default():
    import config
    assert config.STYLE_COLOR_GRADE_ENABLED is False
    # When disabled, standard call must return empty string (unmodified source colors)
    assert _color_grade_filter("lowkey", "desaturated") == ""
    assert _semantic_motif_grade_filter("BETON", "urban") == ""


def test_color_grade_filter_palettes():
    # Test dark / lowkey
    flt_low = _color_grade_filter("lowkey", "desaturated", force_enable=True)
    assert "contrast=1.2" in flt_low or "contrast=1.20" in flt_low
    assert "saturation=0.35" in flt_low

    # Test neon / dramatic
    flt_neon = _color_grade_filter("dramatic", "neon", force_enable=True)
    assert "contrast=1.25" in flt_neon
    assert "saturation=1.45" in flt_neon

    # Test vintage / golden_hour
    flt_vintage = _color_grade_filter("natural", "vintage_film", force_enable=True)
    assert "saturation=0.88" in flt_vintage


def test_semantic_motif_grading():
    # Beton -> Industrial grey
    flt_beton = _semantic_motif_grade_filter("BETON", "urban", force_enable=True)
    assert "colorbalance" in flt_beton

    # Cyber -> Neon Teal/Magenta
    flt_cyber = _semantic_motif_grade_filter("CYBER", "glitch", force_enable=True)
    assert "contrast=1.12" in flt_cyber

    # Weed -> Emerald Green
    flt_weed = _semantic_motif_grade_filter("WEED", "chill", force_enable=True)
    assert "gamma=1.04" in flt_weed


def test_fx_filter_expansion():
    flt = _fx_filter(("vignette", "grain", "chroma", "scanlines"), duration=2.5)
    assert "vignette" in flt
    assert "noise" in flt
    assert "rgbashift" in flt
    assert "drawgrid" in flt


def test_audio_mastering_constants_and_configuration():
    import config
    assert config.AUDIO_MASTER_ENABLED is True
    assert config.AUDIO_MASTER_SUBSONIC_HPF_HZ == 28
    assert config.AUDIO_MASTER_808_BOOST_HZ == 65
    assert config.AUDIO_MASTER_808_BOOST_DB == 2.0
    assert config.AUDIO_MASTER_MUD_CUT_HZ == 280
    assert config.AUDIO_MASTER_MUD_CUT_DB == -2.2
    assert config.AUDIO_MASTER_MS_LOWCUT_HZ == 120
    assert config.AUDIO_MASTER_VOCAL_PRESENCE_HZ == 3500
    assert config.AUDIO_MASTER_SUNO_DEHARSH_HZ == 4500
    assert config.AUDIO_MASTER_SUNO_DEHARSH_DB == -1.8
    assert config.AUDIO_MASTER_HF_AIR_HZ == 12800
    assert config.AUDIO_MASTER_HF_AIR_DB == 2.2
    assert config.AUDIO_MASTER_SATURATION_ENABLED is True
    assert config.AUDIO_MASTER_CLIP_ENABLED is True


def test_audio_mastering_filtergraph_construction(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    import renderer
    import subprocess

    captured_cmds = []

    def mock_run(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        mock_res = MagicMock()
        mock_res.returncode = 0
        # If running loudnorm measurement null sink
        if "-f" in cmd and "null" in cmd:
            mock_res.stderr = json.dumps({
                "input_i": "-16.5",
                "input_tp": "-2.1",
                "input_lra": "6.8",
                "input_thresh": "-26.5"
            })
        else:
            mock_res.stderr = ""
            # Touch target mastered file
            out_file = Path(cmd[-1])
            out_file.touch()
        return mock_res

    monkeypatch.setattr(renderer.subprocess, "run", mock_run)

    test_audio = tmp_path / "test_song.m4a"
    test_audio.touch()

    log_msgs = []
    res = renderer._master_audio(str(test_audio), tmp_path, log_msgs.append)

    assert res == str(tmp_path / "mastered_audio.m4a"), f"Mastering failed, log: {log_msgs}"
    assert len(captured_cmds) == 2
    master_cmd = captured_cmds[1]
    filter_arg = master_cmd[master_cmd.index("-filter_complex") + 1]

    # Subsonic HPF
    assert "highpass=f=28" in filter_arg
    # M/S mono sub cut
    assert "highpass=f=120" in filter_arg
    # 808 subbass punch
    assert "bass=f=65:g=2.0" in filter_arg
    # Mud cut
    assert "equalizer=f=280" in filter_arg
    # Vocal presence & Suno deharsh
    assert "equalizer=f=3500" in filter_arg
    assert "equalizer=f=4500" in filter_arg
    # HF Air recovery
    assert "treble=f=12800" in filter_arg
    # Sättigung / Tape saturation & Hard clip & Limiter
    assert "asoftclip=type=tanh" in filter_arg
    assert "asoftclip=type=hard" in filter_arg
    assert "alimiter=" in filter_arg

