#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
song_semantics.py — lernt Song-Semantik aus Traktor-Pro-Tracklisten
(*.nml + *.htm/*.html) und Suno-Text-Dateien (suno txt/*.txt).

Beide Export-Formate tragen das komplette Lyrics-Feld inkl. strukturierter
[Section]-Marker (Verse, Chorus, Drop, Beat-Switch, Ad-libs) und Prompt-Metadaten.

Dieses Modul:
  1. findet alle *.nml, *.htm, *.html unter FAVS_ROOT und *.txt unter SUNO_TXT_ROOT
  2. parsed Title/Artist/BPM/Key/Lyrics/Prompt je Track-Eintrag
  3. zerlegt die Lyrics in Sections (Label, BPM-Override, Beat-Switch-Flag,
     SFX, Ad-libs, Vocal-Style, Mood/Slang-Keywords, Visual Scene Cues, Cluster-Masks)
  4. extrahiert grounded Visual Objects (Autos, Waffen, Weed/Smoke, Cash, Night/Club, Cyber, Bavaria, Natur)
  5. berechnet Concept-Cluster-Bitmasks, Emotional Tension & Punchline-Density
  6. matched jeden Eintrag auf die tatsächliche mp3/m4a-Datei
  7. schreibt alles atomar & gepuffert in die SQLite-Tabelle song_semantics (db.py)

Nutzung:
    python song_semantics.py                # Full-Scan + Report
    python song_semantics.py --suno-txt     # Fokussierter Scan auf suno txt
    python song_semantics.py --report-only   # nur Report über bereits Gelerntes
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import DATA_DIR, FAVS_ROOT, MUSIK_ROOT, SUNO_TXT_ROOT
import db
from semantic_matching import CONCEPT_CLUSTERS, compute_cluster_mask


# ── Vokabulare & Klassifikatoren ─────────────────────────────────────────────
STYLE_VOCAB = [
    "phonk", "drill", "boom-bap", "boom bap", "trap", "lo-fi", "lofi",
    "industrial", "orchestral", "cyber", "glitch", "grime", "g-funk",
    "hardcore", "synthwave", "house", "techno", "dubstep",
]

ENERGY_VOCAB = [
    "aggressive", "sarcastic", "arrogant", "playful", "nostalgic", "anthemic",
    "hypnotic", "menacing", "creepy", "epic", "majestic", "chaotic",
    "dreamy", "sparse", "dense", "double-time", "half-time", "freefall",
    "triumphant", "gang vocals", "thrilling", "ruthless", "tense", "dark",
]

ATTITUDE_VOCAB = [
    "swag", "flow", "bars", "hustle", "grind", "respekt", "boss", "gang",
    "clique", "crew", "street", "hood", "underground", "real", "authentic",
    "rebel", "outlaw", "attitude", "real talk", "street cred", "monster",
]

WEED_VOCAB = [
    "weed", "420", "kush", "blunt", "joint", "bong", "gras", "kiffen",
    "thc", "stoned", "dope", "haze", "hasch", "tüte", "grinder", "spliff", "ganja",
]

MOOD_VOCAB = STYLE_VOCAB + ENERGY_VOCAB + ATTITUDE_VOCAB + WEED_VOCAB

SLANG_VOCAB = [
    "oida", "wurscht", "kurwa", "jopta", "wallah", "jalla", "bam",
    "oefoef", "tuetue", "089", "stadelheim", "mia san mia", "bist jetzt",
    "weiss wurscht is", "oktoberfest", "wiesn", "dirndl", "lederhosen", "tracht",
    "jva", "haftstrafenquartett", "acab", "knast", "oidasheim", "mvv",
    "graffiti", "sprayer", "train", "trains", "spray", "swag", "flow", "hustle",
    "grind", "gang", "crew", "hood", "street", "real talk", "respekt", "boss",
]

# ── Visuelle Szenen- & Objekt-Grounding-Vokabulare ──────────────────────────
VISUAL_SCENE_VOCAB: dict[str, list[str]] = {
    "CAR_VEHICLE": [
        "car", "cars", "bmw", "mercedes", "benz", "lowrider", "auto", "porsche", "audi",
        "drive", "drift", "speed", "motor", "wheels", "ride", "highway", "autobahn", "engine"
    ],
    "WEAPON_COMBAT": [
        "fist", "fists", "blade", "knife", "punch", "fight", "war", "battle", "gun",
        "cage", "coliseum", "hit", "strike", "blood", "scar", "chokehold", "boxen", "schlagen", "weapon"
    ],
    "WEED_SMOKE": [
        "weed", "smoke", "joint", "blunt", "kush", "bong", "high", "stoned", "puff",
        "cloud", "purple", "green", "daze", "trip", "kiffen", "tüte", "ganja", "cannabis"
    ],
    "CASH_LUXURY": [
        "money", "cash", "gold", "dollar", "euro", "chain", "chains", "diamonds",
        "rich", "boss", "queen", "king", "crown", "linen", "silk", "geld", "million"
    ],
    "NIGHT_CLUB": [
        "night", "dark", "moon", "shadow", "club", "party", "rave", "lights",
        "disco", "drink", "bar", "cocktail", "stage", "dunkel", "nacht"
    ],
    "CYBER_NEON": [
        "neon", "cyber", "laser", "matrix", "synth", "glitch", "screen",
        "digital", "tech", "future", "hud", "circuit", "robot", "grid"
    ],
    "BAVARIAN_ROOTS": [
        "oida", "bier", "beer", "wiesn", "eisbach", "089", "munich", "bayern",
        "lederhose", "weisswurst", "isar", "alpen", "minga"
    ],
    "NATURE_OUTDOORS": [
        "nature", "forest", "mountain", "sky", "water", "river", "sun", "rain",
        "tree", "clouds", "stars", "sea", "ocean", "wald", "berge", "fluss"
    ],
}

POSITIVE_WORDS = {
    "frei", "liebe", "glück", "stark", "feuer", "licht", "leben",
    "gold", "hoffnung", "sieg", "golden", "triumph", "peace", "love", "joy"
}
NEGATIVE_WORDS = {
    "angst", "hass", "tod", "schmerz", "frust", "wut", "zweifel",
    "krieg", "gefängnis", "shutdown", "error", "chaos", "pain", "rage", "blood", "kill"
}
TENSION_WORDS = {
    "ruthless", "twisted", "fight", "cage", "blade", "knife", "war", "conflict",
    "minefield", "despair", "dark", "shadow", "trap", "blood", "horror", "ominous",
    "thrilling", "menacing", "danger", "fists", "bruised", "clash"
}

_MOOD_SET = {tag.lower() for tag in MOOD_VOCAB}
_SLANG_SET = {word.lower() for word in SLANG_VOCAB}
_VISUAL_SETS = {cat: {w.lower() for w in words} for cat, words in VISUAL_SCENE_VOCAB.items()}
_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß0-9]{2,}")
_MOOD_PATTERNS = {tag: re.compile(rf"\b{re.escape(tag)}\b", re.IGNORECASE) for tag in MOOD_VOCAB}
_SLANG_PATTERNS = {word: re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE) for word in SLANG_VOCAB}
_VISUAL_PATTERNS = {
    cat: [re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in words]
    for cat, words in VISUAL_SCENE_VOCAB.items()
}

_SECTION_RE = re.compile(r"\[([^\[\]]{2,160})\]")
_BPM_RE = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*BPM", re.IGNORECASE)
_SFX_RE = re.compile(r"SFX:\s*([^)\]]+)")
_ADLIB_RE = re.compile(r'Ad-?lib:\s*["“]([^"”]+)["”]', re.IGNORECASE)
_BEAT_SWITCH_KEYWORDS = ("BEAT SWITCH", "BEAT DROP", "MOVEMENT", "TRANSITION", "DROP")
_SECTION_TYPE_KEYWORDS = [
    ("pre-chorus", "pre-chorus"), ("prechorus", "pre-chorus"),
    ("chorus", "chorus"), ("hook", "chorus"),
    ("verse", "verse"), ("intro", "intro"), ("outro", "outro"),
    ("bridge", "bridge"), ("breakdown", "breakdown"),
    ("movement", "movement"), ("transition", "transition"),
    ("beat switch", "beat_switch"), ("beat drop", "beat_switch"),
    ("drop", "beat_switch"), ("instrumental", "instrumental"),
    ("ad-lib", "adlib"),
]

_SECTION_TYPE_CUT_HINT = {
    "intro": ("hard_cut", "on_beat"),
    "outro": ("fade_out", "breath"),
    "chorus": ("jump_cut", "snap_drop"),
    "verse": ("dissolve", "on_beat"),
    "bridge": ("dissolve", "syncopated"),
    "breakdown": ("break", "breath"),
    "movement": ("jump_cut", "snap_drop"),
    "transition": ("whip", "syncopated"),
    "beat_switch": ("jump_cut", "snap_drop"),
    "instrumental": ("fade_out", "breath"),
    "adlib": ("whip", "syncopated"),
    "other": ("dissolve", "on_beat"),
}
_AGGRESSIVE_ENERGY_TAGS = {"aggressive", "menacing", "chaotic", "freefall", "double-time", "ruthless", "tense"}
_CALM_ENERGY_TAGS = {"hypnotic", "dreamy", "sparse", "nostalgic", "half-time"}
_EPIC_ENERGY_TAGS = {"epic", "majestic", "anthemic", "triumphant", "gang vocals", "monster"}

MAX_TRACKLIST_HTML_MB = 1.5
TRACKLIST_CACHE_PATH = DATA_DIR / "tracklist_parse_cache.json"


def _file_fingerprint(path: Path) -> str:
    st = path.stat()
    return hashlib.md5(f"{st.st_size}-{st.st_mtime}".encode()).hexdigest()


def _load_tracklist_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_tracklist_cache(cache_path: Path, cache: dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass


def _suggest_cut_hint(section_type: str, is_beat_switch: bool, section_mood_tags: list) -> tuple[str, str]:
    if is_beat_switch:
        return "jump_cut", "snap_drop"
    tags = set(section_mood_tags)
    if tags & _AGGRESSIVE_ENERGY_TAGS:
        return "whip", "on_beat"
    if tags & _CALM_ENERGY_TAGS:
        return "dissolve", "breath"
    if tags & _EPIC_ENERGY_TAGS:
        return "push", "energy_peak"
    return _SECTION_TYPE_CUT_HINT.get(section_type, _SECTION_TYPE_CUT_HINT["other"])


@dataclass
class RawTrackEntry:
    source_file: str
    title: str = ""
    artist: str = ""
    bpm: float = 0.0
    musical_key: str = ""
    comment: str = ""
    lyrics: str = ""
    dir_hint: str = ""     # Traktor-Style Ordnerpfad (nur NML) oder File Path (HTML)
    file_hint: str = ""    # Dateiname (z.B. "aqas-Ruthless_Love-48130fa8.m4a")
    prompt_description: str = ""
    tags_string: str = ""
    track_id: str = ""
    duration: float = 0.0


# ── Suno TXT Parser (*.txt) ──────────────────────────────────────────────────
def parse_suno_txt_file(path: Path) -> list[RawTrackEntry]:
    """Extrahiert Track-Metadaten, Lyrics und Prompt-Beschreibungen aus Suno-Txt-Dateien."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    lines = text.splitlines()
    file_hint = ""
    title = ""
    artist = ""
    track_id = ""
    lyrics_lines: list[str] = []
    in_lyrics = False
    raw_api_str = ""
    in_raw_api = False

    for line in lines:
        sline = line.strip()
        if sline.startswith("Metadata for:"):
            file_hint = sline.replace("Metadata for:", "").strip()
        elif sline.startswith("Title:") and not title:
            title = sline.replace("Title:", "").strip()
        elif sline.startswith("Artist:") and not artist:
            artist = sline.replace("Artist:", "").strip()
        elif sline.startswith("Track ID:") and not track_id:
            track_id = sline.replace("Track ID:", "").strip()
        elif sline.startswith("--- Lyrics ---"):
            in_lyrics = True
            in_raw_api = False
            continue
        elif sline.startswith("--- Raw API Response ---"):
            in_lyrics = False
            in_raw_api = True
            continue
        elif sline.startswith("Cover Art URL:") or sline.startswith("--- Musical Information ---"):
            in_lyrics = False

        if in_lyrics:
            lyrics_lines.append(line)
        elif in_raw_api:
            raw_api_str += line + "\n"

    lyrics = "\n".join(lyrics_lines).strip()
    prompt_desc = ""
    tags_str = ""
    bpm = 0.0
    duration = 0.0

    if raw_api_str.strip():
        try:
            api_data = json.loads(raw_api_str.strip(), strict=False)
            if not title:
                title = api_data.get("title", "")
            if not artist:
                artist = api_data.get("display_name") or api_data.get("handle", "")
            meta = api_data.get("metadata", {}) or {}
            prompt_desc = meta.get("gpt_description_prompt", "") or ""
            tags_str = meta.get("tags", "") or ""
            duration = float(meta.get("duration", 0.0) or 0.0)
            if not lyrics or lyrics.lower() == "[instrumental]":
                prompt_lyrics = meta.get("prompt", "") or ""
                if prompt_lyrics:
                    lyrics = prompt_lyrics
        except Exception:
            pass

    if not file_hint:
        stem = path.stem
        file_hint = stem if (stem.endswith(".m4a") or stem.endswith(".mp3")) else f"{stem}.m4a"

    return [RawTrackEntry(
        source_file=str(path),
        title=title,
        artist=artist,
        bpm=bpm,
        musical_key="",
        comment="",
        lyrics=lyrics,
        dir_hint="",
        file_hint=file_hint,
        prompt_description=prompt_desc,
        tags_string=tags_str,
        track_id=track_id,
        duration=duration,
    )]


# ── NML & HTML Parsers ───────────────────────────────────────────────────────
def parse_nml_file(path: Path) -> list[RawTrackEntry]:
    entries: list[RawTrackEntry] = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError:
        return _parse_nml_fallback(path)

    for entry_el in root.iter("ENTRY"):
        title = entry_el.get("TITLE", "")
        artist = entry_el.get("ARTIST", "")
        loc = entry_el.find("LOCATION")
        dir_hint = loc.get("DIR", "") if loc is not None else ""
        file_hint = loc.get("FILE", "") if loc is not None else ""
        info = entry_el.find("INFO")
        comment = info.get("COMMENT", "") if info is not None else ""
        lyrics = info.get("KEY_LYRICS", "") if info is not None else ""
        tempo = entry_el.find("TEMPO")
        bpm = float(tempo.get("BPM", 0.0)) if tempo is not None else 0.0
        key_el = entry_el.find("MUSICAL_KEY")
        musical_key = key_el.get("VALUE", "") if key_el is not None else ""
        entries.append(RawTrackEntry(
            source_file=str(path), title=title, artist=artist, bpm=bpm,
            musical_key=musical_key, comment=comment, lyrics=lyrics,
            dir_hint=dir_hint, file_hint=file_hint,
        ))
    return entries


def _parse_nml_fallback(path: Path) -> list[RawTrackEntry]:
    text = path.read_text(encoding="utf-8", errors="replace")
    entries = []
    for block in re.findall(r"<ENTRY\b.*?</ENTRY>", text, re.DOTALL):
        def attr(tag: str, name: str) -> str:
            m = re.search(rf"<{tag}\b[^>]*\b{name}=\"([^\"]*)\"", block)
            return html.unescape(m.group(1)) if m else ""

        entries.append(RawTrackEntry(
            source_file=str(path),
            title=attr("ENTRY", "TITLE"), artist=attr("ENTRY", "ARTIST"),
            bpm=float(attr("TEMPO", "BPM") or 0.0),
            musical_key=attr("MUSICAL_KEY", "VALUE"),
            comment=attr("INFO", "COMMENT"), lyrics=attr("INFO", "KEY_LYRICS"),
            dir_hint=attr("LOCATION", "DIR"), file_hint=attr("LOCATION", "FILE"),
        ))
    return entries


def parse_html_file(path: Path) -> list[RawTrackEntry]:
    raw = path.read_bytes().replace(b"\x00", b"")
    text = raw.decode("utf-8", errors="replace")

    row_texts = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.DOTALL | re.IGNORECASE)
    if not row_texts:
        return []

    header_cells = None
    for row_text in row_texts:
        ths = re.findall(r"<th[^>]*>(.*?)</th>", row_text, re.DOTALL | re.IGNORECASE)
        if ths:
            header_cells = [html.unescape(re.sub(r"<.*?>", "", h)).strip() for h in ths]
            break
    if not header_cells:
        return []
    col = {name.lower(): i for i, name in enumerate(header_cells)}

    def get(cells: list, *names: str) -> str:
        for name in names:
            i = col.get(name.lower())
            if i is not None and i < len(cells):
                return cells[i]
        return ""

    entries = []
    for row_text in row_texts:
        cells_raw = re.findall(r"<td[^>]*>(.*?)</td>", row_text, re.DOTALL | re.IGNORECASE)
        if not cells_raw:
            continue
        cells = [html.unescape(re.sub(r"<.*?>", "", c)).strip() for c in cells_raw]
        if not any(cells):
            continue
        bpm_str = get(cells, "bpm", "tempo")
        try:
            bpm = float(re.sub(r"[^\d.]", "", bpm_str) or 0.0)
        except ValueError:
            bpm = 0.0
        entries.append(RawTrackEntry(
            source_file=str(path),
            title=get(cells, "title"), artist=get(cells, "artist"),
            bpm=bpm, musical_key=get(cells, "key"),
            comment=get(cells, "comment", "comment2"),
            lyrics=get(cells, "lyrics", "lyric"),
            dir_hint=get(cells, "file path"), file_hint=get(cells, "file name"),
        ))
    return entries


# ── Lyrics Semantik & Visual Object Grounding ────────────────────────────────
def _classify_section_type(label: str) -> str:
    low = label.lower()
    for keyword, section_type in _SECTION_TYPE_KEYWORDS:
        if keyword in low:
            return section_type
    return "other"


_FEMALE_VOCAL_RE = re.compile(
    r"(?:\[|\(|\b)(?:"
    r"female\s+(?:mc|vocals?|vocalist|singer|rapper|lead|hook|chorus|verse|voice)|singer:\s*female|woman\s+vocals?|"
    r"woman|women|girl|girls|queen|queens|chick|chicks|lady|ladies|miss|babe|babes|she|her|"
    r"rapperin|sängerin|saengerin|frau|frauen|dirndl|braut|chaya|dame|oide|maderl|sie|ihr|weiblich|"
    r"chica|chicas|mujer|mujeres|niña|niñas|reina|mami|dama|ella|"
    r"femme|femmes|fille|filles|reine|chanteuse|rappeuse|elle|"
    r"donna|donne|ragazza|ragazze|regina|signora|lei|"
    r"девушка|женщина|девочка|она|рэперша|певица"
    r")(?:\]|\)|\b)",
    re.IGNORECASE
)
_MALE_VOCAL_RE = re.compile(
    r"(?:\[|\(|\b)(?:"
    r"male\s+(?:mc|vocals?|vocalist|singer|rapper|lead|hook|chorus|verse|voice)|singer:\s*male|man\s+vocals?|"
    r"man|men|boy|boys|king|kings|dude|dudes|guy|guys|bro|bros|sir|mister|he|him|"
    r"rapper|sänger|saenger|mann|männer|maenner|haberer|bazi|kerl|oida|er|ihn|brudi|bruder|männlich|"
    r"chico|chicos|hombre|hombres|niño|niños|rey|papi|caballero|él|el|hermano|tio|"
    r"homme|hommes|garçon|garcon|garcons|roi|mec|mecs|il|frère|frere|gars|chanteur|rappeur|"
    r"uomo|uomini|ragazzo|ragazzi|re|signore|lui|fratello|"
    r"парень|мужчина|мальчик|он|братан|рэпер|певец"
    r")(?:\]|\)|\b)",
    re.IGNORECASE
)
_DUET_VOCAL_RE = re.compile(
    r"(?:\[|\(|\b)(?:"
    r"duet|duett|duette|duetto|дуэт|"
    r"male\s*(?:&|and|\/|\+)\s*female|female\s*(?:&|and|\/|\+)\s*male|"
    r"mann\s*(?:&|und|\/|\+)\s*frau|frau\s*(?:&|und|\/|\+)\s*mann|"
    r"er\s*(?:&|und|\/|\+)\s*sie|sie\s*(?:&|und|\/|\+)\s*er|"
    r"chico\s*(?:&|y|\/|\+)\s*chica|chica\s*(?:&|y|\/|\+)\s*chico|"
    r"homme\s*(?:&|et|\/|\+)\s*femme|femme\s*(?:&|et|\/|\+)\s*homme|"
    r"both\s+(?:vocals?|singers?|mcs?)|both|alle|together|zusammen|juntos|ensemble|"
    r"dialog|dialogue|call\s*(?:and|&)\s*response|versus|vs\.?|"
    r"m\s*&\s*f|f\s*&\s*m|m\s*\+\s*f|f\s*\+\s*m"
    r")(?:\]|\)|\b)",
    re.IGNORECASE
)

_LINE_GENDER_PREFIX_RE = re.compile(
    r"^\s*(?:\[|\(|\b)?(?:(MC\s*1|MC\s*2|M|F|Male|Female|Mann|Frau|Boy|Girl|Er|Sie|Chico|Chica|Homme|Femme|Парень|Девушка|Both|Duet|Duett|Alle))\s*(?:\]|\)|\:|\-)\s*(.*)$",
    re.IGNORECASE
)


def _vocal_style(text: str) -> str:
    if _DUET_VOCAL_RE.search(text):
        return "dual"
    has_fem = bool(_FEMALE_VOCAL_RE.search(text))
    has_mal = bool(_MALE_VOCAL_RE.search(text))
    if has_fem and has_mal:
        return "dual"
    if has_fem:
        return "female"
    if has_mal:
        return "male"
    low = text.lower()
    has_male_word = "male" in low or "mann" in low or "boy" in low or "guy" in low
    has_female_word = "female" in low or "frau" in low or "girl" in low or "woman" in low
    if has_female_word and has_male_word:
        return "dual"
    if has_female_word:
        return "female"
    if has_male_word:
        return "male"
    return "unknown"


def parse_line_genders(lyrics: str) -> tuple[list[dict], bool, list[dict]]:
    """Extrahiert zeilenweise Gesangs- und MC-Geschlechter (M, F, Duet)
    inklusive schneller Wechsel (Flip-Flops / Dialoge / Duette) und Zeit-Timeline."""
    if not lyrics:
        return [], False, []

    lines = [ln.strip() for ln in lyrics.splitlines() if ln.strip()]
    if not lines:
        return [], False, []

    parsed_lines: list[dict] = []
    current_gender = "unknown"
    flip_count = 0
    prev_valid_gender = None

    total_lines = len(lines)
    for idx, raw_line in enumerate(lines):
        line_text = raw_line
        detected_gender = None

        # 1. Zeilen-Präfixe (z.B. "M: ...", "F: ...", "[Female] ...", "Chica: ...")
        prefix_match = _LINE_GENDER_PREFIX_RE.match(raw_line)
        if prefix_match:
            speaker_tag = prefix_match.group(1).strip().lower()
            line_text = prefix_match.group(2).strip()
            if speaker_tag in ("f", "female", "frau", "girl", "sie", "chica", "femme", "девушка", "mc 2"):
                detected_gender = "female"
            elif speaker_tag in ("m", "male", "mann", "boy", "er", "chico", "homme", "парень", "mc 1"):
                detected_gender = "male"
            elif speaker_tag in ("both", "duet", "duett", "alle"):
                detected_gender = "dual"

        # 2. Vokabulare & Bracket-Marker
        if not detected_gender:
            if _DUET_VOCAL_RE.search(raw_line):
                detected_gender = "dual"
            else:
                has_fem = bool(_FEMALE_VOCAL_RE.search(raw_line))
                has_mal = bool(_MALE_VOCAL_RE.search(raw_line))
                if has_fem and has_mal:
                    detected_gender = "dual"
                elif has_fem:
                    detected_gender = "female"
                elif has_mal:
                    detected_gender = "male"

        if detected_gender:
            current_gender = detected_gender

        assigned_gender = current_gender if current_gender != "unknown" else "unknown"

        # Zähle schnelle M/F Flip-Flop-Wechsel
        if assigned_gender in ("male", "female"):
            if prev_valid_gender and prev_valid_gender != assigned_gender:
                flip_count += 1
            prev_valid_gender = assigned_gender

        rel_start = round(idx / total_lines, 4)
        rel_end = round((idx + 1) / total_lines, 4)

        parsed_lines.append({
            "line_index": idx,
            "text": line_text or raw_line,
            "gender": assigned_gender,
            "rel_start": rel_start,
            "rel_end": rel_end,
        })

    is_flip_flop = flip_count >= 2

    # Fasse zusammenhängende Bereiche zu gender_timeline zusammen
    gender_timeline: list[dict] = []
    if parsed_lines:
        cur_int_gender = parsed_lines[0]["gender"]
        cur_int_start = parsed_lines[0]["rel_start"]
        cur_int_end = parsed_lines[0]["rel_end"]

        for item in parsed_lines[1:]:
            if item["gender"] == cur_int_gender:
                cur_int_end = item["rel_end"]
            else:
                gender_timeline.append({
                    "start_frac": cur_int_start,
                    "end_frac": cur_int_end,
                    "gender": cur_int_gender,
                })
                cur_int_gender = item["gender"]
                cur_int_start = item["rel_start"]
                cur_int_end = item["rel_end"]

        gender_timeline.append({
            "start_frac": cur_int_start,
            "end_frac": cur_int_end,
            "gender": cur_int_gender,
        })

    return parsed_lines, is_flip_flop, gender_timeline


def _extract_visual_objects(text: str) -> list[str]:
    """Findet visuell darstellbare Objekte und Szenen im Text über Token-Sets."""
    tokens = set(_TOKEN_RE.findall(text.lower()))
    found = [cat for cat, words in _VISUAL_SETS.items() if not tokens.isdisjoint(words)]
    return sorted(found)


def analyze_lyrics(lyrics: str, prompt_description: str = "", tags_string: str = "") -> dict:
    """Zerlegt Lyrics, Prompts und Style-Tags in strukturierte Song- und Sektions-Semantik."""
    combined_context = f"{lyrics} {prompt_description} {tags_string}".strip()
    if not combined_context:
        return {
            "sections": [], "movements": [], "beat_switch_count": 0,
            "slang": {}, "sentiment": 0.0, "mood_tags": [],
            "style_weights": {}, "dominant_style": None, "energy_character": None,
            "weed_vibe_score": 0.0, "mc_gender": None, "visual_objects": [],
            "cluster_mask": 0, "prompt_description": "", "tension_score": 0.5,
            "punchline_density": 0.0, "line_genders": [], "is_flip_flop": False,
            "gender_timeline": [],
        }

    line_genders, is_flip_flop, gender_timeline = parse_line_genders(lyrics)

    markers = list(_SECTION_RE.finditer(lyrics)) if lyrics else []
    sections = []
    section_genders = []

    if not markers and lyrics:
        # Erstelle Standard-Sektion falls keine [Section]-Marker existieren
        section_type = "verse"
        sec_tokens = set(_TOKEN_RE.findall(lyrics.lower()))
        sec_mood_tags = [tag for tag in _MOOD_SET if tag in sec_tokens][:6]
        sec_visuals = _extract_visual_objects(lyrics)
        sec_mask = compute_cluster_mask(lyrics)
        cut_style, sync_type = _suggest_cut_hint(section_type, False, sec_mood_tags)
        sec_vocal = _vocal_style(lyrics)
        if is_flip_flop:
            sec_vocal = "dual"
        if sec_vocal != "unknown":
            section_genders.append(sec_vocal)
        sec_line_genders, sec_flip_flop, sec_gender_timeline = parse_line_genders(lyrics)
        sections.append({
            "order": 0,
            "label": "Main",
            "section_type": section_type,
            "bpm": None,
            "is_beat_switch": False,
            "vocal_style": sec_vocal,
            "sfx": [],
            "adlibs": [],
            "mood_tags": sec_mood_tags,
            "visual_cues": sec_visuals,
            "cluster_mask": sec_mask,
            "suggested_cut_style": cut_style,
            "suggested_sync_type": sync_type,
            "text_preview": lyrics[:240],
            "line_genders": sec_line_genders,
            "is_flip_flop": sec_flip_flop,
            "gender_timeline": sec_gender_timeline,
        })
    else:
        for i, m in enumerate(markers):
            label = m.group(1).strip()
            body_start = m.end()
            body_end = markers[i + 1].start() if i + 1 < len(markers) else len(lyrics)
            body = lyrics[body_start:body_end].strip()
            bpm_match = _BPM_RE.search(label) or _BPM_RE.search(body[:120])
            is_beat_switch = any(kw in label.upper() for kw in _BEAT_SWITCH_KEYWORDS)
            sfx = [s.strip().rstrip(")") for s in _SFX_RE.findall(label + " " + body[:300])]
            adlibs = _ADLIB_RE.findall(body)
            section_type = _classify_section_type(label)
            section_text = label + " " + body
            sec_tokens = set(_TOKEN_RE.findall(section_text.lower()))
            section_mood_tags = [tag for tag in _MOOD_SET if tag in sec_tokens][:6]
            sec_visuals = _extract_visual_objects(section_text)
            sec_mask = compute_cluster_mask(section_text)
            cut_style, sync_type = _suggest_cut_hint(section_type, is_beat_switch, section_mood_tags)
            sec_vocal = _vocal_style(section_text)
            sec_line_genders, sec_flip_flop, sec_gender_timeline = parse_line_genders(body if body else section_text)
            if sec_flip_flop:
                sec_vocal = "dual"
            if sec_vocal != "unknown":
                section_genders.append(sec_vocal)
            sections.append({
                "order": i,
                "label": label,
                "section_type": section_type,
                "bpm": float(bpm_match.group(1)) if bpm_match else None,
                "is_beat_switch": is_beat_switch,
                "vocal_style": sec_vocal,
                "sfx": sfx[:6],
                "adlibs": adlibs[:8],
                "mood_tags": section_mood_tags,
                "visual_cues": sec_visuals,
                "cluster_mask": sec_mask,
                "suggested_cut_style": cut_style,
                "suggested_sync_type": sync_type,
                "text_preview": body[:240],
                "line_genders": sec_line_genders,
                "is_flip_flop": sec_flip_flop,
                "gender_timeline": sec_gender_timeline,
            })

    # MC-Gender Aggregation
    full_vocal = _vocal_style(combined_context)
    if is_flip_flop or "dual" in section_genders or (_DUET_VOCAL_RE.search(combined_context) is not None) or ("female" in section_genders and "male" in section_genders):
        mc_gender = "dual"
    elif full_vocal in ("female", "male", "dual"):
        mc_gender = full_vocal
    elif "female" in section_genders:
        mc_gender = "female"
    elif "male" in section_genders:
        mc_gender = "male"
    else:
        mc_gender = None

    movements = sorted({s["bpm"] for s in sections if s["bpm"]})
    beat_switch_count = sum(1 for s in sections if s["is_beat_switch"])

    tokens = _TOKEN_RE.findall(combined_context.lower())
    token_counts = {}
    for t in tokens:
        token_counts[t] = token_counts.get(t, 0) + 1

    slang = {w: token_counts[w] for w in _SLANG_SET if w in token_counts}
    style_weights = {tag: token_counts[tag] for tag in _MOOD_SET if tag in token_counts}
    mood_tags = list(style_weights.keys())

    def _top_tag(vocab: list) -> str | None:
        candidates = {tag: c for tag, c in style_weights.items() if tag in vocab}
        return max(candidates, key=candidates.get) if candidates else None

    dominant_style = _top_tag(STYLE_VOCAB)
    energy_character = _top_tag(ENERGY_VOCAB)

    # Weed-Vibe-Score
    weed_hits = sum(style_weights.get(tag, 0) for tag in WEED_VOCAB)
    word_count = max(1, len(tokens))
    weed_vibe_score = round(min(1.0, (weed_hits / word_count) / 0.08), 3)

    # Sentiment & Emotional Tension
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    sentiment = (pos - neg) / (pos + neg + 1)

    tension_hits = sum(1 for t in tokens if t in TENSION_WORDS)
    tension_score = round(min(1.0, 0.3 + (tension_hits / word_count) * 6.0), 3)

    # Punchline Density (Reime / Slang / Lines)
    num_lines = max(1, len(lyrics.splitlines()))
    punchline_density = round(min(1.0, (len(slang) + len(style_weights)) / num_lines), 3)

    # Global Visual Scene Objects
    visual_objects = _extract_visual_objects(combined_context)

    # Global Concept Cluster Bitmask
    cluster_mask = compute_cluster_mask(combined_context)

    return {
        "sections": sections,
        "movements": movements,
        "beat_switch_count": beat_switch_count,
        "slang": slang,
        "sentiment": round(sentiment, 3),
        "mood_tags": mood_tags,
        "style_weights": style_weights,
        "dominant_style": dominant_style,
        "energy_character": energy_character,
        "weed_vibe_score": weed_vibe_score,
        "mc_gender": mc_gender,
        "visual_objects": visual_objects,
        "cluster_mask": cluster_mask,
        "prompt_description": prompt_description[:500] if prompt_description else "",
        "tension_score": tension_score,
        "punchline_density": punchline_density,
        "line_genders": line_genders,
        "is_flip_flop": is_flip_flop,
        "gender_timeline": gender_timeline,
    }


# ── mp3-Auflösung & Datei-Indexierung ─────────────────────────────────────────
def build_filename_index(favs_root: Path, extra_roots: list[Path] | None = None) -> dict[str, Any]:
    """Baut einen blitzschnellen Lookup-Index (Dateinamen, Stems, Short-UUIDs) über alle Musikordner auf."""
    ignored = {"stems", "16zu9", "9zu16", "tmp", "logs", "data", "imgs", "styles", "__pycache__", "suno txt", "suno_txt"}
    all_roots = [favs_root]
    if extra_roots:
        for r in extra_roots:
            if r and r.exists() and r not in all_roots:
                all_roots.append(r)

    filename_map: dict[str, list[str]] = {}
    stem_map: dict[str, list[str]] = {}
    short_id_map: dict[str, list[str]] = {}
    title_map: dict[str, list[str]] = {}

    valid_exts = {".mp3", ".m4a", ".wav", ".flac"}
    for root in all_roots:
        if not root or not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(str(root)):
            # Prune ignored subdirectories in-place
            dirnames[:] = [d for d in dirnames if d.lower() not in ignored and not d.lower().startswith("_demucs_tmp") and "stems" not in d.lower()]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in valid_exts:
                    continue
                full_p = os.path.join(dirpath, fname)
                fname_low = fname.lower()
                stem_low = os.path.splitext(fname)[0].lower()

                filename_map.setdefault(fname_low, []).append(full_p)
                stem_map.setdefault(stem_low, []).append(full_p)

                # Extrahiere 8-stellige Hex UUIDs aus dem Dateinamen (z.B. "48130fa8")
                hex_matches = re.findall(r"[0-9a-fA-F]{8}", stem_low)
                for h in hex_matches:
                    short_id_map.setdefault(h.lower(), []).append(full_p)

                # Bereinigter Titel
                clean_title = re.sub(r"[^a-zA-Z0-9]+", " ", stem_low).strip()
                if clean_title:
                    title_map.setdefault(clean_title, []).append(full_p)

    return {
        "filenames": filename_map,
        "stems": stem_map,
        "short_ids": short_id_map,
        "titles": title_map,
    }


def resolve_mp3_path(
    entry: RawTrackEntry,
    source_path: Path,
    favs_root: Path,
    index_bundle: dict[str, Any] | None = None
) -> str | None:
    """Löst einen Tracklist/Suno-Eintrag deterministisch auf die zugehörige Audiodatei auf."""
    # 1. Direkter Match im selben Ordner
    if entry.file_hint:
        cand = source_path.parent / entry.file_hint
        if cand.exists():
            return str(cand)
        # Andere Audio-Endungen prüfen
        for ext in (".mp3", ".m4a", ".wav"):
            cand_ext = cand.with_suffix(ext)
            if cand_ext.exists():
                return str(cand_ext)

    if not index_bundle:
        return None

    fname_map = index_bundle.get("filenames", {})
    stem_map = index_bundle.get("stems", {})
    short_id_map = index_bundle.get("short_ids", {})
    title_map = index_bundle.get("titles", {})

    # 2. Dateinamen-Match
    if entry.file_hint:
        hint_low = entry.file_hint.lower()
        if hint_low in fname_map:
            return fname_map[hint_low][0]
        hint_stem = Path(hint_low).stem
        if hint_stem in stem_map:
            return stem_map[hint_stem][0]

    # 3. Suno Track ID Match (8-Char Prefix)
    if entry.track_id:
        short_id = entry.track_id[:8].lower()
        if short_id in short_id_map:
            return short_id_map[short_id][0]

    # 4. Titel Match
    if entry.title:
        clean_t = re.sub(r"[^a-zA-Z0-9]+", " ", entry.title.lower()).strip()
        if clean_t in title_map:
            return title_map[clean_t][0]

    return None


# ── Scan & Learn ─────────────────────────────────────────────────────────────
def find_tracklist_files(
    favs_root: Path,
    suno_txt_root: Path | None = None
) -> tuple[list[Path], list[Path], list[Path]]:
    nml_files = sorted(favs_root.rglob("*.nml")) if favs_root.exists() else []
    html_files = sorted(list(favs_root.rglob("*.htm")) + list(favs_root.rglob("*.html"))) if favs_root.exists() else []

    suno_txt_files: list[Path] = []
    if suno_txt_root and suno_txt_root.exists():
        suno_txt_files = sorted(suno_txt_root.rglob("*.txt"))
    elif favs_root.exists():
        suno_txt_files = sorted(favs_root.rglob("*.txt"))

    return nml_files, html_files, suno_txt_files


def scan_and_learn(
    favs_root: Path | None = None,
    suno_txt_root: Path | None = None,
    log=print
) -> dict:
    favs_root = favs_root or FAVS_ROOT
    suno_txt_root = suno_txt_root or SUNO_TXT_ROOT

    nml_files, html_files, suno_txt_files = find_tracklist_files(favs_root, suno_txt_root)
    log(f"[song_semantics] Gefunden: {len(nml_files)} .nml, {len(html_files)} .htm/.html, {len(suno_txt_files)} Suno .txt Dateien.")

    extra_roots = []
    if MUSIK_ROOT.exists():
        extra_roots.append(MUSIK_ROOT)
    if suno_txt_root and suno_txt_root.exists():
        extra_roots.append(suno_txt_root)

    log("[song_semantics] Erstelle schnellen Audio-Datei-Index...")
    index_bundle = build_filename_index(favs_root, extra_roots)
    total_audio_indexed = sum(len(v) for v in index_bundle["filenames"].values())
    log(f"[song_semantics] {total_audio_indexed} Audio-Dateien im Suchindex erfasst.")

    parse_cache = _load_tracklist_cache(TRACKLIST_CACHE_PATH)
    cache_changed = False
    cache_hits = 0

    best_entry_by_mp3: dict[str, RawTrackEntry] = {}

    all_files: list[tuple[Path, Any]] = (
        [(p, parse_nml_file) for p in nml_files] +
        [(p, parse_html_file) for p in html_files] +
        [(p, parse_suno_txt_file) for p in suno_txt_files]
    )

    stats = {
        "files": len(all_files),
        "entries": 0,
        "resolved": 0,
        "learned": 0,
        "beat_switch_songs": 0,
        "suno_txt_scanned": len(suno_txt_files),
    }

    for file_idx, (path, parser) in enumerate(all_files, 1):
        if file_idx % 2500 == 0 or file_idx == len(all_files):
            log(f"[song_semantics] Verarbeite Metadaten: {file_idx}/{len(all_files)} Dateien...")

        if parser is parse_html_file:
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > MAX_TRACKLIST_HTML_MB:
                continue

        cache_key = str(path)
        fingerprint = _file_fingerprint(path)
        cached = parse_cache.get(cache_key)

        if cached and cached.get("fingerprint") == fingerprint:
            entries = [RawTrackEntry(**e) for e in cached.get("entries", [])]
            cache_hits += 1
        else:
            try:
                entries = parser(path)
            except Exception as e:
                continue
            parse_cache[cache_key] = {
                "fingerprint": fingerprint,
                "entries": [asdict(e) for e in entries],
            }
            cache_changed = True

        stats["entries"] += len(entries)
        for entry in entries:
            mp3_path = resolve_mp3_path(entry, path, favs_root, index_bundle)
            if not mp3_path:
                continue
            existing = best_entry_by_mp3.get(mp3_path)
            if existing is None or len(entry.lyrics or "") > len(existing.lyrics or ""):
                best_entry_by_mp3[mp3_path] = entry

    if cache_hits:
        log(f"[song_semantics] {cache_hits}/{len(all_files)} Dateien unverändert (Cache-Treffer).")
    if cache_changed:
        _save_tracklist_cache(TRACKLIST_CACHE_PATH, parse_cache)

    # Check already analyzed records in DB to skip redundant work
    existing_db = {s["path"]: s for s in db.get_all_song_semantics()}
    needed_entries = []
    cached_records = []

    for mp3_path, entry in best_entry_by_mp3.items():
        ex = existing_db.get(mp3_path)
        if ex and ex.get("source_file") == entry.source_file and ex.get("visual_objects"):
            cached_records.append(ex)
            stats["resolved"] += 1
            stats["learned"] += 1
            if ex.get("beat_switch_count", 0) > 0:
                stats["beat_switch_songs"] += 1
        else:
            needed_entries.append((mp3_path, entry))

    log(f"[song_semantics] Analysiere semantische Lyrics für {len(needed_entries)} neue/geänderte Songs ({len(cached_records)} aus DB-Cache)...")

    def _process_entry(item):
        mp3_path, entry = item
        semantics = analyze_lyrics(
            lyrics=entry.lyrics,
            prompt_description=entry.prompt_description,
            tags_string=entry.tags_string,
        )
        return {
            "path": mp3_path,
            "source_file": entry.source_file,
            "title": entry.title or Path(mp3_path).stem,
            "artist": entry.artist,
            "bpm": entry.bpm,
            "musical_key": entry.musical_key,
            "sections": semantics["sections"],
            "movements": semantics["movements"],
            "mood_tags": semantics["mood_tags"],
            "slang": semantics["slang"],
            "beat_switch_count": semantics["beat_switch_count"],
            "sentiment": semantics["sentiment"],
            "dominant_style": semantics["dominant_style"],
            "energy_character": semantics["energy_character"],
            "style_weights": semantics["style_weights"],
            "mc_gender": semantics.get("mc_gender"),
            "visual_objects": semantics.get("visual_objects", []),
            "cluster_mask": semantics.get("cluster_mask", 0),
            "prompt_description": semantics.get("prompt_description", ""),
            "tension_score": semantics.get("tension_score", 0.5),
            "punchline_density": semantics.get("punchline_density", 0.0),
        }

    records = []
    if needed_entries:
        from concurrent.futures import ThreadPoolExecutor
        workers = min(32, (os.cpu_count() or 4) * 4)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(_process_entry, needed_entries))
        
        for r in records:
            stats["resolved"] += 1
            stats["learned"] += 1
            if r.get("beat_switch_count", 0) > 0:
                stats["beat_switch_songs"] += 1

        log(f"[song_semantics] Speichere {len(records)} Songs in beat_sync.db...")
        db.upsert_song_semantics_many(records)

    log(f"[song_semantics] Fertig: {stats['learned']} Songs mit tiefen Lyrics- & Szenen-Semantiken gelernt.")
    return stats


def get_semantics_for_song(mp3_path: str) -> dict | None:
    """Öffentliche API für Song-Semantik-Abfragen."""
    return db.get_song_semantics(mp3_path)


def main():
    parser = argparse.ArgumentParser(description="Lyrics & Tracklisten -> Song-Semantik-DB")
    parser.add_argument("--favs-root", type=str, default=None)
    parser.add_argument("--suno-txt-root", type=str, default=None)
    parser.add_argument("--suno-txt", action="store_true", help="Fokussiert Scan auf suno txt Ordner")
    parser.add_argument("--report-only", action="store_true", help="Nur Report über bereits Gelerntes")
    args = parser.parse_args()

    db.init_db()
    if not args.report_only:
        favs_root = Path(args.favs_root) if args.favs_root else FAVS_ROOT
        suno_root = Path(args.suno_txt_root) if args.suno_txt_root else SUNO_TXT_ROOT
        scan_and_learn(favs_root=favs_root, suno_txt_root=suno_root)

    all_semantics = db.get_all_song_semantics()
    print(f"\n[song_semantics] {len(all_semantics)} Song(s) mit gelernter Semantik in der DB.")
    with_visuals = [s for s in all_semantics if s.get("visual_objects")]
    print(f"[song_semantics] {len(with_visuals)} Song(s) mit visuellen Objekt-Groundings.")
    for s in sorted(all_semantics, key=lambda x: len(x.get("visual_objects", [])), reverse=True)[:15]:
        v_str = ", ".join(s.get("visual_objects", [])) or "–"
        style_str = s.get("dominant_style") or "?"
        tension = s.get("tension_score", 0.5)
        print(f"  - {s['title']!r} ({Path(s['path']).name}): Visuals=[{v_str}] | Style={style_str} | Tension={tension:.2f} | Mask={s.get('cluster_mask', 0)}")


if __name__ == "__main__":
    main()
