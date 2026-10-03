import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "viral-strategy.py"

spec = importlib.util.spec_from_file_location("viral_strategy", MODULE_PATH)
viral_strategy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viral_strategy)


def test_snapshot_command_generates_report(tmp_path, monkeypatch):
    output_path = tmp_path / "snapshot.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "viral-strategy.py",
            "snapshot",
            "--artist",
            "Oida",
            "--track",
            "Beat Runner",
            "--release",
            "R-42",
            "--label",
            "oidasheim",
            "--platform",
            "tiktok",
            "--output",
            str(output_path),
        ],
    )

    viral_strategy.main()

    assert output_path.exists(), "snapshot output should be written to disk"
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["artist"] == "Oida"
    assert data["track"] == "Beat Runner"
    assert data["release"] == "R-42"
    assert data["platforms"]["tiktok"]["best_time"] == "19:00"
    assert data["niche"] == "hiphop"
    assert any("#deutschrap" in tag or "#hiphop" in tag for tag in data["hashtags"]["nische"])


def test_hiphop_mood_niche_mapping():
    niche = viral_strategy._niche_for_mood(["aggressive", "boom bap", "808"])
    assert niche == "hiphop"

    niche_fallback = viral_strategy._niche_for_mood([], fallback="hiphop")
    assert niche_fallback == "hiphop"


def test_learn_default_niche_from_catalog():
    semantics = [
        {"mood_tags": ["trap", "aggressive", "drill"]},
        {"mood_tags": ["boom-bap", "rap"]},
        {"mood_tags": ["techno", "modular"]},
    ]
    learned = viral_strategy.learn_default_niche(semantics)
    assert learned == "hiphop"

    # Leerer Katalog fällt auf DEFAULT_HASHTAG_NICHE ('hiphop') zurück
    empty_learned = viral_strategy.learn_default_niche([])
    assert empty_learned == "hiphop"

