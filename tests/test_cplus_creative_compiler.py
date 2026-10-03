from pathlib import Path
import pytest
from creative_compiler import (
    SongIR, SceneIR, SelfLearningKernel, OptimizerKernel,
    CreativeCompilerOS, compile_creative_ir
)


def test_song_and_scene_ir():
    song = SongIR(
        song_id="test_song_01",
        title="BeatSync Anthem",
        artist="Oi.Da",
        bpm=140.0,
        duration_sec=120.0,
        beat_graph=[0.0, 0.43, 0.86],
        energy_levels=[0.3, 0.8, 0.5],
        emotion_tags=["Aggressive", "Cyberpunk"],
    )
    assert song.bpm == 140.0
    d = song.to_dict()
    assert d["title"] == "BeatSync Anthem"

    scene = SceneIR(
        scene_id="scene_001",
        intent="Cinematic Dynamic",
        director_style="cunningham",
        shot_list=[{"clip": "c1.mp4", "energy": 0.8}],
        total_duration_sec=120.0,
        average_energy=0.53,
        cuts_per_minute=25.0,
    )
    assert scene.director_style == "cunningham"
    assert len(scene.shot_list) == 1


def test_self_learning_kernel_sqlite(tmp_path):
    db_file = tmp_path / "test_exp.db"
    kernel = SelfLearningKernel(db_path=db_file)
    try:
        kernel.save_experience({
            "episode": 1,
            "song_hash": "song_abc",
            "clip_id": "clip_winner.mp4",
            "energy": 0.8,
            "sync_score": 0.9,
            "flow_score": 0.9,
            "duplicate_penalty": 0.0,
            "reward": 0.95,
            "metadata": {"director": "cunningham"}
        })

        best = kernel.get_best_clip("song_abc", energy=0.82)
        assert best == "clip_winner.mp4"

        stats = kernel.get_stats()
        assert stats["total_experiences"] == 1
        assert stats["avg_reward"] == 0.95
    finally:
        kernel.close()


def test_creative_compiler_pipeline_bridge(tmp_path):
    class MockSong:
        path = "J:/fake/track.mp3"
        title = "Track 1"
        artist = "Oida"
        tag_vector = {"trap": 0.8}

    class MockAudio:
        bpm = 135.0
        duration_sec = 60.0
        beat_times = [0.0, 0.5, 1.0, 1.5]
        sections = [(0.0, 30.0, "low"), (30.0, 60.0, "high")]
        energy = [0.2, 0.3, 0.8, 0.9]
        mc_gender = "female"

    class MockSegment:
        def __init__(self, start, end, clip):
            self.start_sec = start
            self.end_sec = end
            self.clip_path = clip
            self.target_energy = 0.8
            self.cut_style = "hard_cut"
            self.rhythm_pattern = "steady"
            self.sync_type = "on_beat"
            self.speed_factor = 1.0
            self.on_structure_boundary = False
            self.section_label = "high"
            self.theme = "cyberpunk"

    class MockStyle:
        name = "cunningham"

    timeline = [MockSegment(0.0, 2.0, "c1.mp4"), MockSegment(2.0, 4.0, "c2.mp4")]
    db_file = tmp_path / "test_exp_bridge.db"

    manifest = compile_creative_ir(
        song=MockSong(),
        audio=MockAudio(),
        timeline=timeline,
        style=MockStyle(),
        semantics={"mood_tags": ["drill", "bass"]},
        db_path=db_file,
    )

    assert "song_ir" in manifest
    assert "scene_ir" in manifest
    assert "self_critic" in manifest
    assert manifest["self_critic"]["quality_score"] > 0.0
    assert manifest["kernel_stats"]["total_experiences"] >= 2
