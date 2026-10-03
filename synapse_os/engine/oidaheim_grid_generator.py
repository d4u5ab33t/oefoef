#!/usr/bin/env python3
import json
import random
from dataclasses import asdict, dataclass

# Base Data Architecture
KEYS = ["C Minor", "C# Minor", "F# Minor", "G Minor", "A Phrygian", "D Dorian"]
MODES = ["Quanten-Drill (140 BPM)", "Stoisch-Half Time (70 BPM)", "Push-Pull Drift (145 BPM)"]

OIDA_PREFIXES = ["Quanten-Oida", "Swalla-König", "Root-Pass", "089-Protokoll", "Sub-Quant", "Stadelheim-Vektor"]
OIDA_ACTION = ["schaltet die Matrix", "biegt die Isar", "bricht den Loop", "drippt stoisch", "hackt den Takt", "fliegt per FPV"]
OIDA_LOCATIONS = ["Neuperlach 83", "Werkviertel", "Sendling-Deep", "U7-Schacht", "Olympia-Beton", "Stadelheim-Gate"]

FLOW_FLIPS = [
    "140 BPM Drill ➔ 70 BPM Stoic Half-Time Drop auf Beat 3",
    "Polyrhythmischer Triplet-Stutter ➔ Liquid Off-Beat Glide",
    "Micro-Delay Vocal Rush ➔ Sub-Bass Earthquake Pause",
    "Pitch-Shift (-12st) ➔ Quanten-Quantized Triple-Staccato",
    "Whisper-Precision ➔ Heavy Sliding 808 Lead"
]

BEAT_DRIFTS = [
    "Sliding -24st 808 Sub + U7-Bremsschrei-Snare",
    "Reverse Vinyl Scratch ➔ Laser-Clean Staccato Kick",
    "Sub-Woofer Frequency Sweep (30Hz) ➔ Muted Rimshot",
    "Industrial Drill-Hats ➔ Atmospheric Druid Choir Layer",
    "Analog Tape Flanger ➔ Crystal-Clear Mono Bass Drop"
]

PUNCHLINES_LEAD = [
    "Kein Schreien im Mikro, pure Präsenz macht die Welle stumm.",
    "Root-User Pass-Door, ich klinke mich ein, du bleibst im Raum.",
    "Oida swalla den Bass, dein Algorithmus bricht im Takt.",
    "Quantensprung im 089-Grid, ich schreib den Code, du liest das Skript.",
    "Keine Hektik auf der Spur, ich steure den Drift per Gedankenstrom.",
    "Stadelheim-Logik: Während du brüllst, übernimmt die Stille den Markt."
]

PUNCHLINES_HOOK = [
    "Swalla die Line, Oida, der Flow kippt ohne Vorwarnung.",
    "Zero Noise, volle Kontrolle – VIP-Zugang freigeschaltet.",
    "Von NPL83 bis zum Zenith: Das Grid gehört dem Flüstern.",
    "Der Beat driftet ab, doch die Achse bleibt stoisch stehen."
]

@dataclass
class TrackDetail:
    id: int
    title: str
    key: str
    bpm: int
    mode: str
    viral_score: float
    flow_flip: str
    beat_drift: str
    prompt_style: str
    lyrics_snippet: str

def generate_track(track_id: int) -> TrackDetail:
    title = f"{random.choice(OIDA_PREFIXES)}: {random.choice(OIDA_ACTION)} ({random.choice(OIDA_LOCATIONS)})"
    key = random.choice(KEYS)
    mode = random.choice(MODES)
    bpm = 140 if "140" in mode else (70 if "70" in mode else 145)
    score = round(random.uniform(9.4, 9.98), 2)
    
    flow = random.choice(FLOW_FLIPS)
    drift = random.choice(BEAT_DRIFTS)
    
    style_prompt = (
        f"regional drill, stoic male rap, pure vocal presence, zero shouting, "
        f"{bpm} bpm, {key}, {drift}, quanted flow flips, deep sub-bass, dark cinematic atmosphere"
    )
    
    lyrics = (
        f"[Intro]\n(Sub-Bass Rumble)\nRoot-User Pass-Door. Oida... 089.\n\n"
        f"[Verse]\n{random.choice(PUNCHLINES_LEAD)}\n"
        f"Flow-Flip: {flow}.\n\n"
        f"[Hook]\n{random.choice(PUNCHLINES_HOOK)}\n"
        f"Oidaheim 3047 – Stoische Kontrolle."
    )
    
    return TrackDetail(track_id, title, key, bpm, mode, score, flow, drift, style_prompt, lyrics)

def main():
    print("🚀 Generating 100-Track VIP Viral Matrix...")
    grid = [generate_track(i) for i in range(1, 101)]
    
    json_filename = "../config/oidaheim_100_song_grid.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in grid], f, ensure_ascii=False, indent=2)
    print(f"✅ JSON export completed: {json_filename}")

if __name__ == "__main__":
    main()
