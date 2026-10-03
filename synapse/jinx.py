"""JINX - The Viral Alchemist (Visuals / Social Media).

Verantwortung laut Konzept:
- Erzeugt N Short-Form-Cuts pro Track (TikTok/Reels/Shorts)
- Hook-/Drop-Snippets markieren, Viral-Score vorhersagen
- Autonomes Posting auf Plattformen
- UGC-Aufforderungen generieren

WICHTIG: Echtes Auto-Posting erfordert:
  - TikTok Display API oder Business-Creator-Account + OAuth2
  - Instagram Graph API (Business-Account)
  - YouTube Data API (OAuth2 + Quota)
  -> Diese Credentials werden NICHT in diesem Repo gespeichert.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hive_io import audit, load_hive, save_hive

NODE_NAME = "JINX"


def generate_cuts(track_id: str, clip_pool_dir: Path,
                  n_cuts: int = 30) -> list[dict[str, Any]]:
    """Plant N Short-Form-Cuts fuer einen Track.

    TODO: real impl
      - ruft deine bestehende main.py-Pipeline (CLAW2-Engine) auf
        ueber subprocess.call(["python", "../main.py", "--song", ...,
        "--limit", "1", "--output-dir", ...])
      - Clip-Matching ueber clip_pool.py
      - Beat-Sync ueber audio_analysis.py
    Aktuell: Stub, schreibt Cut-Plan in Hive-Mind.
    """
    if not clip_pool_dir.exists():
        raise FileNotFoundError(f"Clip-Pool nicht gefunden: {clip_pool_dir}")

    hive = load_hive()
    cuts: list[dict[str, Any]] = []
    for i in range(1, n_cuts + 1):
        cuts.append({
            "clip_id": f"{track_id}_cut_{i:02d}",
            "cut_id": i,
            "platform": "tiktok",  # spaeter: tiktok|reels|shorts
            "hook_pts": [],        # TODO: aus audio_analysis ableiten
            "viral_score": None,   # TODO: predictor trainieren (Phase 6)
            "posted_at": None,
            "views": 0,
            "retention_pct": None,
        })
    hive["visuals"][track_id] = cuts
    save_hive(hive)
    audit(NODE_NAME, "generate_cuts",
          {"track_id": track_id, "n_cuts": n_cuts, "clip_pool": str(clip_pool_dir)})
    return cuts


def post_cuts(cut_ids: list[str]) -> dict[str, Any]:
    """Plant das Posten - fuehrt es NICHT selbst aus.

    Echtes Posting muss ueber die jeweilige Plattform-API laufen.
    Diese Funktion gibt einen Schedule-Plan zurueck, den ein
    Cronjob oder ein Mensch dann ausfuehrt.
    """
    schedule: dict[str, Any] = {"queue": [], "errors": []}
    for cid in cut_ids:
        schedule["queue"].append({
            "cut_id": cid,
            "scheduled_for": None,  # TODO: 7-Tage-Verteilung
            "requires_human_action": True,
            "reason": "Plattform-API-Credentials erforderlich",
        })
    audit(NODE_NAME, "post_cuts_plan", {"n_cuts": len(cut_ids)})
    return schedule
