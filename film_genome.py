"""Declarative Film Genome AST and deterministic constraint resolver."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FrameAST:
    zoom: float = 1.0
    pan: float = 0.0
    crop: str = "fit"
    lut: str = "neutral"
    grain: float = 0.0
    subtitle: str | None = None


@dataclass(frozen=True)
class ShotAST:
    duration_sec: float
    camera: str = "hold"
    energy: float = 0.5
    transition: str = "cut"
    required_tags: tuple[str, ...] = ()
    frame: FrameAST = field(default_factory=FrameAST)
    clip_path: str | None = None


@dataclass(frozen=True)
class SceneAST:
    name: str
    required_tags: tuple[str, ...] = ()
    emotion: str = "neutral"
    color: str = "neutral"
    energy: float = 0.5
    shots: tuple[ShotAST, ...] = ()


@dataclass(frozen=True)
class EmotionAST:
    section: str
    value: str
    intensity: float


@dataclass(frozen=True)
class ThemeAST:
    name: str
    tags: tuple[str, ...] = ()
    emotions: tuple[str, ...] = ()


@dataclass(frozen=True)
class FilmGenome:
    idea: str
    themes: tuple[ThemeAST, ...] = ()
    emotion_curve: tuple[EmotionAST, ...] = ()
    scenes: tuple[SceneAST, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _emotion_for_section(label: str) -> str:
    return {"low": "reflection", "mid": "expectation", "high": "release"}.get(label, "neutral")


def compile_film_genome(song_tags: list[str], sections: list,
                        timeline: list, style) -> FilmGenome:
    """Compiles existing analysis and resolved shots into a serializable AST."""
    tags = tuple(dict.fromkeys(song_tags or ()))
    theme_name = tags[0] if tags else "freedom"
    theme = ThemeAST(theme_name, tags=tags, emotions=("hope", "confidence"))
    emotion_curve = tuple(
        EmotionAST(label, _emotion_for_section(label),
                   0.35 if label == "low" else 0.65 if label == "mid" else 0.95)
        for _, _, label in sections
    )

    scenes = []
    for index, (start, end, label) in enumerate(sections, 1):
        scene_shots = []
        for segment in timeline:
            if segment.start_sec < end and segment.end_sec > start:
                scene_shots.append(ShotAST(
                    duration_sec=round(segment.end_sec - segment.start_sec, 4),
                    camera=segment.camera,
                    energy=round(segment.target_energy, 4),
                    transition=segment.transition,
                    required_tags=tags,
                    frame=FrameAST(lut=segment.color),
                    clip_path=segment.clip_path,
                ))
        scenes.append(SceneAST(
            name=f"scene_{index}_{label}", required_tags=tags,
            emotion=_emotion_for_section(label),
            color=style.color if style else "neutral",
            energy=0.35 if label == "low" else 0.65 if label == "mid" else 0.95,
            shots=tuple(scene_shots),
        ))

    return FilmGenome(
        idea= "; ".join(str(t) for t in tags) if tags else "deterministic music film",
        themes=(theme,), emotion_curve=emotion_curve, scenes=tuple(scenes),
        constraints={
            "deterministic": True,
            "no_repeat_window": "resolver policy",
            "renderer_contract": ["clip", "trim", "camera", "fx", "transition"],
        },
    )


# TOTE FUNKTIONEN ENTFERNT (Deep-Wiring-Audit): _cosine_similarity() und
# resolve_clip_constraints() bildeten einen kompletten, eigenständigen
# Clip-Scoring-Pfad (Tag-Overlap + Vektor-Similarity + Energie-Match ->
# sortierte Kandidatenliste) -- aber KEIN Aufrufer in der gesamten Pipeline
# hat sie je verwendet. Die tatsächlich aktive Clip-Auswahl läuft
# ausschließlich über timeline_builder._pick_clip() (eigene, unabhängig
# weiterentwickelte Scoring-Logik inkl. Anti-Repeat/Cooldown/User-Prefs, die
# resolve_clip_constraints() nie kannte). Dieser Codepfad war also nicht nur
# unbenutzt, sondern inzwischen auch inhaltlich veraltet (fehlende Anti-
# Repeat-/Cooldown-/Story-Cluster-Logik) -- ein "Wieder-Verdrahten" hätte die
# Clip-Auswahl gegenüber dem aktuellen Stand sogar verschlechtert. Ersatzlos
# entfernt statt reaktiviert.
