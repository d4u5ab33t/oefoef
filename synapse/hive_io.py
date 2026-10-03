"""Gemeinsamer I/O-Layer fuer alle SYNAPSE-Nodes.

Liest/schreibt die zentrale Hive-Mind-JSON-Datei und fuehrt ein
append-only Audit-Log. Threading-Lock, weil mehrere Nodes parallel
laufen koennen (in spaeteren Phasen).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).parent
HIVE_PATH = _HERE / "hive_mind.json"

_LOCK = threading.Lock()


def _empty_hive() -> dict:
    return {
        "version": "0.1.0",
        "tracks": {},
        "masters": {},
        "visuals": {},
        "creator_db": {},
        "pitch_log": {},
        "revenue": {},
        "fan_db": {},
        "ad_spend": {},
        "audit": [],
    }


def load_hive() -> dict:
    """Laedt die Hive-Mind. Erstellt leere Struktur, wenn Datei fehlt."""
    if not HIVE_PATH.exists():
        hive = _empty_hive()
        save_hive(hive)
        return hive
    with _LOCK:
        with HIVE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)


def save_hive(hive: dict) -> None:
    """Schreibt die Hive-Mind atomar."""
    with _LOCK:
        tmp = HIVE_PATH.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(hive, f, indent=2, ensure_ascii=False)
        tmp.replace(HIVE_PATH)


def audit(actor: str, action: str, payload: dict | None = None) -> None:
    """Haengt einen Eintrag an das Audit-Log."""
    hive = load_hive()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "payload": payload or {},
    }
    hive.setdefault("audit", []).append(entry)
    save_hive(hive)
