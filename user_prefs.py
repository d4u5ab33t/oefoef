"""
user_prefs.py — liest das bisher nie gelesene user_preferences.yaml und
liefert daraus einen additiven Scoring-Bonus/-Malus für die Clip-Auswahl in
timeline_builder.py.

Die Datei lag bereits im Projekt-Root, wurde aber nur von
module_2_user_prefs.py referenziert — einem RL-Bandit-Prototyp, der nie an
den echten (deterministischen) Resolver angeschlossen war (main.py:
"Deterministic resolver: energy, semantic tags, information density and
continuity."). Statt die komplette RL-Maschinerie einzubauen, wird hier nur
das eigentliche Nutzersignal (likes/dislikes + global_weight) als simpler,
deterministischer Bonus in den bestehenden Score von
timeline_builder._pick_clip eingespeist.

Kein pyyaml nötig: die Datei hat eine feste, einfache Struktur
(global_weight + likes/dislikes-Listen aus tag/weight-Paaren) — ein
Mini-Regex-Parser reicht und spart eine zusätzliche Abhängigkeit.

Fehlt die Datei, ist sie leer oder kaputt, liefert preference_bonus() für
JEDEN Clip 0.0 -> Verhalten ist dann exakt identisch zu "Feature nicht
vorhanden", niemals ein Grund für einen Absturz.
"""
from __future__ import annotations

import re
from pathlib import Path

from config import USER_PREFS_PATH

_cache: dict | None = None
_cache_mtime: float | None = None
_EMPTY = {"global_weight": 0.0, "likes": {}, "dislikes": {}}


def _extract_block(text: str, key: str) -> dict:
    block_match = re.search(rf"{key}:\s*\n((?:[ \t]+.*\n?)+)", text)
    if not block_match:
        return {}
    pairs = re.findall(
        r'-\s*tag:\s*"?([\w-]+)"?\s*\n\s*weight:\s*(-?[\d.]+)',
        block_match.group(1),
    )
    return {tag: float(weight) for tag, weight in pairs}


def _parse_simple_yaml(text: str) -> dict:
    """Handgeschriebener Mini-Parser NUR für die feste Struktur von
    user_preferences.yaml — kein allgemeiner YAML-Parser."""
    weight_match = re.search(r"global_weight:\s*([\d.]+)", text)
    global_weight = float(weight_match.group(1)) if weight_match else 0.3
    return {
        "global_weight": global_weight,
        "likes": _extract_block(text, "likes"),
        "dislikes": _extract_block(text, "dislikes"),
    }


def _load() -> dict:
    global _cache, _cache_mtime
    path = Path(USER_PREFS_PATH)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return _EMPTY
    if _cache is not None and _cache_mtime == mtime:
        return _cache
    try:
        parsed = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        parsed = _EMPTY
    _cache, _cache_mtime = parsed, mtime
    return parsed


def preference_bonus(tags: list) -> float:
    """Additiver Scoring-Bonus/Malus für einen Clip anhand seiner Tags
    (clip_pool._tags_from_path). Summe der Einzelgewichte aller matchenden
    likes/dislikes-Tags, skaliert mit global_weight (0.0 = Feature aus,
    1.0 = Nutzergeschmack zählt voll mit)."""
    prefs = _load()
    if not tags or (not prefs["likes"] and not prefs["dislikes"]):
        return 0.0
    tagset = {t.lower() for t in tags}
    total = sum(w for tag, w in prefs["likes"].items() if tag.lower() in tagset)
    total += sum(w for tag, w in prefs["dislikes"].items() if tag.lower() in tagset)
    return round(total * prefs["global_weight"], 4)


def has_preferences() -> bool:
    prefs = _load()
    return bool(prefs["likes"] or prefs["dislikes"])
