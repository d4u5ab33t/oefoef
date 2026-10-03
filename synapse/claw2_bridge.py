"""claw2_bridge.py - ruft die bestehende Oidasheim-Pipeline auf und
schreibt ihre Outputs in die Hive-Mind.

Designentscheidung:
  Wir importieren main.py NICHT direkt. Stattdessen wird main.py als
  Subprocess aufgerufen mit --dry-run (kein Render noetig fuer Tests).
  Dadurch bleibt main.py unabhaengig, und die Bridge funktioniert
  auch wenn main.py fehlschlaegt (z.B. fehlendes numpy).

Aufruf:
    python claw2_bridge.py <mp3> [--clips DIR] [--style NAME] [--platform NAME] [--n-cuts N]

Output:
  - schreibt Tracks/Masters/Cuts in hive_mind.json
  - schreibt das EDL-JSON aus main.py in synapse/edl/<track_id>.edl.json
  - schreibt das Genome-JSON in synapse/edl/<track_id>.genome.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hive_io import audit, load_hive, save_hive

NODE_NAME = "CLAW2-BRIDGE"
HERE = Path(__file__).parent
PARENT = HERE.parent  # J:/Oidasheim/oefoef/
PYTHON = sys.executable


def run_main_pipeline(mp3: Path, output_dir: Path,
                      style: str = "cinematic",
                      platform: str = "tiktok") -> dict[str, Any]:
    """Ruft main.py --song ... --dry-run auf und sammelt die EDL/Genome-Files.

    Returnt ein Dict mit Pfaden zu den geschriebenen Files + Returncode.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    edl_dir = output_dir
    cmd = [
        PYTHON, str(PARENT / "main.py"),
        "--song", str(mp3),
        "--output-dir", str(edl_dir),
        "--style", style,
        "--platform", platform,
        "--rebuild-globe",
        "--dry-run",
    ]
    print(f"[bridge] $ {' '.join(cmd)}")
    # MP3-Root dynamisch anpassen:
    # Damit mp3_scanner.scan_all_songs() den Track findet, muss
    # OIDASHEIM_MP3_ROOT den Ordner des Tracks enthalten.
    env = os.environ.copy()
    env["OIDASHEIM_ROOT"] = str(PARENT)
    env["OIDASHEIM_CLIP_POOL"] = r"J:\raw_vidz\_DTRFMO_"
    env["OIDASHEIM_MP3_ROOT"] = str(mp3.parent)
    try:
        result = subprocess.run(
            cmd, cwd=str(PARENT), env=env,
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return _bridge_result(-1, error="timeout", stdout="", stderr="")
    except FileNotFoundError as e:
        return _bridge_result(-2, error=str(e))

    return _bridge_result(
        result.returncode, stdout=result.stdout, stderr=result.stderr,
    )


def _bridge_result(returncode: int, *, stdout: str = "",
                   stderr: str = "", error: str | None = None) -> dict[str, Any]:
    """Normalisiert das Run-Ergebnis (immer gleiches Schema)."""
    edl_dir = HERE / "edl"
    edl_paths: list[str] = []
    genome_paths: list[str] = []
    if edl_dir.exists():
        edl_paths = sorted(str(p) for p in edl_dir.glob("*.edl.json"))
        genome_paths = sorted(str(p) for p in edl_dir.glob("*.genome.json"))
    return {
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "error": error,
        "edl_paths": edl_paths,
        "genome_paths": genome_paths,
    }


def ingest_into_hive(mp3: Path, run_result: dict[str, Any]) -> dict[str, Any]:
    """Liest EDL + Genome aus dem Run und schreibt sie in die Hive-Mind."""
    hive = load_hive()
    track_id = mp3.stem
    edl_entry = {
        "title": track_id,
        "artist": "Unknown Artist",
        "path": str(mp3.resolve()),
        "bridge_run_at": datetime.now(timezone.utc).isoformat(),
        "main_returncode": run_result["returncode"],
        "edl_files": run_result["edl_paths"],
        "genome_files": run_result["genome_paths"],
        "status": "ingested" if run_result["returncode"] == 0 else "main_failed",
    }
    # erstes EDL als Vorschau parsen
    if run_result["edl_paths"]:
        try:
            edl = json.loads(Path(run_result["edl_paths"][0]).read_text(encoding="utf-8"))
            edl_entry["edl_summary"] = {
                "segments": len(edl.get("sequence", [])),
                "style": edl.get("style"),
                "platform": edl.get("platform", ""),
            }
        except (OSError, json.JSONDecodeError, KeyError) as e:
            edl_entry["edl_parse_error"] = str(e)

    hive["tracks"][track_id] = edl_entry
    save_hive(hive)
    audit(NODE_NAME, "ingest", {"track_id": track_id,
                                "rc": run_result["returncode"],
                                "n_edl": len(run_result["edl_paths"])})
    return edl_entry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CLAW2-Bridge: main.py -> Hive-Mind")
    p.add_argument("mp3", type=Path, help="Pfad zur MP3-Datei")
    p.add_argument("--clips", type=Path, default=None,
                   help="Clip-Pool-Ordner (nur informativ, main.py nimmt config.py)")
    p.add_argument("--style", default="cinematic")
    p.add_argument("--platform", default="tiktok",
                   choices=("full", "tiktok"))
    p.add_argument("--n-cuts", type=int, default=30,
                   help="Anzahl Cuts in Hive-Mind (Plan, nicht Render)")
    p.add_argument("--edl-dir", type=Path, default=HERE / "edl",
                   help="Wo EDL/Genome-Files abgelegt werden")
    args = p.parse_args(argv)

    if not args.mp3.exists():
        print(f"[bridge] FEHLER: MP3 nicht gefunden: {args.mp3}")
        return 2

    print(f"[bridge] Starte Pipeline fuer: {args.mp3.name}")
    result = run_main_pipeline(args.mp3, args.edl_dir,
                                style=args.style, platform=args.platform)

    print(f"[bridge] main.py returncode = {result['returncode']}")
    if result["stderr"]:
        last = result["stderr"].strip().splitlines()[-5:]
        print("[bridge] stderr (letzte 5 Zeilen):")
        for line in last:
            print(f"    {line}")

    entry = ingest_into_hive(args.mp3, result)
    print(f"[bridge] Hive-Mind aktualisiert: status={entry['status']}, "
          f"edl={len(entry['edl_files'])}, genome={len(entry['genome_files'])}")

    # Nachgelagert: Jinx-Cuts planen (immer, auch wenn main fehlschlaegt)
    import jinx
    cuts = jinx.generate_cuts(args.mp3.stem, args.clips or args.edl_dir,
                              n_cuts=args.n_cuts)
    print(f"[bridge] {len(cuts)} Cuts geplant in Hive-Mind.")

    return 0 if result["returncode"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
