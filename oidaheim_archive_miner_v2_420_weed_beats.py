#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OIDA NEXT LEVEL BEAT FORGE
==========================

Liest rekursiv HTML-Songarchive und erzeugt daraus NEUE Beat-/Suno-Konzepte.

INPUT:
    J:\\Oidasheim\\Musik\\FAVs\\*.html
    J:\\Oidasheim\\Musik\\FAVs\\**\\*.html

OUTPUT:
    oida_next_level_beats/
        beats_v001.html
        beats_v001.json
        beats_v001.txt

Eigenschaften:
- rekursiver HTML-Scan
- erkennt Song-Metadaten
- analysiert vorhandene Beat-/Flow-/Strukturbegriffe
- extrahiert BPM-Verteilung
- erkennt Beat Switches
- erzeugt neue Genre-Mixe
- erzeugt neue Songstrukturen
- injiziert Breaks und Überraschungen
- Fake Drops
- Silence Breaks
- Half-Time / Double-Time
- 808 Dropouts
- Scratch Breaks
- Acapella Breaks
- Rhythmuswechsel
- Final Mutations
- Suno-4.5-orientierte Style Tags
- keine Input-Dateien werden überschrieben
- automatische Versionierung

Keine externen Pakete erforderlich.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import median
from html.parser import HTMLParser


# ============================================================
# CONFIG
# ============================================================

DEFAULT_ROOT = Path(r"J:\Oidasheim\Musik\FAVs")
DEFAULT_OUT = Path("oida_next_level_beats")

SEED = None


# ============================================================
# HTML PARSER
# ============================================================

class TableParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = None
        self.current_cell = None
        self.in_td = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "tr":
            self.current_row = []

        elif tag in ("td", "th"):
            self.current_cell = []
            self.in_td = True

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in ("td", "th"):
            if self.current_row is not None:
                text = " ".join(self.current_cell or [])
                text = re.sub(r"\s+", " ", text).strip()
                self.current_row.append(text)

            self.current_cell = None
            self.in_td = False

        elif tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)

            self.current_row = None

    def handle_data(self, data):
        if self.in_td and self.current_cell is not None:
            self.current_cell.append(data)


# ============================================================
# DATA
# ============================================================

@dataclass
class Song:

    source: str = ""
    title: str = ""
    artist: str = ""
    genre: str = ""
    bpm: float = 0
    key: str = ""
    comment: str = ""
    lyrics: str = ""
    production: str = ""
    raw_text: str = ""

    beat_words: list[str] = None
    structure_words: list[str] = None
    style_tags: list[str] = None

    def __post_init__(self):

        if self.beat_words is None:
            self.beat_words = []

        if self.structure_words is None:
            self.structure_words = []

        if self.style_tags is None:
            self.style_tags = []


@dataclass
class GeneratedBeat:

    number: int
    title: str

    source_inspiration: list[str]

    genre_mix: list[str]
    bpm: int
    mood: str

    drums: str
    bass: str
    melody: str
    fx: str

    structure: list[str]

    surprise_count: int
    surprise_mechanics: list[str]

    suno_tags: list[str]

    suno_prompt: str
    lyrics: str = ""


# ============================================================
# VOCABULARY
# ============================================================

GENRES = [
    "German Boom Bap",
    "Golden Era Hip-Hop",
    "East Coast Hip-Hop",
    "Hardcore Hip-Hop",
    "Underground Rap",
    "Jazz Rap",
    "Soul Rap",
    "Alternative Hip-Hop",
    "Abstract Hip-Hop",
    "Trap",
    "Drill",
    "UK Drill",
    "Phonk",
    "Drift Phonk",
    "G-Funk",
    "Dirty South",
    "Crunk",
    "Rap Rock",
    "Trap Metal",
    "Afrotrap",
    "Electro Hip-Hop",
    "EDM",
    "House",
    "Techno",
    "Four-to-the-Floor",
]

DRUMS = [
    "dusty MPC drums with hard kick and cracking snare",
    "dry punchy Boom-Bap drums with vinyl swing",
    "polyrhythmic breakbeats with ghost snares",
    "hard Drill drums with syncopated hats",
    "distorted Phonk drums with aggressive cowbell",
    "heavy Trap drums with rapid hi-hat rolls",
    "funky West-Coast drums with bouncing percussion",
    "industrial drums with metallic transient hits",
    "minimal drums that explode into full breaks",
]

