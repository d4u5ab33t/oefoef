"""
test_rl_bandit.py — Tests for v0.6 RL-Bandit components.
"""
import pytest
from genome_engine.rl.bandit import ContextualBandit
from genome_engine.rl.user_preferences import UserPreferenceProfile


def test_user_preference_profile():
    profile = UserPreferenceProfile(liked_tags=["snow", "drill"], disliked_tags=["boring"])
    
    score = profile.get_score_modifier(["snow", "drill", "landscape"])
    assert score == pytest.approx(0.4)

    score_dislike = profile.get_score_modifier(["boring"])
    assert score_dislike == pytest.approx(-0.3)


def test_contextual_bandit():
    bandit = ContextualBandit(epsilon=0.0)  # Pure exploitation for test
    
    # Train arm
    for _ in range(10):
        bandit.update("zoom_push", 0.95)
        bandit.update("hard_cut", 0.2)

    chosen = bandit.select_action()
    assert chosen == "zoom_push"

    decision = bandit.evaluate_decision(beat_precision=0.9, novelty=0.8, flow=0.85)
    assert decision.total_reward > 0.8
    assert decision.chosen_strategy == "zoom_push"
