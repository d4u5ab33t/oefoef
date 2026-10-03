# core/models.py
from pydantic import BaseModel, Field
from typing import Literal, List

class BeatNode(BaseModel):
    timestamp: float
    energy: float
    is_downbeat: bool

class PhraseNode(BaseModel):
    id: str
    start_time: float
    end_time: float
    beats: List[BeatNode]
    dominant_emotion: str

class SectionNode(BaseModel):
    id: str
    type: str
    start_time: float
    end_time: float
    phrases: List[PhraseNode]
    energy_level: float

class SongAST(BaseModel):
    id: str
    duration: float
    bpm: float
    sections: List[SectionNode]