BASS = [
    "deep sliding 808 sub bass",
    "dirty analog bassline",
    "distorted sub bass with pitch dives",
    "funky electric bass with aggressive slides",
    "minimal sub bass that disappears before drops",
    "heavy sustained 808 with sudden bass cuts",
]

MELODIES = [
    "dusty chopped piano sample",
    "dark minor-key piano",
    "haunting Rhodes chords",
    "psychedelic vinyl sample",
    "cinematic brass stabs",
    "eerie choir textures",
    "warped jazz fragments",
    "minimal synth motif",
    "distorted guitar fragments",
    "München-night atmospheric piano",
]

MOODS = [
    "dreckig",
    "dunkel",
    "arrogant",
    "chaotisch",
    "cinematic",
    "bedrohlich",
    "humorvoll",
    "hypnotisch",
    "aggressiv",
    "euphorisch",
    "surreal",
    "underground",
    "psychedelisch",
]

SURPRISES = [
    "Fake Drop",
    "1-Bar Silence",
    "Unexpected Pause",
    "Beat Switch",
    "Flow Switch",
    "Half Time",
    "Double Time",
    "808 Dropout",
    "Drumless Section",
    "Acapella Break",
    "Scratch Break",
    "DJ Interruption",
    "Instrument Removal",
    "Bass Ambush",
    "Rhythm Collapse",
    "Call And Response",
    "Tempo Shift",
    "Key Change",
    "Reverse Hook",
    "False Ending",
    "Final Beat Mutation",
]

STRUCTURES = [

    [
        "[Cold Open]",
        "[Beat Drop]",
        "[Verse 1]",
        "[Micro Break]",
        "[Hook]",
        "[Fake Drop]",
        "[Beat Slam]",
        "[Verse 2]",
        "[Half Time]",
        "[Acapella Break]",
        "[Beat Switch]",
        "[Verse 3]",
        "[Final Hook]",
        "[Sudden Stop]",
    ],

    [
        "[DJ Cut Intro]",
        "[Verse 1]",
        "[Hook]",
        "[Scratch Break]",
        "[Verse 2]",
        "[808 Dropout]",
        "[Drumless Section]",
        "[Beat Return]",
        "[Flow Switch]",
        "[Final Hook]",
        "[False Ending]",
        "[Hidden Beat]",
    ],

    [
        "[Cold Open]",
        "[Minimal Beat]",
        "[Verse 1]",
        "[Hook]",
        "[Instrument Removal]",
        "[Verse 2]",
        "[Beat Switch]",
        "[Double Time]",
        "[Drum Break]",
        "[Half Time]",
        "[Final Hook]",
        "[Final Beat Mutation]",
    ],

    [
        "[Cinematic Intro]",
        "[Verse 1]",
        "[Mini Hook]",
        "[Verse 2]",
        "[Unexpected Pause]",
        "[Hook]",
        "[Genre Switch]",
        "[Verse 3]",
        "[Acapella Break]",
        "[Beat Slam]",
        "[Final Hook]",
        "[Sudden Stop]",
    ],

    [
        "[Hype Intro]",
        "[Hook]",
        "[Verse 1]",
        "[Call And Response]",
        "[Beat Break]",
        "[Verse 2]",
        "[Fake Drop]",
        "[Silence]",
        "[Beat Slam]",
        "[Double Time]",
        "[Final Hook]",
    ],
]


# ============================================================
# DETECTION VOCABULARY
# ============================================================

BEAT_WORDS = [
    "808",
    "bass",
    "sub",
    "kick",
    "snare",
    "drum",
    "beat",
    "bounce",
    "groove",
    "break",
    "drop",
    "switch",
    "flip",
    "drift",
    "glitch",
    "scratch",
    "cut",
    "tape-stop",
    "stomp",
    "double-time",
    "half-time",
    "syncopated",
    "polyrhythmic",
    "punch",
    "slam",
    "rumble",
    "roll",
    "loop",
    "peak",
]

STRUCTURE_WORDS = [
    "intro",
    "verse",
    "hook",
    "chorus",
    "bridge",
    "outro",
    "break",
    "drop",
    "switch",
    "acapella",
    "scratch",
    "instrumental",
    "silence",
    "half time",
    "double time",
    "tempo change",
    "key change",
]

