import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creative_genome import FilmDNA, compile_style, update_film_dna


def test_compile_style_keeps_requested_name_and_inherits_parent(tmp_path):
    package_dir = tmp_path / "styles"
    package_dir.mkdir()
    (package_dir / "custom.json").write_text(
        json.dumps({
            "parent": "trap-pack",
            "camera": "orbit",
            "fx": ["pulse"],
        }),
        encoding="utf-8",
    )

    style = compile_style("custom", package_dir)

    assert style.name == "custom"
    assert style.parent == "trap-pack"
    assert style.camera == "orbit"
    assert style.lighting == "lowkey"
    assert style.color == "warm"
    assert style.fx == ("pulse",)


def test_update_film_dna_uses_motion_energy_continuity(tmp_path):
    dna = FilmDNA()
    intent = compile_style("cinematic").__class__
    # direct call with a realistic intent
    from creative_genome import DirectorIntent

    intent = DirectorIntent(
        section="chorus",
        theme="freedom",
        target_energy=0.8,
        target_information=0.55,
        camera="push",
        lighting="natural",
        color="warm",
        transition="whip",
        required_tags=("urban",),
        confidence=0.8,
    )

    update_film_dna(dna, intent, {"motion_score": 0.8})

    assert dna.continuity > 0.0
    assert dna.motions
    assert dna.rhythm >= 0.0
