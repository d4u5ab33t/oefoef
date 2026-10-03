"""ATLAS - The Resource Guardian (Buchhaltung / ROI / Splits).

Verantwortung laut Konzept:
- Revenue-Splits (Artist / Label / Producer / Promo / Creator)
- Reinvestitions-Strategie
- Ad-Budget-Freigabe basierend auf Viral-Score
- Risk-Management (Track-Sperrungen etc.)

WICHTIG:
  - Smart-Contract-Splits erfordern eine Blockchain-Wallet, Gas-Budget
    und eine gewaehlte Chain. Standardvorschlag: Polygon (guenstig).
  - Bis dahin: klassische CSV-/Buchhaltung als Fallback.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hive_io import audit, load_hive, save_hive

NODE_NAME = "ATLAS"

# Default-Split gemaess Konzept (sum = 1.00)
DEFAULT_SPLIT = {
    "artist":      0.40,
    "label":       0.20,
    "producer":    0.15,
    "promo":       0.15,
    "syndicate":   0.10,
}


def record_revenue(track_id: str, platform: str, amount_eur: float) -> dict[str, Any]:
    """Verbucht eine Einnahme und berechnet den Split.

    TODO: real impl
      - Hook an DistroKid / LabelGrid / The Orchard APIs
      - Smart-Contract-Aufruf statt nur lokalem Eintrag
    """
    hive = load_hive()
    stream_id = f"{track_id}_{platform}_{int(datetime.now(timezone.utc).timestamp())}"
    splits = {k: round(amount_eur * v, 2) for k, v in DEFAULT_SPLIT.items()}

    entry = {
        "stream_id": stream_id,
        "track_id": track_id,
        "platform": platform,
        "amount_eur": amount_eur,
        "split_paid": splits,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    hive["revenue"][stream_id] = entry
    save_hive(hive)
    audit(NODE_NAME, "record_revenue",
          {"track_id": track_id, "platform": platform, "amount_eur": amount_eur})
    return entry


def decide_ad_budget(track_id: str, viral_score: float,
                     cap_eur: float = 500.0) -> dict[str, Any]:
    """Entscheidet, ob Ad-Budget freigegeben wird.

    Regel (Stub):
        viral_score >= 8.5 -> cap_eur
        viral_score >= 7.0 -> cap_eur / 2
        sonst              -> 0
    """
    if viral_score >= 8.5:
        amount = cap_eur
    elif viral_score >= 7.0:
        amount = cap_eur / 2
    else:
        amount = 0.0

    decision = {
        "track_id": track_id,
        "viral_score": viral_score,
        "approved_eur": amount,
        "decision_at": datetime.now(timezone.utc).isoformat(),
        "requires_human_action": True,  # Meta/TikTok-Ads: manuell
        "reason": "Ad-Spend laeuft ueber Business-Account, manuelle Freigabe noetig",
    }
    audit(NODE_NAME, "decide_ad_budget", decision)
    return decision