STYLE_WORDS = [
    "boom bap",
    "trap",
    "drill",
    "phonk",
    "g-funk",
    "grime",
    "jazz rap",
    "underground",
    "hardcore",
    "dark",
    "cinematic",
    "melodic",
    "aggressive",
    "raw",
    "experimental",
]


# ============================================================
# HELPERS
# ============================================================

def clean(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def norm(text: str) -> str:
    return clean(text).lower()


def parse_bpm(value: str) -> float:

    if not value:
        return 0

    match = re.search(r"(\d+(?:\.\d+)?)", value)

    if not match:
        return 0

    try:
        bpm = float(match.group(1))

        if 30 <= bpm <= 250:
            return bpm

    except ValueError:
        pass

    return 0


def find_column(headers, names):

    normalized = [norm(x) for x in headers]

    for name in names:

        name = norm(name)

        for i, header in enumerate(normalized):

            if name == header:
                return i

    return None


# ============================================================
# HTML DISCOVERY
# ============================================================

def discover_html(root: Path):

    return sorted(
        root.rglob("*.html"),
        key=lambda p: str(p).lower()
    )


# ============================================================
# HTML SONG PARSER
# ============================================================

def parse_html_file(path: Path):

    try:
        raw = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )
    except Exception:
        return []

    parser = TableParser()
    parser.feed(raw)

    if not parser.rows:
        return []

    header_idx = None
    headers = []

    for i, row in enumerate(parser.rows):

        low = [norm(x) for x in row]

        if (
            "title" in low
            and ("artist" in low or "time" in low)
        ):
            header_idx = i
            headers = row
            break

    if header_idx is None:
        return []

    title_idx = find_column(headers, ["title"])
    artist_idx = find_column(headers, ["artist"])
    bpm_idx = find_column(headers, ["bpm"])
    key_idx = find_column(headers, ["key", "key text"])
    genre_idx = find_column(headers, ["genre"])
    comment_idx = find_column(headers, ["comment"])
    lyrics_idx = find_column(headers, ["lyrics"])
    producer_idx = find_column(
        headers,
        ["producer", "production", "production notes"]
    )

    songs = []

    for row in parser.rows[header_idx + 1:]:

        def get(idx):
            if idx is not None and idx < len(row):
                return clean(row[idx])
            return ""

        title = get(title_idx)

        if not title:
            continue

        song = Song(
            source=str(path),
            title=title,
            artist=get(artist_idx),
            genre=get(genre_idx),
            bpm=parse_bpm(get(bpm_idx)),
            key=get(key_idx),
            comment=get(comment_idx),
            lyrics=get(lyrics_idx),
            production=get(producer_idx),
            raw_text=" ".join(row),
        )

        combined = " ".join([
            song.genre,
            song.comment,
            song.lyrics,
            song.production,
            song.raw_text,
        ])

        low = norm(combined)

        song.beat_words = [
            word
            for word in BEAT_WORDS
            if re.search(
                rf"(?<!\w){re.escape(word)}(?!\w)",
                low
            )
        ]

        song.structure_words = [
            word
            for word in STRUCTURE_WORDS
            if word in low
        ]

        song.style_tags = [
            word
            for word in STYLE_WORDS
            if word in low
        ]

        songs.append(song)

    return songs


# ============================================================
# CORPUS ANALYSIS
# ============================================================

def analyze_corpus(songs):

    bpm_values = [
        s.bpm
        for s in songs
        if s.bpm > 0
    ]

    genres = Counter()
    beats = Counter()
    structures = Counter()
    styles = Counter()

    for song in songs:

        if song.genre:
            genres[song.genre] += 1

        beats.update(song.beat_words)
        structures.update(song.structure_words)
        styles.update(song.style_tags)

    if bpm_values:
        bpm_center = int(round(median(bpm_values)))
    else:
        bpm_center = 140

    return {
        "songs": len(songs),
        "bpm_center": bpm_center,
        "genres": genres,
        "beats": beats,
        "structures": structures,
        "styles": styles,
    }



# ============================================================
# LYRIC ENGINE
# ============================================================

PUNCHLINE_STARTERS = [
    "Ich bin der", "Du bist nur ein", "Mein Flow ist", "Dein Style ist",
    "Check das aus:", "Hör genau zu,", "Wer ist der Boss?", "Guck mich an,",
]
PUNCHLINE_MIDDLES = [
    "unantastbar", "ein Witz", "auf einem anderen Level", "absoluter Müll",
    "die Definition von Perfektion", "nur eine Kopie", "das Ende deiner Karriere",
    "das Gesetz in diesem Game", "die Wahrheit in den Lyrics",
]
PUNCHLINE_ENDINGS = [
    "und du weißt es.", "Punkt.", "keine Diskussion.", "verstehst du?",
    "König von München.", "Oida, echt jetzt.", "game over.", "einfach nur krank.",
]

