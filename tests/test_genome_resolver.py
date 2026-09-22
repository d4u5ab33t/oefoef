"""
test_genome_resolver.py — Tests for v0.5 Genome Resolver components.
"""
import pytest
import os
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment
from genome_engine.resolver.semantic_index import SemanticIndex, MediaAsset
from genome_engine.resolver.clip_resolver import ClipResolver
from genome_engine.rl.user_preferences import UserPreferenceProfile


def test_semantic_index_search():
    index = SemanticIndex()
    index.add_asset(MediaAsset("clip1.mp4", tags=["snow", "zugspitze"]))
    index.add_asset(MediaAsset("clip2.mp4", tags=["gold_chains", "moshpit"]))

    results = index.search_by_tags(["snow"])
    assert len(results) >= 1
    assert results[0].clip_path == "clip1.mp4"


def test_semantic_index_directory_scan(tmp_path):
    clip_dir = tmp_path / "clips"
    clip_dir.mkdir()
    (clip_dir / "zugspitze_mountain_drone.mp4").write_bytes(b"dummy")
    (clip_dir / "lederhosen_drill_moshpit.mov").write_bytes(b"dummy")
    (clip_dir / "notes.txt").write_bytes(b"ignored")

    index = SemanticIndex()
    count = index.scan_directory(str(clip_dir))
    assert count == 2
    assert len(index.assets) == 2

    cache_file = tmp_path / "cache.json"
    index.save_cache(str(cache_file))
    assert os.path.exists(cache_file)

    new_index = SemanticIndex()
    loaded = new_index.load_cache(str(cache_file))
    assert loaded is True
    assert len(new_index.assets) == 2


def test_clip_resolver_with_prefs():
    index = SemanticIndex()
    index.add_asset(MediaAsset("clip_snow.mp4", duration_sec=10.0, tags=["snow"]))
    index.add_asset(MediaAsset("clip_chain.mp4", duration_sec=10.0, tags=["gold_chains"]))

    prefs = UserPreferenceProfile(liked_tags=["gold_chains"], disliked_tags=["boring"])
    resolver = ClipResolver(index, user_prefs=prefs)

    edl = EditDecisionList(
        track_path="track.mp3",
        total_duration_sec=10.0,
        bpm=120.0,
        style_name="alpine_drill_comedy",
        segments=[
            TimelineSegment(1, 0.0, 5.0, 5.0, "verse", 0.5, "hard_cut", "on_beat", query_tags=["snow"]),
            TimelineSegment(2, 5.0, 10.0, 5.0, "chorus", 0.9, "zoom_push", "on_drop", query_tags=["gold_chains"]),
        ]
    )

    resolved_edl = resolver.resolve_edl(edl)

    assert resolved_edl.segments[0].assigned_clip_path == "clip_snow.mp4"
    assert resolved_edl.segments[1].assigned_clip_path == "clip_chain.mp4"
    assert resolved_edl.segments[0].clip_out_sec > 0
