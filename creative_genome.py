"""
creative_genome.py - deterministic contracts for the Creative Genome compiler.

The compiler deliberately keeps analysis, intent, resolution and rendering
separate. Models may add signals to a genome, but never own final decisions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json


@dataclass(frozen=True)
class StyleSpec:
    name: str = "cinematic"
    parent: str | None = None
    camera: str = "dynamic"
    lighting: str = "natural"
    color: str = "neutral"
    transition: str = "cut"
    fx: tuple[str, ...] = ()
    motion_gain: float = 1.10
    information_target: float = 0.60
    tags: tuple[str, ...] = ()

    def merged(self, parent: "StyleSpec | None") -> "StyleSpec":
        if parent is None:
            return self
        return StyleSpec(
            name=self.name,
            parent=parent.name,
            camera=self.camera if self.camera != "dynamic" else parent.camera,
            lighting=self.lighting if self.lighting != "natural" else parent.lighting,
            color=self.color if self.color != "neutral" else parent.color,
            transition=self.transition if self.transition != "cut" else parent.transition,
            fx=self.fx or parent.fx,
            motion_gain=self.motion_gain if self.motion_gain != 1.10 else parent.motion_gain,
            information_target=(self.information_target
                                if self.information_target != 0.60
                                else parent.information_target),
            tags=self.tags or parent.tags,
        )


BUILTIN_STYLES = {
    "cinematic": StyleSpec(),
    "trap-pack": StyleSpec(
        name="trap-pack", parent="cinematic", camera="push", lighting="lowkey",
        color="warm", transition="whip", fx=("grain",), motion_gain=1.15,
        information_target=0.65, tags=("urban", "night", "action"),
    ),
    "horror-pack": StyleSpec(
        name="horror-pack", parent="cinematic", camera="drift", lighting="lowkey",
        color="desaturated", transition="flash", fx=("grain", "flicker"),
        motion_gain=0.85, information_target=0.42, tags=("dark", "night", "mystery"),
    ),
    "anime-pack": StyleSpec(
        name="anime-pack", parent="cinematic", camera="snap", lighting="highkey",
        color="vivid", transition="cut", fx=("chroma",), motion_gain=1.25,
        information_target=0.75, tags=("action", "vivid", "fast"),
    ),
    "cunningham": StyleSpec(
        name="cunningham", parent="cinematic", camera="snap", lighting="highkey",
        color="desaturated", transition="flash", fx=("chroma", "flicker"), motion_gain=1.35,
        information_target=0.80, tags=("glitch", "cyber", "action", "dark"),
    ),
    "gondry": StyleSpec(
        name="gondry", parent="cinematic", camera="focus_zoom", lighting="natural",
        color="warm", transition="whip", fx=("grain",), motion_gain=1.10,
        information_target=0.65, tags=("urban", "vivid", "psych"),
    ),
    "hype_williams": StyleSpec(
        name="hype_williams", parent="cinematic", camera="push", lighting="lowkey",
        color="vivid", transition="slide", fx=("grain",), motion_gain=1.25,
        information_target=0.75, tags=("night", "urban", "street", "bavarian"),
    ),
    "jonze": StyleSpec(
        name="jonze", parent="cinematic", camera="drift", lighting="natural",
        color="neutral", transition="cut", fx=(), motion_gain=0.95,
        information_target=0.55, tags=("nature", "urban", "chill"),
    ),
    "oida_raw": StyleSpec(
        name="oida_raw", parent="cinematic", camera="snap", lighting="lowkey",
        color="desaturated", transition="slide", fx=("grain", "flicker"), motion_gain=1.20,
        information_target=0.70, tags=("street", "089", "beton", "oida", "weed"),
    ),
    "oida-pack": StyleSpec(
        name="oida-pack", parent="trap-pack", camera="snap", lighting="lowkey",
        color="desaturated", transition="slide", fx=("grain", "flicker"), motion_gain=1.20,
        information_target=0.60, tags=("night", "urban", "dark", "aggressive", "melancholic", "fog", "street", "089"),
    ),
}


def compile_style(name: str = "cinematic", package_dir: Path | None = None) -> StyleSpec:
    """Load a local JSON package, falling back to deterministic built-ins."""
    raw = None
    if package_dir:
        candidate = package_dir / f"{name}.json"
        if candidate.exists():
            raw = json.loads(candidate.read_text(encoding="utf-8"))
    if raw is None:
        return resolve_style(BUILTIN_STYLES.get(name, BUILTIN_STYLES["cinematic"]))

    allowed = {field_name for field_name in StyleSpec.__dataclass_fields__}
    values = {k: v for k, v in raw.items() if k in allowed}
    for key in ("fx", "tags"):
        if key in values and isinstance(values[key], list):
            values[key] = tuple(values[key])

    values.setdefault("name", name)
    return resolve_style(StyleSpec(**values))


def resolve_style(style: StyleSpec, seen: set[str] | None = None) -> StyleSpec:
    seen = seen or set()
    if style.name in seen:
        raise ValueError(f"Style inheritance cycle at {style.name}")
    if not style.parent:
        return style
    parent = BUILTIN_STYLES.get(style.parent)
    if parent is None:
        raise ValueError(f"Unknown parent style: {style.parent}")
    return style.merged(resolve_style(parent, seen | {style.name}))


@dataclass(frozen=True)
class DirectorIntent:
    section: str
    theme: str
    target_energy: float
    target_information: float
    camera: str
    lighting: str
    color: str
    transition: str
    required_tags: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass
class FilmDNA:
    themes: list[str] = field(default_factory=list)
    emotions: list[str] = field(default_factory=list)
    cameras: list[str] = field(default_factory=list)
    motions: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    rhythm: float = 0.0
    surprise: float = 0.0
    continuity: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def emotion_for_energy(value: float) -> str:
    if value < 0.25:
        return "tension"
    if value < 0.5:
        return "expectation"
    if value < 0.75:
        return "confidence"
    return "release"


def build_intent(section: str, energy: float, style: StyleSpec,
                song_tags: list[str]) -> DirectorIntent:
    # Theme-Auswahl, in Prioritätsreihenfolge:
    #   1. ein Song-Tag, das auch im Style-Vokabular vorkommt (inhaltlicher
    #      UND stilistischer Treffer, z.B. Mood-Tag "night" bei trap-pack).
    #   2. sonst irgendein bekanntes Song-Tag (z.B. Mood-/Slang-Tag aus
    #      song_semantics.py) — immer noch aussagekräftiger als der pauschale
    #      "freedom"-Default, auch wenn es nicht im Style-Vokabular steht.
    #   3. nur wenn wirklich keine Song-Tags vorliegen (song_tags == []),
    #      bleibt der alte Default "freedom" -> Aufrufer ohne song_tags
    #      (ältere main.py-Version, Tests) verhalten sich exakt wie vorher.
    theme = (next((tag for tag in song_tags if tag in style.tags), None)
             or (song_tags[0] if song_tags else "freedom"))
    label = "high" if energy >= 0.66 else "low" if energy < 0.33 else "mid"
    return DirectorIntent(
        section=section,
        theme=theme,
        target_energy=max(0.0, min(1.0, energy * style.motion_gain)),
        target_information=style.information_target,
        camera=style.camera,
        lighting=style.lighting,
        color=style.color,
        transition=style.transition if label == "high" else "cut",
        required_tags=tuple(style.tags),
        confidence=0.65 if song_tags else 0.35,
    )


def information_density(meta: dict) -> float:
    signals = sum(bool(meta.get(key)) for key in ("tags", "objects", "ocr", "faces"))
    motion = float(meta.get("motion_score", 0.0))
    entropy = float(meta.get("entropy", motion))
    return min(1.0, 0.15 * signals + 0.45 * motion + 0.4 * entropy)


def _cosine_similarity(vec_a, vec_b) -> float:
    """Cosine-Similarity zwischen zwei numerischen Tag-Vektoren (Listen/Tupel
    gleicher Bedeutung, z.B. beide über TAG_VOCAB indiziert wie in
    mp3_scanner.build_tag_vector / clip_pool.analyze_clip). Liefert 0.0 bei
    leeren/fehlenden Vektoren statt eines Fehlers, kein numpy-Import nötig."""
    if not vec_a or not vec_b:
        return 0.0
    n = min(len(vec_a), len(vec_b))
    if n == 0:
        return 0.0
    # BUGFIX (Deep-Wiring-Audit Teil 4): dieselbe Cosine-Similarity-Funktion
    # existiert unabhängig noch zweimal (timeline_builder.py::_cosine(),
    # semantic_matching.py::cosine_similarity()) -- alle drei litten am
    # selben Fehler: dot() wurde auf n=min(len(a),len(b)) gekürzt (TAG_VOCAB
    # wächst inkrementell, gecachte Clip-Vektoren im Globe können daher
    # kürzer sein als der aktuelle song_vector), aber norm_a/norm_b liefen
    # über die VOLLEN, ungekürzten Vektoren -- inkonsistent mit dot() und
    # drückte den Score für jeden Clip mit kürzerem Cache-Vektor systematisch
    # nach unten. Hier zusätzlich sicherheitshalber gefixt, da score_candidate()
    # dasselbe song_vector<->meta["vector"]-Längen-Mismatch-Risiko hat.
    vec_a, vec_b = vec_a[:n], vec_b[:n]
    dot = sum(vec_a[i] * vec_b[i] for i in range(n))
    norm_a = sum(v * v for v in vec_a) ** 0.5
    norm_b = sum(v * v for v in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


def score_candidate(meta: dict, intent: DirectorIntent, previous: dict | None = None,
                    song_vector: list | None = None) -> float:
    tags = set(meta.get("tags", []))
    tag_overlap_score = len(tags & set(intent.required_tags)) / max(1, len(intent.required_tags))
    # Vector-Logic-Upgrade: `required_tags` sind nur die groben Style-Tags
    # (z.B. "urban","night") - trifft ein Clip keinen davon exakt, war
    # tag_score bisher immer 0, selbst wenn er dem Song inhaltlich sehr nahe
    # ist. Ist ein song_vector verfügbar, wird die echte, viel granularere
    # Cosine-Similarity (Song-Tag-Vektor <-> Clip-Vektor) zur Hälfte mit
    # eingerechnet, statt sich rein auf den binären Style-Tag-Treffer zu
    # verlassen. Ohne song_vector (Aufrufer, die das Argument nicht kennen)
    # bleibt exakt das alte Verhalten erhalten.
    if song_vector:
        vector_sim = (_cosine_similarity(song_vector, meta.get("vector", [])) + 1.0) / 2.0
        tag_score = 0.5 * tag_overlap_score + 0.5 * vector_sim
    else:
        tag_score = tag_overlap_score
    motion = float(meta.get("motion_score", 0.5))
    energy_score = 1.0 - abs(motion - intent.target_energy)
    density_score = 1.0 - abs(information_density(meta) - intent.target_information)
    continuity = 0.5
    if previous is not None:
        continuity = 1.0 - min(1.0, abs(motion - float(previous.get("motion_score", motion))))
    return 0.40 * energy_score + 0.25 * tag_score + 0.20 * density_score + 0.15 * continuity


def update_film_dna(dna: FilmDNA, intent: DirectorIntent, meta: dict) -> None:
    for attr, value in (("themes", intent.theme), ("emotions", emotion_for_energy(intent.target_energy)),
                        ("cameras", intent.camera), ("colors", intent.color)):
        values = getattr(dna, attr)
        if value and value not in values:
            values.append(value)
    motion = float(meta.get("motion_score", 0.0))
    dna.motions.append("high" if motion >= 0.66 else "low" if motion < 0.33 else "mid")
    dna.rhythm = (dna.rhythm * 0.8) + motion * 0.2
    continuity_signal = max(0.0, 1.0 - abs(motion - intent.target_energy))
    dna.continuity = (dna.continuity * 0.8) + continuity_signal * 0.2
    dna.surprise = (dna.surprise * 0.8) + abs(motion - intent.target_energy) * 0.2


def genome_manifest(song: object, style: StyleSpec, dna: FilmDNA) -> dict:
    return {
        "version": "creative-genome-v1",
        "song": {"path": getattr(song, "path", ""), "bpm": getattr(song, "bpm", 0.0)},
        "style": asdict(style),
        "film_dna": dna.to_dict(),
        "deterministic": True,
        "model_policy": "analysis-only; resolver owns decisions",
    }
