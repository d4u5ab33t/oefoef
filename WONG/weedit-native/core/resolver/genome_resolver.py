import sqlite3
import json
from pathlib import Path
from typing import List
from core.ir import ShotIntent, ClipDNA, ResolverResult, ResolverCandidate

class GenomeResolver:
    def __init__(self, clip_dna_list: List[ClipDNA], db_path: Path = Path(".weed_cache/genome.db")):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(self.db_path))

    def resolve(self, intent: ShotIntent, top_k: int = 50) -> ResolverResult:
        cursor = self.conn.execute("SELECT * FROM clips")
        rows = cursor.fetchall()
        candidates = []
        for row in rows:
            cid, fpath, entropy, cam, genes, dur = row
            genes_list = json.loads(genes)
            score = 0.5
            if intent.need_energy > 0.7 and entropy > 0.6: score += 0.3
            if intent.need_camera.movement in cam or cam == "handheld": score += 0.2
            if any(g in genes_list for g in intent.need_color): score += 0.2
            candidates.append(ResolverCandidate(
                clip_dna_id=cid, trim_start_ms=0, trim_end_ms=min(dur, intent.end_ms - intent.start_ms),
                constraint_match_score=min(1.0, score), semantic_similarity=0.7
            ))
        candidates.sort(key=lambda x: x.constraint_match_score, reverse=True)
        return ResolverResult(intent_id=intent.id, candidates=candidates[:top_k], query_constraints={})