def generate_arrogant_line():
    return f"{random.choice(PUNCHLINE_STARTERS)} {random.choice(PUNCHLINE_MIDDLES)} {random.choice(PUNCHLINE_ENDINGS)}"

def generate_lyrics(songs, structure, mood, genre_mix):
    # Collect seeds from existing lyrics and comments
    seeds = []
    for s in songs:
        if s.lyrics: seeds.append(s.lyrics)
        if s.comment: seeds.append(s.comment)
    
    # Mix of original seeds and arrogant new lines
    lyrics_output = []
    
    for section in structure:
        # Create 2-4 lines per section
        num_lines = random.randint(2, 4)
        section_lines = []
        for _ in range(num_lines):
            if random.random() < 0.4 and seeds:
                # Use a fragment of an old lyric/comment
                seed = random.choice(seeds)
                # Take a random slice or the first line
                line = seed.split("\n")[0] if "\n" in seed else seed
                section_lines.append(line[:100] + "...")
            else:
                # Generate arrogant punchline
                section_lines.append(generate_arrogant_line())
        
        lyrics_output.append(f"{section}\n" + "\n".join(section_lines))
    
    return "\n\n".join(lyrics_output)


# ============================================================
# BPM ENGINE
# ============================================================

def generate_bpm(center, genre_mix):
    choices = [
        center - 10,
        center - 5,
        center,
        center + 5,
        center + 10,
        90,
        100,
        110,
        120,
        130,
        140,
        145,
        150,
        160,
        170,
    ]
    
    # EDM Limit: Four-to-the-floor / House / Techno not faster than 129
    edm_keywords = ["EDM", "House", "Techno", "Four-to-the-Floor"]
    is_edm = any(k in " ".join(genre_mix) for k in edm_keywords)
    
    choices = [
        max(70, min(180, x))
        for x in choices
    ]
    
    if is_edm:
        choices = [min(129, x) for x in choices]
        
    return random.choice(choices)


# ============================================================
# GENRE MUTATION
# ============================================================

def generate_genre_mix(corpus):

    corpus_genres = list(corpus["genres"].keys())

    pool = list(dict.fromkeys(
        corpus_genres + GENRES
    ))

    if len(pool) < 2:
        return random.sample(GENRES, 2)

    return random.sample(pool, 2)


# ============================================================
# SURPRISE ENGINE
# ============================================================

def generate_surprises():

    count = random.choice([
        3,
        4,
        5,
        6,
        7,
    ])

    return random.sample(
        SURPRISES,
        min(count, len(SURPRISES))
    )


# ============================================================
# STRUCTURE MUTATION
# ============================================================

def mutate_structure():

    base = random.choice(STRUCTURES).copy()

    surprises = generate_surprises()

    insertion_points = []

    for i in range(1, len(base)):

        if random.random() < 0.40:
            insertion_points.append(i)

    offset = 0

    for i in insertion_points:

        surprise = random.choice(surprises)

        base.insert(
            i + offset,
            f"[{surprise}]"
        )

        offset += 1

    # Nicht völlig ausufern lassen
    return base[:24]


# ============================================================
# SUNO TAG ENGINE
# ============================================================

def generate_suno_tags(
    genre_mix,
    mood,
    drums,
    bass,
    melody,
    surprises,
):

    tags = [
        f"[{genre_mix[0]}]",
        f"[{genre_mix[1]}]",
        f"[{mood.title()}]",
        "[Hard Punchy Drums]",
        "[Dynamic Arrangement]",
        "[Male Rap Vocals]",
        "[Dense Multisyllabic Flow]",
        "[Internal Rhymes]",
    ]

    if "808" in bass.lower():
        tags.append("[808 Sub Bass]")

    if "scratch" in " ".join(surprises).lower():
        tags.append("[Turntablism]")

    if "Beat Switch" in surprises:
        tags.append("[Beat Switch]")

    if "Flow Switch" in surprises:
        tags.append("[Flow Switch]")

    if "Half Time" in surprises:
        tags.append("[Half Time]")

    if "Double Time" in surprises:
        tags.append("[Double Time]")

    if "Fake Drop" in surprises:
        tags.append("[Fake Drop]")

    if "Silence" in " ".join(surprises):
        tags.append("[Unexpected Silence]")

    if "808 Dropout" in surprises:
        tags.append("[808 Dropout]")

    if "Acapella Break" in surprises:
        tags.append("[Acapella Break]")

    if "Final Beat Mutation" in surprises:
        tags.append("[Final Beat Mutation]")

    tags.extend([
        "[Beat Breaks]",
        "[Unexpected Transitions]",
        "[Cinematic Drops]",
        "[Aggressive Energy]",
    ])

    # Deduplizieren
    return list(dict.fromkeys(tags))


