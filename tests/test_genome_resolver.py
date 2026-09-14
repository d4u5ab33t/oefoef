"""
test_genome_resolver.py — Tests for v0.5 Genome Resolver components.
"""
import pytest
from genome_engine.compiler.timeline import EditDecisionList, TimelineSegment
from genome_engine.resolver.semantic_index import SemanticIndex, MediaAsset
from genome_engine.resolver.clip_resolver import ClipResolver


def test_semantic_index_search():
    index = SemanticIndex()
    index.add_asset(MediaAsset("clip1.mp4", tags=["snow", "zugspitze"]))
    index.add_asset(MediaAsset("clip2.mp4", tags=["gold_chains", "moshpit"]))

    results = index.search_by_tags(["snow"])
    assert len(results) >= 1
    assert results[0].clip_path == "clip1.mp4"


def test_clip_resolver():
    index = SemanticIndex()
    index.add_asset(MediaAsset("clip_snow.mp4", tags=["snow"]))
    index.add_asset(MediaAsset("clip_chain.mp4", tags=["gold_chains"]))

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

    resolver = ClipResolver(index)
    resolved_edl = resolver.resolve_edl(edl)

    assert resolved_edl.segments[0].assigned_clip_path == "clip_snow.mp4"
    assert resolved_edl.segments[1].assigned_clip_path == "clip_chain.mp4"
