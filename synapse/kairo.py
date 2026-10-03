"""KAIRO - The Sound Architect (Production / Stems).

Verantwortung laut Konzept:
- Track-Produktion (Beats, Arrangement, Sounddesign)
- Liefert Stems (Drums, Bass, Vocals, Instrumental) statt nur Stereo-Mix
- Markiert automatisch Hook- und Drop-Timecodes
- Reagiert auf Viral-Score-Daten aus dem Hive-Mind
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hive_io import audit, load_hive, save_hive

NODE_NAME = "KAIRO"


def produce_stems(track_path: Path, output_dir: Path) -> dict[str, Any]:
    """Erzeugt Stems aus einem MP3/Projekt-File.

    TODO: real impl
      - echte Stem-Separation (z.B. Demucs / Spleeter)
      - Hook/Drop-Erkennung ueber Essentia oder librosa
      - Marker-Datei (.edl.json) wie in main.py
    Aktuell: Stub, schreibt Track-Metadaten in die Hive-Mind.
    """
    if not track_path.exists():
        raise FileNotFoundError(f"Track nicht gefunden: {track_path}")

    hive = load_hive()
    track_id = track_path.stem
    entry = {
        "title": track_path.stem,
        "artist": "Unknown Artist",
        "path": str(track_path.resolve()),
        "bpm": None,
        "key": None,
        "sections": [],
        "stem_paths": {},  # TODO: echte Stems
        "status": "stub_produced",
        "produced_at": datetime.now(timezone.utc).isoformat(),
    }
    hive["tracks"][track_id] = entry
    save_hive(hive)
    audit(NODE_NAME, "produce_stems", {"track_id": track_id, "path": str(track_path)})
    return entry


def get_stems(track_id: str) -> dict[str, Any]:
    """Gibt Stems eines Tracks zurueck (von VEGA / JINX aufgerufen)."""
    hive = load_hive()
    return hive["tracks"].get(track_id, {}).get("stem_paths", {})