# ============================================================
# PROMPT ENGINE
# ============================================================

def generate_prompt(
    genre_mix,
    bpm,
    mood,
    drums,
    bass,
    melody,
    surprises,
    structure,
):

    structure_text = " → ".join(structure)

    surprise_text = ", ".join(surprises)

    tags = generate_suno_tags(
        genre_mix,
        mood,
        drums,
        bass,
        melody,
        surprises,
    )

    tag_text = " ".join(tags)

    return (
        f"{tag_text}\n\n"
        f"Deutschsprachiger Hip-Hop-Beat mit {bpm} BPM, "
        f"Mix aus {genre_mix[0]} und {genre_mix[1]}. "
        f"Stimmung: {mood}. "
        f"{drums}. "
        f"{bass}. "
        f"{melody}. "
        f"Dynamische, überraschende Arrangementstruktur "
        f"mit echten Spannungswechseln statt monotonem Loop. "
        f"Verwende: {surprise_text}. "
        f"Die Überraschungen sollen musikalisch vorbereitet, "
        f"aber nicht vorhersehbar sein. "
        f"Punchy Drums, tiefer Bass, aggressive Transienten, "
        f"deutliche Flow-Pockets und kurze extreme Breaks. "
        f"Songstruktur: {structure_text}. "
        f"Finale mit maximaler Energie und anschließend "
        f"hartem überraschendem Stop."
    )


# ============================================================
# TITLE ENGINE
# ============================================================

TITLE_WORDS_1 = [
    "OIDA",
    "BASS",
    "BREAK",
    "DRIFT",
    "FLIP",
    "ROTOr",
    "BAM",
    "089",
    "MINGA",
    "TUNNEL",
    "BEAT",
    "PRALL",
    "SWITCH",
    "KRAWALL",
]

TITLE_WORDS_2 = [
    "Mutation",
    "Protocol",
    "Ambush",
    "Drift",
    "Collapse",
    "Overdrive",
    "Maschine",
    "Achterbahn",
    "Flip",
    "Break",
    "Attack",
    "Chaos",
    "Reloaded",
    "Explosion",
]


def generate_title():

    return (
        random.choice(TITLE_WORDS_1)
        + " "
        + random.choice(TITLE_WORDS_2)
    )


# ============================================================
# BEAT GENERATOR
# ============================================================

def generate_beat(number, songs, corpus):

    if songs:

        inspiration = random.sample(
            songs,
            min(random.randint(2, 4), len(songs))
        )

        inspiration_titles = [
            s.title
            for s in inspiration
        ]

    else:
        inspiration_titles = []

    genre_mix = generate_genre_mix(corpus)

    bpm = generate_bpm(
        corpus["bpm_center"],
        genre_mix
    )

    mood = random.choice(MOODS)

    drums = random.choice(DRUMS)

    bass = random.choice(BASS)

    melody = random.choice(MELODIES)

    fx = random.choice([
        "vinyl crackle, DJ cuts and tape-stop FX",
        "industrial impacts and glitch transitions",
        "reverse cymbals, sub drops and stereo scratches",
        "crowd chants, vocal cuts and cinematic impacts",
        "analog tape warble with sudden digital glitches",
    ])

    surprises = generate_surprises()

    structure = mutate_structure()

    tags = generate_suno_tags(
        genre_mix,
        mood,
        drums,
        bass,
        melody,
        surprises,
    )

    prompt = generate_prompt(
        genre_mix,
        bpm,
        mood,
        drums,
        bass,
        melody,
        surprises,
        structure,
    )

    return GeneratedBeat(
        number=number,
        title=generate_title(),
        source_inspiration=inspiration_titles,
        genre_mix=genre_mix,
        bpm=bpm,
        mood=mood,
        drums=drums,
        bass=bass,
        melody=melody,
        fx=fx,
        structure=structure,
        surprise_count=len(surprises),
        lyrics=generate_lyrics(songs, structure, mood, genre_mix),
        surprise_mechanics=surprises,
        suno_tags=tags,
        suno_prompt=prompt,
    )


