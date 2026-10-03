from typing import List, Dict
from core.ir import ShotIntent, ResolverResult, BanditDecision, RenderIR, SongAST, ReplayLog
from datetime import datetime

class BeatAlignmentPass:
    def run(self, intent, candidate, current_ir: RenderIR, song_ast: SongAST) -> RenderIR:
        snapped_in = (current_ir.trim_in_ms // 500) * 500
        return current_ir.model_copy(update={"trim_in_ms": snapped_in, "metadata": {**current_ir.metadata, "pass": "beat"}})

class CameraContinuityPass:
    def run(self, intent, candidate, current_ir: RenderIR, prev_shots: List[RenderIR]) -> RenderIR:
        transform = {"zoom": 1.0, "x": 0, "y": 0}
        if prev_shots and intent.continue_from_shot_id:
            last = prev_shots[-1]
            if last.camera_transform:
                transform["zoom"] = last.camera_transform.get("zoom", 1.0) * 1.05
        return current_ir.model_copy(update={"camera_transform": transform})

class OptimizerPipeline:
    def __init__(self, song_ast: SongAST):
        self.song_ast = song_ast
        self.passes = [BeatAlignmentPass(), CameraContinuityPass()]
        self.replay_logs = []

    def optimize_all(self, intents: List[ShotIntent], resolver_results: Dict, bandit_decisions: Dict, initial_irs: Dict) -> List[RenderIR]:
        timeline, prev_shots = [], []
        for intent in intents:
            ir = initial_irs[intent.id]
            applied = []
            for p in self.passes:
                if isinstance(p, BeatAlignmentPass):
                    ir = p.run(intent, bandit_decisions[intent.id].chosen_candidate, ir, self.song_ast)
                else:
                    ir = p.run(intent, bandit_decisions[intent.id].chosen_candidate, ir, prev_shots)
                applied.append(p.__class__.__name__)
            timeline.append(ir)
            prev_shots.append(ir)
            self.replay_logs.append(ReplayLog(
                shot_id=intent.id, timestamp=datetime.utcnow(), intent=intent,
                resolver_result=resolver_results[intent.id], bandit_decision=bandit_decisions[intent.id],
                final_reward=bandit_decisions[intent.id].reward_prediction, optimizer_passes_applied=applied
            ))
        return timeline
