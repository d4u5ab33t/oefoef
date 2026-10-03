import random
from core.ir import ShotIntent, ResolverResult, BanditDecision, SongAST, RenderIR
from typing import List

class RLBandit:
    def choose(self, intent: ShotIntent, resolver_result: ResolverResult, song_ast: SongAST, prev_shots: List[RenderIR]) -> BanditDecision:
        candidates = resolver_result.candidates
        if not candidates: raise ValueError("No candidates")
        best = max(candidates, key=lambda c: c.constraint_match_score + random.uniform(0, 0.1))
        reward = best.constraint_match_score * 0.7 + best.semantic_similarity * 0.3
        return BanditDecision(
            intent_id=intent.id, chosen_candidate=best, rejected_candidates_count=len(candidates)-1,
            reward_prediction=reward, decision_reason=f"Maximized constraint match ({best.constraint_match_score:.2f})"
        )