# ============================================================
# HTML OUTPUT
# ============================================================

def html_escape(value):

    return html.escape(str(value))


def create_html(beats, corpus, filename):

    sections = []

    sections.append("""
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">

<title>OIDA NEXT LEVEL BEAT FORGE</title>

<style>

body {
    font-family: Arial, sans-serif;
    background: #111;
    color: #eee;
    margin: 0;
    padding: 30px;
}

h1 {
    font-size: 34px;
}

.beat {
    background: #1d1d1d;
    border: 1px solid #444;
    border-radius: 14px;
    padding: 24px;
    margin: 24px 0;
}

.title {
    font-size: 26px;
    font-weight: bold;
}

.meta {
    color: #bbb;
    margin: 8px 0 20px;
}

.tags span {
    display: inline-block;
    background: #333;
    padding: 5px 9px;
    border-radius: 8px;
    margin: 3px;
}

.structure {
    line-height: 1.8;
    font-family: monospace;
}

.prompt {
    white-space: pre-wrap;
    background: #090909;
    border: 1px solid #333;
    padding: 16px;
    border-radius: 10px;
}

.surprise {
    color: #fff;
    font-weight: bold;
}

</style>
</head>

<body>

<h1>🔥 OIDA NEXT LEVEL BEAT FORGE</h1>
""")

    sections.append(
        f"""
<p>
Analysierte Songs:
<b>{corpus['songs']}</b>
<br>
Corpus-BPM-Zentrum:
<b>{corpus['bpm_center']}</b>
</p>
"""
    )

    for beat in beats:

        tags = "".join(
            f"<span>{html_escape(tag)}</span>"
            for tag in beat.suno_tags
        )

        structure = "<br>".join(
            html_escape(x)
            for x in beat.structure
        )

        surprises = ", ".join(
            html_escape(x)
            for x in beat.surprise_mechanics
        )

        inspiration = ", ".join(
            html_escape(x)
            for x in beat.source_inspiration
        )

        sections.append(
            f"""
<div class="beat">

<div class="title">
{beat.number:03d} — {html_escape(beat.title)}
</div>

<div class="meta">
BPM: <b>{beat.bpm}</b> |
Mood: <b>{html_escape(beat.mood)}</b> |
Surprises: <b>{beat.surprise_count}</b>
</div>

<p>
<b>Genre Mutation:</b>
{html_escape(" × ".join(beat.genre_mix))}
</p>

<p>
<b>Inspiration aus Archiv:</b>
{inspiration or "Corpus allgemein"}
</p>

<p>
<b>Drums:</b> {html_escape(beat.drums)}
<br>
<b>Bass:</b> {html_escape(beat.bass)}
<br>
<b>Melodie:</b> {html_escape(beat.melody)}
<br>
<b>FX:</b> {html_escape(beat.fx)}
</p>

<h3>💥 Überraschungsmechaniken</h3>

<p class="surprise">
{surprises}
</p>

<h3>🧬 Arrangement</h3>

<div class="structure">
{structure}
</div>

<h3>🎛️ Suno 4.5 Style Tags</h3>

<div class="tags">
{tags}
</div>

<h3>📝 Lyrics</h3>
<div class="prompt">
{html_escape(beat.lyrics)}
</div>

<h3>🔥 Suno Prompt</h3>

<div class="prompt">
{html_escape(beat.suno_prompt)}
</div>

</div>
"""
        )

    sections.append("""
</body>
</html>
""")

    Path(filename).write_text(
        "\n".join(sections),
        encoding="utf-8"
    )


# ============================================================
# JSON OUTPUT
# ============================================================

def create_json(beats, corpus, filename):

    data = {
        "generator": "OIDA NEXT LEVEL BEAT FORGE",
        "corpus": {
            "songs": corpus["songs"],
            "bpm_center": corpus["bpm_center"],
            "genres": corpus["genres"].most_common(),
            "beat_terms": corpus["beats"].most_common(),
            "structure_terms": corpus["structures"].most_common(),
            "style_terms": corpus["styles"].most_common(),
        },
        "beats": [
            asdict(beat)
            for beat in beats
        ],
    }

    Path(filename).write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ============================================================
