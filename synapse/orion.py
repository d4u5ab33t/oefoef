"""ORION - The Market Navigator (A&R / Promo / Sync).

Verantwortung laut Konzept:
- Playlist-Pitching an Spotify/Apple-Redakteure
- Sync-Licensing an Netflix/Ubisoft/Werbeagenturen
- Regionale Metadata-Optimierung
- 5000+ Kuratoren-Datenbank

WICHTIG:
  - Spotify hat keine oeffentliche Pitch-API.
    Pitching laeuft ueber https://artists.spotify.com/ (manuell).
  - Sync-Deals brauchen Pre-Cleared-Stems von VEGA.
  - Diese Funktionen erzeugen Pitch-Texte und Tracking,
    das tatsaechliche Absenden bleibt manuell.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hive_io import audit, load_hive, save_hive

NODE_NAME = "ORION"


def build_pitch(track_id: str, curator: str,
                platform: str = "spotify") -> dict[str, Any]:
    """Erzeugt einen Pitch-Entwurf (Subject + Body) fuer einen Kurator.

    TODO: real impl
      - echte Kuratoren-Datenbank (CSV / Notion / Airtable)
      - LLM-generierte Pitches in der Sprache des Marktes
      - Locale-Tags aus Hive-Mind.tracks[track_id]['tags']
    """
    hive = load_hive()
    if track_id not in hive["tracks"]:
        raise KeyError(f"Track '{track_id}' nicht in Hive-Mind.")

    pitch_id = f"{track_id}_{curator}_{int(datetime.now(timezone.utc).timestamp())}"
    pitch = {
        "pitch_id": pitch_id,
        "track_id": track_id,
        "curator": curator,
        "platform": platform,
        "subject": f"[PITCH] {hive['tracks'][track_id].get('title', track_id)}",
        "body": (
            "Hi {{curator}},\n\n"
            "wir hoeren eure Playlist '{{playlist}}' regelmaessig und "
            "denken, dass unser neuer Track perfekt passt.\n\n"
            "Track: {{title}}\n"
            "Artist: {{artist}}\n"
            "BPM/Key: {{bpm}} / {{key}}\n"
            "Link: {{smartlink}}\n\n"
            "Stems fuer Sync sind auf Anfrage sofort verfuegbar.\n\n"
            "Beste Gruesse,\nSYNAPSE A&R"
        ),
        "sent_at": None,
        "status": "draft",
    }
    hive["pitch_log"][pitch_id] = pitch
    save_hive(hive)
    audit(NODE_NAME, "build_pitch",
          {"pitch_id": pitch_id, "track_id": track_id, "curator": curator})
    return pitch


def list_curators() -> list[str]:
    """Stub: gibt eine leere Liste zurueck, bis eine echte DB existiert."""
    return []
