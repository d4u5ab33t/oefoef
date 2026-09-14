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