# TEXT OUTPUT
# ============================================================

def create_txt(beats, filename):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        for beat in beats:

            f.write(
                "\n"
                + "=" * 80
                + "\n"
            )

            f.write(
                f"{beat.number:03d} — {beat.title}\n"
            )

            f.write(
                f"BPM: {beat.bpm}\n"
            )

            f.write(
                f"GENRE: {' × '.join(beat.genre_mix)}\n"
            )

            f.write(
                f"MOOD: {beat.mood}\n\n"
            )

            f.write(
                "SURPRISES:\n"
            )

            for x in beat.surprise_mechanics:
                f.write(
                    f"  - {x}\n"
                )

            f.write(
                "\nSTRUCTURE:\n"
            )

            for x in beat.structure:
                f.write(
                    f"  {x}\n"
                )

            f.write(
                "\nSUNO TAGS:\n"
            )

            f.write(
                " ".join(beat.suno_tags)
                + "\n\n"
            )

            f.write(
                "LYRICS:\n"
            )
            f.write(beat.lyrics + "\n\n")
            f.write(
                "SUNO PROMPT:\n"
            )

            f.write(
                beat.suno_prompt
                + "\n"
            )


# ============================================================
# VERSIONING
# ============================================================

def next_version(out_dir: Path):

    out_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    existing = list(
        out_dir.glob("beats_v*.html")
    )

    versions = []

    for file in existing:

        match = re.search(
            r"beats_v(\d+)\.html$",
            file.name
        )

        if match:
            versions.append(
                int(match.group(1))
            )

    if not versions:
        return 1

    return max(versions) + 1


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="OIDA Next Level Beat Forge"
    )

    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Root-Verzeichnis mit HTML-Dateien"
    )

    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Output-Verzeichnis"
    )

    parser.add_argument(
        "--count",
        type=int,
        default=25,
        help="Anzahl neuer Beats"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Reproduzierbarer Random Seed"
    )

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    root = Path(args.root)
    out = Path(args.out)

    print()
    print("=" * 70)
    print("🔥 OIDA NEXT LEVEL BEAT FORGE")
    print("=" * 70)
    print()

    print(
        f"📂 Scanne rekursiv: {root}"
    )

    html_files = discover_html(root)

    print(
        f"📄 HTML-Dateien gefunden: {len(html_files)}"
    )

    songs = []

    for file in html_files:

        parsed = parse_html_file(file)

        songs.extend(parsed)

    print(
        f"🎧 Songs extrahiert: {len(songs)}"
    )

    if not songs:

        print(
            "⚠ Keine Songs erkannt."
        )

        return

    corpus = analyze_corpus(
        songs
    )

    print(
        f"🎚 BPM-Zentrum: {corpus['bpm_center']}"
    )

    print(
        "🎼 Top Genres:"
    )

    for genre, count in corpus["genres"].most_common(8):

        print(
            f"   {genre}: {count}"
        )

    print()

    print(
        f"⚙ Erzeuge {args.count} neue Beat-Konzepte..."
    )

    beats = []

    for i in range(
        1,
        args.count + 1
    ):

        beat = generate_beat(
            i,
            songs,
            corpus
        )

        beats.append(beat)

        print(
            f"   {i:03d} | "
            f"{beat.title:<28} | "
            f"{beat.bpm} BPM | "
            f"{len(beat.surprise_mechanics)} Überraschungen"
        )

    version = next_version(
        out
    )

    base = out / f"beats_v{version:03d}"

    html_file = base.with_suffix(".html")
    json_file = base.with_suffix(".json")
    txt_file = base.with_suffix(".txt")

    create_html(
        beats,
        corpus,
        html_file
    )

    create_json(
        beats,
        corpus,
        json_file
    )

    create_txt(
        beats,
        txt_file
    )

    print()
    print("=" * 70)
    print("✅ FERTIG")
    print("=" * 70)

    print(
        f"🌐 HTML: {html_file}"
    )

    print(
        f"🧠 JSON: {json_file}"
    )

    print(
        f"📝 TXT:  {txt_file}"
    )

    print()
    print(
        "Keine Input-Datei wurde überschrieben."
    )


if __name__ == "__main__":
    main()