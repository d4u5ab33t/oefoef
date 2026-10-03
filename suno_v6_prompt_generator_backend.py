#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUNO v6 / v7 Prompt Generator Backend (OIDAHEIM NATIVE GENOME)
Semantic Index + Traktor Tracklist Vector Scanner + Qwen / OpenRouter Integration

Features:
- 50+ Hip-Hop Styles with specific sound signatures, tempos, structures & Suno 4.5/v6 tags
- 8 Core Song Structures (Klassischer Rap-Banger, 90s Boom-Bap, Beat-Switch-Monster, etc.)
- Hierarchical Tag Architecture: [Genre] [Mood] [Tempo] [Drums] [Bass] [Instruments] [Vocal Style] [Flow] [Structure] [Production] [Transitions] [FX]
- Oidaheim Urban & Quantum-Lore Lyrics Bank (Munich Underground, JVA Stadelheim, Schwabing, 089, 420 Weed Beats)
- Traktor HTML / NML Semantic & Vector Scanner across J:\\Oidasheim\\Musik\\FAVs\\**\\*.html
- OpenRouter / Qwen LLM Backend Integration
"""
import glob
import html
import json
import os
import re
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Configuration Constants ──────────────────────────────────────────────────
DEFAULT_DB_PATH = os.environ.get("SUNO_PROMPT_DB", "suno_prompt_index.db")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")
FAVS_ROOT = Path(os.environ.get("OIDASHEIM_FAVS_ROOT", r"J:\Oidasheim\Musik\FAVs"))

# ── 50 Hip-Hop Styles Reference Catalog ──────────────────────────────────────
HIPHOP_STYLES_CATALOG = [
    {
        "style": "Boom Bap",
        "sound": "harte Drums, Sample-Loops, Vinyl, MPC, Scratches",
        "structure": "[DJ Intro] → [Verse 1] → [Hook] → [Verse 2] → [Scratch Break] → [Verse 3] → [Hook] → [Outro]",
        "tags": ["[90s Boom Bap]", "[Dusty Samples]", "[Hard Drums]", "[Vinyl Crackle]", "[Turntablism]"],
        "tempo_range": "88-96",
    },
    {
        "style": "Golden Era Hip-Hop",
        "sound": "Sampling, Funk/Jazz, komplexe Drums",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Bridge] → [Hook]",
        "tags": ["[Golden Era Hip-Hop]", "[Sample-Based]", "[Classic Breakbeat]", "[DJ Scratches]"],
        "tempo_range": "90-100",
    },
    {
        "style": "East Coast Rap",
        "sound": "trocken, düster, lyrisch, aggressive Drums",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Hook] → [Outro]",
        "tags": ["[East Coast Hip-Hop]", "[Dark Boom Bap]", "[Punchy Drums]", "[Dense Lyrics]"],
        "tempo_range": "88-95",
    },
    {
        "style": "West Coast Rap",
        "sound": "Funk, G-Funk, Synths, Basslines",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2] → [Hook]",
        "tags": ["[West Coast Hip-Hop]", "[G-Funk]", "[Funky Bass]", "[Talkbox]", "[Smooth Synths]"],
        "tempo_range": "92-104",
    },
    {
        "style": "Gangsta Rap",
        "sound": "harte Basslines, Street Narratives, dominante Delivery",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Hook] → [Outro]",
        "tags": ["[Gangsta Rap]", "[Hard-Hitting]", "[Street Narrative]", "[Heavy Bass]", "[Aggressive Flow]"],
        "tempo_range": "90-100",
    },
    {
        "style": "Hardcore Hip-Hop",
        "sound": "maximal aggressiv, düster, harte Drums",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Beat Break] → [Verse 3] → [Outro]",
        "tags": ["[Hardcore Hip-Hop]", "[Aggressive Rap]", "[Heavy Drums]", "[Dark Atmosphere]"],
        "tempo_range": "90-110",
    },
    {
        "style": "Battle Rap",
        "sound": "Punchlines, Reimketten, direkte Angriffe",
        "structure": "[Intro] → [Verse 1] → [Verse 2] → [Hook/Chant] → [Verse 3] → [Outro]",
        "tags": ["[Battle Rap]", "[Punchline Heavy]", "[Complex Rhymes]", "[Aggressive Delivery]"],
        "tempo_range": "90-105",
    },
    {
        "style": "Freestyle Rap",
        "sound": "spontan, wechselnde Flows, lockere Struktur",
        "structure": "[Intro] → [Verse 1] → [Verse 2] → [Freestyle Outro]",
        "tags": ["[Freestyle Rap]", "[Improvised Flow]", "[Off-The-Top]", "[Dynamic Delivery]"],
        "tempo_range": "90-115",
    },
    {
        "style": "Conscious Rap",
        "sound": "Gesellschaft, Politik, Philosophie, Storytelling",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Bridge] → [Hook]",
        "tags": ["[Conscious Hip-Hop]", "[Thought-Provoking]", "[Storytelling]", "[Soulful Samples]"],
        "tempo_range": "85-98",
    },
    {
        "style": "Jazz Rap",
        "sound": "Jazz-Samples, Kontrabass, Rhodes, komplexe Drums",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Instrumental] → [Verse 2] → [Outro]",
        "tags": ["[Jazz Rap]", "[Live Jazz]", "[Rhodes]", "[Double Bass]", "[Complex Drums]"],
        "tempo_range": "85-95",
    },
    {
        "style": "Soul Rap",
        "sound": "warme Soul-Samples, emotionale Hooks",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Hook] → [Outro]",
        "tags": ["[Soulful Hip-Hop]", "[Soul Samples]", "[Warm Vocals]", "[Emotional Hook]"],
        "tempo_range": "82-94",
    },
    {
        "style": "Alternative Hip-Hop",
        "sound": "experimentell, ungewöhnliche Sounds",
        "structure": "[Intro] → [Verse 1] → [Switch] → [Verse 2] → [Experimental Outro]",
        "tags": ["[Alternative Hip-Hop]", "[Experimental]", "[Unconventional Structure]", "[Genre Fusion]"],
        "tempo_range": "90-130",
    },
    {
        "style": "Abstract Hip-Hop",
        "sound": "surreal, abstrakt, fragmentierte Beats",
        "structure": "[Intro] → [Verse 1] → [Beat Switch] → [Verse 2] → [Outro]",
        "tags": ["[Abstract Hip-Hop]", "[Experimental Beats]", "[Surreal]", "[Off-Kilter Rhythm]"],
        "tempo_range": "80-105",
    },
    {
        "style": "Underground Rap",
        "sound": "roh, DIY, wenig Mainstream-Politur",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Hook]",
        "tags": ["[Underground Hip-Hop]", "[Raw Production]", "[Lo-Fi]", "[Dusty Drums]"],
        "tempo_range": "88-100",
    },
    {
        "style": "Lo-Fi Hip-Hop",
        "sound": "gedämpft, warm, Vinyl, entspannt",
        "structure": "[Intro] → [Loop] → [Variation] → [Loop] → [Outro]",
        "tags": ["[Lo-Fi Hip-Hop]", "[Chill]", "[Vinyl Hiss]", "[Warm Samples]", "[Relaxed Beat]"],
        "tempo_range": "70-85",
    },
    {
        "style": "Cloud Rap",
        "sound": "schwebende Pads, Autotune, atmosphärisch",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2] → [Outro]",
        "tags": ["[Cloud Rap]", "[Ethereal]", "[Dreamy Pads]", "[Heavy 808]", "[Autotune]"],
        "tempo_range": "120-140",
    },
    {
        "style": "Trap",
        "sound": "808s, Hi-Hats, Rolls, Subbass",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2] → [Hook]",
        "tags": ["[Trap]", "[808 Sub Bass]", "[Rapid Hi-Hats]", "[Dark Synths]", "[Hard Drums]"],
        "tempo_range": "130-150",
    },
    {
        "style": "Drill",
        "sound": "Sliding 808s, düstere Melodien, Stop/Start",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Hook] → [Outro]",
        "tags": ["[Drill]", "[Sliding 808]", "[Dark Piano]", "[Staccato Flow]", "[Heavy Bass]"],
        "tempo_range": "138-145",
    },
    {
        "style": "UK Drill",
        "sound": "schnelle Hats, tiefe Slides, kalte Atmosphäre",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Beat Switch] → [Verse 3]",
        "tags": ["[UK Drill]", "[Sliding 808s]", "[Cold Piano]", "[Dark Atmosphere]", "[Syncopated Flow]"],
        "tempo_range": "140-144",
    },
    {
        "style": "NY Drill",
        "sound": "aggressive 808s, schnelle Flows",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2]",
        "tags": ["[NY Drill]", "[Aggressive 808]", "[Dark Melody]", "[Rapid Flow]"],
        "tempo_range": "140-148",
    },
    {
        "style": "Trap Metal",
        "sound": "Trap + Metal, Screams, verzerrte Bässe",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Breakdown] → [Hook]",
        "tags": ["[Trap Metal]", "[Distorted 808]", "[Heavy Guitar]", "[Screamed Vocals]", "[Breakdown]"],
        "tempo_range": "130-160",
    },
    {
        "style": "Phonk",
        "sound": "Memphis-Samples, Cowbells, distorted bass",
        "structure": "[Intro] → [Loop] → [Verse 1] → [Drop] → [Loop]",
        "tags": ["[Phonk]", "[Memphis Rap Samples]", "[Cowbell]", "[Distorted Bass]", "[Dark]"],
        "tempo_range": "115-135",
    },
    {
        "style": "Drift Phonk",
        "sound": "aggressive Cowbells, distortion, schnelle Energie",
        "structure": "[Intro] → [Build] → [Drop] → [Switch] → [Drop]",
        "tags": ["[Drift Phonk]", "[Distorted Cowbells]", "[Aggressive Bass]", "[Racing Energy]", "[Beat Drop]"],
        "tempo_range": "145-165",
    },
    {
        "style": "Memphis Rap",
        "sound": "Lo-Fi, Horror-Samples, düster",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Outro]",
        "tags": ["[Memphis Rap]", "[Dark Lo-Fi]", "[Horror Samples]", "[Raw Vocals]"],
        "tempo_range": "120-140",
    },
    {
        "style": "Southern Hip-Hop",
        "sound": "schwere Basslines, Swing, langsamer Groove",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2]",
        "tags": ["[Southern Hip-Hop]", "[Heavy Bass]", "[Southern Bounce]", "[808s]"],
        "tempo_range": "75-90",
    },
    {
        "style": "Crunk",
        "sound": "maximaler Party-Energy, Chants",
        "structure": "[Intro] → [Chant] → [Verse 1] → [Hook] → [Verse 2] → [Hook]",
        "tags": ["[Crunk]", "[Hype Chant]", "[Aggressive Bass]", "[Party Energy]"],
        "tempo_range": "100-115",
    },
    {
        "style": "Dirty South",
        "sound": "Bass, Bounce, Southern Slang",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2] → [Outro]",
        "tags": ["[Dirty South]", "[Southern Bounce]", "[Heavy 808]", "[Catchy Hook]"],
        "tempo_range": "80-95",
    },
    {
        "style": "Miami Bass",
        "sound": "extrem basslastig, schnelle Party-Rhythmen",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Dance Break]",
        "tags": ["[Miami Bass]", "[Deep Bass]", "[Electro Drums]", "[Party Rap]"],
        "tempo_range": "125-135",
    },
    {
        "style": "Electro Hip-Hop",
        "sound": "Synths, Drum Machines, Breakbeats",
        "structure": "[Intro] → [Beat] → [Verse 1] → [Hook] → [Beat Break] → [Verse 2]",
        "tags": ["[Electro Hip-Hop]", "[Synth Bass]", "[Drum Machine]", "[Breakbeat]"],
        "tempo_range": "118-128",
    },
    {
        "style": "Turntablism",
        "sound": "Scratch-Solos, Cuts, DJ als Instrument",
        "structure": "[DJ Intro] → [Verse 1] → [Scratch Break] → [Verse 2] → [DJ Outro]",
        "tags": ["[Turntablism]", "[Vinyl Scratches]", "[DJ Cuts]", "[Breakbeats]", "[Scratch Solo]"],
        "tempo_range": "90-105",
    },
    {
        "style": "Rap Rock",
        "sound": "Rap + Gitarren, Live Drums",
        "structure": "[Intro] → [Verse 1] → [Chorus] → [Verse 2] → [Guitar Break] → [Chorus]",
        "tags": ["[Rap Rock]", "[Heavy Guitar]", "[Live Drums]", "[Crossover]"],
        "tempo_range": "90-120",
    },
    {
        "style": "Rap Metal",
        "sound": "Metal-Riffs, aggressive Vocals",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Breakdown] → [Verse 2] → [Hook]",
        "tags": ["[Rap Metal]", "[Heavy Riffs]", "[Aggressive Rap]", "[Breakdown]"],
        "tempo_range": "95-135",
    },
    {
        "style": "Pop Rap",
        "sound": "extrem eingängige Hooks",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2] → [Hook] → [Outro]",
        "tags": ["[Pop Rap]", "[Catchy Hook]", "[Polished Production]", "[Radio Ready]"],
        "tempo_range": "95-115",
    },
    {
        "style": "Melodic Rap",
        "sound": "gesungene Hooks, Rap-Verses",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2] → [Hook]",
        "tags": ["[Melodic Rap]", "[Sung Hook]", "[Emotional Vocals]", "[808 Bass]"],
        "tempo_range": "110-135",
    },
    {
        "style": "Emo Rap",
        "sound": "melancholisch, introspektiv",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Bridge] → [Hook]",
        "tags": ["[Emo Rap]", "[Melancholic]", "[Emotional Hook]", "[Atmospheric]"],
        "tempo_range": "115-130",
    },
    {
        "style": "Horrorcore",
        "sound": "Horror, düstere Samples, aggressive Delivery",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Breakdown] → [Outro]",
        "tags": ["[Horrorcore]", "[Dark Atmosphere]", "[Horror Samples]", "[Distorted Bass]"],
        "tempo_range": "85-110",
    },
    {
        "style": "Comedy Rap",
        "sound": "Humor, absurdes Storytelling, Punchlines",
        "structure": "[Intro] → [Setup] → [Verse 1] → [Punchline Hook] → [Verse 2] → [Outro]",
        "tags": ["[Comedy Rap]", "[Humorous]", "[Punchline Heavy]", "[Quirky Adlibs]"],
        "tempo_range": "90-110",
    },
    {
        "style": "Nerdcore",
        "sound": "Gaming, Technik, Internet, Pop Culture",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Bridge] → [Hook]",
        "tags": ["[Nerdcore]", "[Geek Culture]", "[Rapid Lyrics]", "[Playful Samples]"],
        "tempo_range": "95-115",
    },
    {
        "style": "Storytelling Rap",
        "sound": "filmische Handlung, Charaktere, Perspektivwechsel",
        "structure": "[Cinematic Intro] → [Verse 1] → [Hook] → [Verse 2] → [Climax] → [Final Hook] → [Outro]",
        "tags": ["[Storytelling Rap]", "[Cinematic]", "[Narrative]", "[Character Voices]"],
        "tempo_range": "85-98",
    },
    {
        "style": "Political Rap",
        "sound": "Protest, Gesellschaft, Analyse",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Bridge] → [Final Hook]",
        "tags": ["[Political Hip-Hop]", "[Conscious]", "[Powerful Lyrics]", "[Cinematic]"],
        "tempo_range": "88-100",
    },
    {
        "style": "Christian Hip-Hop",
        "sound": "Glauben + Rap",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Bridge] → [Hook]",
        "tags": ["[Christian Hip-Hop]", "[Inspirational]", "[Soulful Hook]", "[Uplifting]"],
        "tempo_range": "85-100",
    },
    {
        "style": "Afrotrap",
        "sound": "Afro-Rhythmik + Trap",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Dance Break] → [Hook]",
        "tags": ["[Afrotrap]", "[Afrobeats Groove]", "[Trap 808]", "[Percussion]"],
        "tempo_range": "105-120",
    },
    {
        "style": "Dancehall Rap",
        "sound": "Caribbean Groove, Dancehall-Rhythmus",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Chant] → [Verse 2] → [Hook]",
        "tags": ["[Dancehall Hip-Hop]", "[Caribbean Groove]", "[Dancehall Bounce]"],
        "tempo_range": "95-108",
    },
    {
        "style": "Reggae Rap",
        "sound": "Offbeat, Dub Bass, Reggae",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Dub Break] → [Verse 2] → [Outro]",
        "tags": ["[Reggae Rap]", "[Dub Bass]", "[Offbeat Guitar]", "[Reggae Groove]"],
        "tempo_range": "75-90",
    },
    {
        "style": "Latin Hip-Hop",
        "sound": "Latin Percussion, spanische Vocals",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Percussion Break] → [Verse 2] → [Hook]",
        "tags": ["[Latin Hip-Hop]", "[Latin Percussion]", "[Spanish Rap]", "[Dance Groove]"],
        "tempo_range": "95-115",
    },
    {
        "style": "Boom Bap Deutschrap",
        "sound": "deutsche Punchlines, Samples, trockene Drums",
        "structure": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Beat Switch] → [Verse 3] → [Hook]",
        "tags": ["[German Boom Bap]", "[Punchline Rap]", "[Dusty Samples]", "[Hard Drums]"],
        "tempo_range": "88-96",
    },
    {
        "style": "Deutschrap Straße",
        "sound": "808, dunkle Synths, direkte Lyrics",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2] → [Outro]",
        "tags": ["[German Street Rap]", "[Dark 808]", "[Aggressive Flow]", "[Street Energy]"],
        "tempo_range": "90-140",
    },
    {
        "style": "Deutschrap Pop",
        "sound": "Rap + große Melodie",
        "structure": "[Intro] → [Hook] → [Verse 1] → [Pre-Hook] → [Hook] → [Verse 2] → [Hook]",
        "tags": ["[German Pop Rap]", "[Huge Hook]", "[Melodic Vocals]", "[Radio Ready]"],
        "tempo_range": "98-125",
    },
    {
        "style": "Deutschrap Underground",
        "sound": "dreckig, experimentell, eigenständig",
        "structure": "[Intro] → [Verse 1] → [Switch] → [Verse 2] → [Hook] → [Outro]",
        "tags": ["[German Underground Rap]", "[Raw]", "[Experimental]", "[Dusty Beat]"],
        "tempo_range": "88-135",
    },
    {
        "style": "Half-Time Trap Boom-Bap Hybrid",
        "sound": "Dusty Vinyl Saturation, Clean Melancholic Guitar, Warm Syncopated Live Bass, Surging Drops",
        "structure": "[Intro] → [Verse 1] → [420 Expansion Chant] → [Hook] → [Verse 2 - Double-Time Shift] → [Outro]",
        "tags": ["[Half-Time Trap]", "[Boom-Bap Hybrid]", "[Dusty Vinyl Saturation]", "[Clean Melancholic Guitar]", "[Warm Syncopated Live Bass]", "[Surging Drops]", "[[Fake SFX: Tunnel-Blick-Trick Tick Tick & Sub-Bass Rumble]]", "[[Melodic: Fake Hendrix Wah Guitar Motif & Clean Melancholy Riff]]"],
        "tempo_range": "116-122",
    },
]

# ── 8 Core Song Structures ───────────────────────────────────────────────────
SONG_STRUCTURES = {
    "1. Klassischer Rap-Banger": {
        "sequence": "[Intro] → [Verse 1] → [Hook] → [Verse 2] → [Hook] → [Outro]",
        "tags": ["[Classic Structure]", "[Radio Ready]", "[Catchy Hook]"],
        "desc": "Sofort verstaendlich, Hook bleibt haengen, klassischer Single-Aufbau.",
    },
    "2. 90s Boom-Bap": {
        "sequence": "[DJ Intro] → [Verse 1] → [Hook] → [Verse 2] → [Scratch Break] → [Verse 3] → [Hook] → [Outro]",
        "tags": ["[Dusty Samples]", "[Vinyl Crackle]", "[Hard Drums]", "[DJ Scratches]", "[Punchline Rap]"],
        "desc": "Authentischer 90er Sound mit DJ Cuts und klassischem 3-Verse Aufbau.",
    },
    "3. Beat-Switch-Monster": {
        "sequence": "[Intro] → [Verse 1] → [Hook] → [Beat Switch] → [Verse 2] → [Beat Switch] → [Final Hook]",
        "tags": ["[Beat Switch]", "[Tempo Change]", "[Key Change]", "[Flow Switch]", "[Double Time]", "[Half Time]"],
        "desc": "Track veraendert mehrfach seinen Charakter statt vier Minuten denselben Loop zu fahren.",
    },
    "4. Cinematic Story": {
        "sequence": "[Cinematic Intro] → [Verse 1] → [Hook] → [Verse 2] → [Bridge] → [Climax] → [Final Hook] → [Outro]",
        "tags": ["[Cinematic]", "[Storytelling]", "[Sound Design]", "[Character Voices]", "[Dramatic Build]"],
        "desc": "Filmischer Spannungsbogen mit emotionalem Hoehepunkt und Sound-Effekten.",
    },
    "5. Freestyle / Cypher": {
        "sequence": "[DJ Intro] → [MC 1] → [MC 2] → [MC 3] → [Scratch Break] → [MC 4] → [Final Cypher]",
        "tags": ["[Cypher]", "[Freestyle]", "[Multiple MCs]", "[Call And Response]", "[DJ Scratches]"],
        "desc": "Cypher-Dynamik mit mehreren MCs und spontanem Flow-Wechsel.",
    },
    "6. Trap/Drill": {
        "sequence": "[Intro] → [Hook] → [Verse 1] → [Hook] → [Verse 2] → [Beat Drop] → [Final Hook]",
        "tags": ["[808 Sub Bass]", "[Hi-Hat Rolls]", "[Sliding 808]", "[Beat Drop]", "[Adlibs]"],
        "desc": "Dunkle, treibende Rhythmen mit massivem Bass-Drop vor der Final Hook.",
    },
    "7. Party Rap": {
        "sequence": "[Hype Intro] → [Hook] → [Verse 1] → [Hook] → [Dance Break] → [Verse 2] → [Final Hook]",
        "tags": ["[Party Energy]", "[Crowd Chant]", "[Call And Response]", "[Dance Break]", "[Hype Adlibs]"],
        "desc": "Maximale Party-Energie mit Chants und mitreissendem Dance Break.",
    },
    "8. Progressive Hip-Hop": {
        "sequence": "[Intro] → [Verse 1] → [Hook] → [Instrumental] → [Beat Switch] → [Verse 2] → [Bridge] → [Final Switch] → [Outro]",
        "tags": ["[Progressive Hip-Hop]", "[Multiple Beat Switches]", "[Dynamic Arrangement]", "[Genre Fusion]"],
        "desc": "Komplexe musikalische Evolution mit Genre-Fusionen und dynamischem Arrangement.",
    },
}

# ── Oidaheim Semantic Lyrics Bank (Urban Quantum / Ghetto-Metaphern) ─────────
OIDAHEIM_LYRICS_METAPHORS = [
    "von funny Quanten-Mechanik zur Strassen-Botanik intelligent Ghetto-Metaphern...",
    "Universum 1 : schreibe Dissertation / Universum 2: deale an U-Bahnstationen...",
    "Wer braucht schon Licht wenn man mit der Dunkelheit (in die Ecke bricht) spricht!...",
    "Welle Teilchen bis fährt dauerts nur ein kurzes Weilchen...",
    "Relativ gesehen macht ein Stein noch kein Einstein...",
    "FSK12 der Gute bekommt die Frau, FSK 18 der Böse bekommt die Frau, FSK18 alle bekommen die Frau!",
    "OK Google wie ist ein Dreier mit Alexa und Siri!?",
    "Vote 4 strict gender splitting in separate 19\" racks!",
    "Lay back bis break u neck kopf-nick to bouncing moshpit!",
    "Tunnel-Blick-Trick tick tick tick — Schwabinger Untergrund-Moment.",
    "Gleis 13, 089 Code — wir holen uns das Fundament.",
    "Weed — eat — need — sleep — repeat! (Oida, repeat, repeat!)",
    "OIDA — BETONKRONE 089! (Bouncing Moshpit!)",
    "Walla Oida, Joda Jopta, Eisbach Rhymes im Takt!",
    "Scratch Hook: 'Oida weis wurscht is!' KURWA weiss hois einfach wurscht is Oida WALLA JODA JOPTA ois DA OIDA D.G.",
    "Universum 1 liest Bücher, Universum 2 baut Beats.",
    "19-Zoll-Rack glüht im Keller — Rubber Flex Flow, Munich Streets!",
    "Haftstrafenquartett JVA Stadelheim — ACAB Oidasheim MVV Trains Züge Cars Sprayer Graffiti!",
    "Oktoberfest Dirndl Lederhosen Tracht — Betonkrone bricht das Gitter!",
]


class PromptIndexDB:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            style TEXT,
            genre TEXT,
            tags TEXT,
            tempo_min INTEGER,
            tempo_max INTEGER,
            structure TEXT,
            key_elements TEXT,
            lyrics TEXT,
            version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'draft'
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS hiphop_styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style TEXT UNIQUE,
            sound TEXT,
            structure TEXT,
            tags TEXT,
            tempo_range TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS song_semantics_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT UNIQUE,
            title TEXT,
            artist TEXT,
            bpm REAL,
            musical_key TEXT,
            lyrics TEXT,
            tags TEXT,
            parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()
        conn.close()
        self.seed_catalog()

    def seed_catalog(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        for item in HIPHOP_STYLES_CATALOG:
            c.execute(
                """INSERT OR REPLACE INTO hiphop_styles (style, sound, structure, tags, tempo_range)
                         VALUES (?, ?, ?, ?, ?)""",
                (
                    item["style"],
                    item["sound"],
                    item["structure"],
                    json.dumps(item["tags"]),
                    item["tempo_range"],
                ),
            )
        conn.commit()
        conn.close()

    def get_style_info(self, style_name: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM hiphop_styles WHERE style LIKE ?", (f"%{style_name}%",))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "style": row[1],
                "sound": row[2],
                "structure": row[3],
                "tags": json.loads(row[4]) if row[4] else [],
                "tempo_range": row[5],
            }
        return None

    def add_prompt(self, data: Dict) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO prompts 
            (title, content, style, genre, tags, tempo_min, tempo_max, structure, key_elements, lyrics, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("title", "Untitled"),
                data.get("content", ""),
                data.get("style", "Boom Bap"),
                data.get("genre", "Hip-Hop"),
                json.dumps(data.get("tags", [])),
                data.get("tempo_min", 90),
                data.get("tempo_max", 120),
                data.get("structure", ""),
                json.dumps(data.get("key_elements", [])),
                data.get("lyrics", ""),
                data.get("version", "v6/v7"),
            ),
        )
        pid = c.lastrowid
        conn.commit()
        conn.close()
        return pid


class TracklistSemanticScanner:
    """Scans J:\\Oidasheim\\Musik\\FAVs\\**\\*.html, *.htm, *.nml for song semantics and vector logic"""

    @staticmethod
    def scan_and_index_favs(favs_dir: Path = FAVS_ROOT, db: Optional[PromptIndexDB] = None) -> List[Dict]:
        results = []
        if not favs_dir.exists():
            print(f"[scanner] FAVs directory not found: {favs_dir}")
            return results

        patterns = [str(favs_dir / "**" / "*.html"), str(favs_dir / "**" / "*.htm"), str(favs_dir / "**" / "*.nml")]
        files = []
        for p in patterns:
            files.extend(glob.glob(p, recursive=True))

        print(f"[scanner] Scanning {len(files)} semantic files across FAVs...")
        for fpath in files:
            try:
                content = Path(fpath).read_text(encoding="utf-8", errors="replace")
                parsed = TracklistSemanticScanner.parse_file_content(fpath, content)
                if parsed:
                    results.append(parsed)
                    if db:
                        TracklistSemanticScanner.save_to_db(db, parsed)
            except Exception as e:
                continue

        print(f"[scanner] Successfully extracted {len(results)} song semantic entries.")
        return results

    @staticmethod
    def parse_file_content(file_path: str, content: str) -> Optional[Dict]:
        title = Path(file_path).stem
        artist = "Unknown Artist"
        bpm = 0.0
        musical_key = ""
        lyrics = ""
        tags = []

        if file_path.endswith(".html") or file_path.endswith(".htm"):
            # Extract Traktor / Suno HTML export metadata
            title_m = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
            if title_m:
                title = html.unescape(title_m.group(1).strip())
            
            # Lyrics & Section Markers
            lyrics_matches = re.findall(r"(\[[A-Z0-9\s\-_:]{3,60}\][^<\[]{10,800})", content)
            if lyrics_matches:
                lyrics = "\n".join(lyrics_matches)
            
            # BPM search
            bpm_m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*BPM", content, re.IGNORECASE)
            if bpm_m:
                bpm = float(bpm_m.group(1))

        # Tag extraction
        for style in ["Boom Bap", "Trap", "Drill", "Phonk", "West Coast", "East Coast", "Deutschrap", "Half-Time"]:
            if re.search(rf"\b{re.escape(style)}\b", content, re.IGNORECASE):
                tags.append(style)

        for kw in ["089", "Stadelheim", "Eisbach", "Weed", "420", "Oktoberfest", "Tracht", "MVV", "Graffiti"]:
            if re.search(rf"\b{re.escape(kw)}\b", content, re.IGNORECASE):
                tags.append(kw)

        return {
            "source_file": file_path,
            "title": title,
            "artist": artist,
            "bpm": bpm,
            "musical_key": musical_key,
            "lyrics": lyrics,
            "tags": tags,
        }

    @staticmethod
    def save_to_db(db: PromptIndexDB, parsed: Dict):
        conn = sqlite3.connect(db.db_path)
        c = conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO song_semantics_cache 
            (source_file, title, artist, bpm, musical_key, lyrics, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                parsed["source_file"],
                parsed["title"],
                parsed["artist"],
                parsed["bpm"],
                parsed["musical_key"],
                parsed["lyrics"],
                json.dumps(parsed["tags"]),
            ),
        )
        conn.commit()
        conn.close()


class SunoPromptEngine:
    """Core Suno v6 / v7 Prompt Generator Engine"""

    def __init__(self, db: PromptIndexDB):
        self.db = db

    def generate_suno_prompt(
        self,
        style_name: str = "Half-Time Trap Boom-Bap Hybrid",
        structure_name: str = "3. Beat-Switch-Monster",
        custom_lyrics: Optional[str] = None,
        bpm: Optional[int] = None,
        key_signature: str = "Bb Minor",
        artist_persona: str = "IgnaZ 089 x Frau Holocaust",
    ) -> Dict[str, Any]:
        style_info = self.db.get_style_info(style_name) or HIPHOP_STYLES_CATALOG[-1]
        structure_info = SONG_STRUCTURES.get(structure_name, list(SONG_STRUCTURES.values())[0])

        tags_list = list(style_info.get("tags", []))
        structure_tags = structure_info.get("tags", [])
        combined_tags = tags_list + [t for t in structure_tags if t not in tags_list]

        # Style prompt string
        style_prompt = ", ".join(combined_tags)

        # Lyrics generator with quantum / street metaphors
        if not custom_lyrics:
            lyrics = self._build_default_lyrics()
        else:
            lyrics = custom_lyrics

        # Full prompt compilation
        prompt_data = {
            "title": f"HAFTSTRAFEN QUARTETT ({style_name.upper()})",
            "artist": artist_persona,
            "bpm": bpm or (118 if "Half-Time" in style_name else 95),
            "key": key_signature,
            "style_prompt": style_prompt,
            "structure": structure_info["sequence"],
            "lyrics": lyrics,
            "video_clip_prompt": (
                "SCENE 1 [00:00-00:30]: Cinematic wide shot of Munich city at night, dark alley, volumetric smoke rising, glowing green neon signs.\n"
                "SCENE 2 [00:30-01:15]: Fast FPV drone flying through subway station & 19-inch server rack, flickering strobe lights, neon masks.\n"
                "SCENE 3 [01:15-End]: Locked split-screen on concrete rooftop in heavy rain, dark street silhouette, glitch HUD overlay.\n"
                "SEARCH TAGS: munich, 089, u-bahn, city night, smoke, fpv drone, greenbox, neon, split-screen, 19-inch rack"
            ),
        }
        return prompt_data

    def _build_default_lyrics(self) -> str:
        return (
            "[INTRO]\n"
            "Oida... 089 Underground Signal Connection...\n"
            "[Fake SFX: Tunnel-Blick-Trick Tick Tick & Sub-Bass Rumble]\n\n"
            "[VERSE 1]\n"
            "Lay back bis break u neck kopf-nick to bouncing moshpit!\n"
            "Tunnel-Blick-Trick tick tick tick — Schwabinger Untergrund-Moment.\n"
            "Gleis 13, 089 Code — wir holen uns das Fundament.\n"
            "Von funny Quanten-Mechanik zur Strassen-Botanik intelligent Ghetto-Metaphern.\n"
            "Universum 1 schreibt Dissertation / Universum 2 dealt an U-Bahnstationen!\n\n"
            "[420 EXPANSION CHANT]\n"
            "Weed — eat — need — sleep — repeat! (Oida, repeat, repeat!)\n\n"
            "[HOOK]\n"
            "OIDA — BETONKRONE 089! (Bouncing Moshpit!)\n"
            "Walla Oida, Joda Jopta, Eisbach Rhymes im Takt!\n"
            "Scratch Hook: 'Oida weis wurscht is!' KURWA weiss hois einfach wurscht is Oida WALLA JODA JOPTA ois DA OIDA D.G.\n\n"
            "[VERSE 2 - DOUBLE-TIME SHIFT]\n"
            "Universum 1 liest Bücher, Universum 2 baut Beats.\n"
            "19-Zoll-Rack glüht im Keller — Rubber Flex Flow, Munich Streets!\n"
            "Relativ gesehen macht ein Stein noch kein Einstein — Welle-Teilchen-Dualismus am Hauptbahnhof-Gleis!\n"
            "FSK12 der Gute bekommt die Frau, FSK 18 der Böse bekommt die Frau, FSK18 alle bekommen die Frau!\n"
            "Vote 4 strict gender splitting in separate 19\" racks!\n\n"
            "[OUTRO]\n"
            "[Melodic: Fake Hendrix Wah Guitar Motif & Clean Melancholy Riff]\n"
            "U-Bahn fährt ab. OIDA ENDE."
        )

    def query_openrouter_qwen(self, prompt: str) -> Optional[str]:
        """Calls OpenRouter API with Qwen model for dynamic prompt synthesis"""
        if not OPENROUTER_API_KEY:
            return None
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/oefoef/oidasheim",
            "X-Title": "Oidasheim Prompt Engine",
        }
        body = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are the master Suno v6 / v7 rap prompt architect for Oidasheim Munich underground rap, combining quantum mechanics metaphors with street botany, boom-bap, trap and drill vibes.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[openrouter] Error querying LLM: {e}")
            return None


if __name__ == "__main__":
    print("🚀 SUNO v6/v7 PROMPT GENERATOR BACKEND (OIDASHEIM NATIVE GENOME)")
    print("=" * 70)

    db = PromptIndexDB(DEFAULT_DB_PATH)
    engine = SunoPromptEngine(db)

    # 1. Test Prompt Generation
    prompt_res = engine.generate_suno_prompt(
        style_name="Half-Time Trap Boom-Bap Hybrid",
        structure_name="3. Beat-Switch-Monster",
    )
    print(f"\n🎵 GENERATED STYLE PROMPT:\n{prompt_res['style_prompt']}")
    print(f"\n📜 LYRICS PREVIEW:\n{prompt_res['lyrics'][:300]}...\n")

    # 2. Test Traktor / HTML Scanner
    TracklistSemanticScanner.scan_and_index_favs(FAVS_ROOT, db)
    print("✅ System initialized successfully.")
