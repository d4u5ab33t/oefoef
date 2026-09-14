"""
test_auto_learning.py — Tests for v0.9 Auto-Learning Genome components.
"""
import pytest
from genome_engine.genome.schema import VisualGenome
from genome_engine.learning.synapse_loop import AestheticGenomeLearner, VisualAnalysisProfile


def test_aesthetic_genome_learner():
    learner = AestheticGenomeLearner(learning_rate=0.5)
    initial_genome = VisualGenome(style_name="alpine_drill_comedy", target_cuts_per_min=50.0)

    profile = VisualAnalysisProfile(
        avg_shot_duration_sec=0.6,
        detected_cuts_per_min=100.0,
        dominant_colors=["neon_green"],
        motion_intensity=0.9
    )

    updated_genome = learner.adapt_visual_genome(initial_genome, profile)

    assert updated_genome.target_cuts_per_min == 75.0  # 0.5 * 50 + 0.5 * 100
    assert "neon_green" in updated_genome.color_palette
    assert "whip_pan" in updated_genome.camera_motion
