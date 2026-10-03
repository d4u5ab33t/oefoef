from __future__ import annotations
from uuid import uuid4
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict

class GenomeAsset(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    version: str = "1.0.0"
    genes: List[str] = Field(default_factory=list)
    reward: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    history: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

class BeatAST(GenomeAsset):
    type: Literal["beat"] = "beat"
    time_ms: int
    is_downbeat: bool
    energy: float = Field(ge=0.0, le=1.0)

class PhraseAST(GenomeAsset):
    type: Literal["phrase"] = "phrase"
    start_ms: int
    end_ms: int
    beats: List[BeatAST]
    dominant_emotion: str
    energy_curve: List[float]

class SectionAST(GenomeAsset):
    type: Literal["section"] = "section"
    name: str
    start_ms: int
    end_ms: int
    phrases: List[PhraseAST]
    bpm: float
    dynamic_range: float

class SongAST(GenomeAsset):
    type: Literal["song"] = "song"
    title: str
    artist: str
    total_duration_ms: int
    sections: List[SectionAST]
    global_energy_curve: List[float]
    global_emotion_curve: List[float]

class CameraIntent(BaseModel):
    movement: str
    framing: str
    persistence_id: str

class ShotIntent(GenomeAsset):
    type: Literal["shot_intent"] = "shot_intent"
    song_section: str
    phrase_id: str
    start_ms: int
    end_ms: int
    need_energy: float = Field(ge=0.0, le=1.0)
    need_emotion: List[str]
    need_color: List[str]
    need_camera: CameraIntent
    need_rhythm: str
    continue_from_shot_id: Optional[str] = None

class ClipDNA(GenomeAsset):
    type: Literal["clip_dna"] = "clip_dna"
    file_path: str
    duration_ms: int
    motion_entropy: float
    dominant_colors: List[str]
    detected_objects: List[str]
    detected_faces: int
    camera_motion: str
    lighting: str
    embedding_vector_id: str

class ResolverCandidate(BaseModel):
    clip_dna_id: str
    trim_start_ms: int
    trim_end_ms: int
    constraint_match_score: float
    semantic_similarity: float

class ResolverResult(BaseModel):
    intent_id: str
    candidates: List[ResolverCandidate]
    query_constraints: Dict[str, Any]

class BanditDecision(BaseModel):
    intent_id: str
    chosen_candidate: ResolverCandidate
    rejected_candidates_count: int
    reward_prediction: float
    decision_reason: str

class ReplayLog(GenomeAsset):
    type: Literal["replay_log"] = "replay_log"
    shot_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intent: ShotIntent
    resolver_result: ResolverResult
    bandit_decision: BanditDecision
    final_reward: float
    optimizer_passes_applied: List[str]

class RenderIR(GenomeAsset):
    model_config = ConfigDict(frozen=True)
    type: Literal["render_ir"] = "render_ir"
    clip_file_path: str
    trim_in_ms: int
    trim_out_ms: int
    speed_multiplier: float = 1.0
    discard_clip_audio: bool = True
    main_audio_track_id: str
    camera_transform: Optional[Dict[str, float]] = None
    transition_in: Optional[str] = None
    transition_out: Optional[str] = None
    lut_file: Optional[str] = None
    fx_chain: List[str] = Field(default_factory=list)
    source_intent_id: str
    replay_log_id: str
