#!/usr/bin/env python3
"""
OIDAHEIM 3047: VIP-100 VIRAL MATRIX GENERATOR (QUANTEN-GRID ENGINE)
- Erzeugt ein 100-Song-Grid mit stoischer Kontrolle, Quanten-Sprung-Flips & Beat-Drifts.
- Fokus: Pure Präsenz, intelligente Oida-Swalla-Punchlines, zero Schreien.
- Exportiert als JSON & Markdown-Tabelle für Suno v4.5 Processing.
- Aktiviert durch den Befehl: "Clip Clip CLAP!" (System-Boot-Komponente)
"""

import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime

# ==============================================================================
# 1. BASE DATA ARCHITECTURE (Das Fundament des Imperiums)
# ==============================================================================

# --- Musiktheorie & Taktik (Stoische Kontrolle) ---
KEYS = ["C Minor", "C# Minor", "F# Minor", "G Minor", "A Phrygian", "D Dorian"]
MODES = ["Quanten-Drill (140 BPM)", "Stoisch-Half Time (70 BPM)", "Push-Pull Drift (145 BPM)"]

# --- Oida-Swalla-Punchlines (Intelligenz & Präsenz) ---
OIDA_PREFIXES = ["Quanten-Oida", "Swalla-König", "Root-Pass", "089-Protokoll", "Sub-Quant", "Stadelheim-Vektor"]
OIDA_ACTION = ["schaltet die Matrix", "biegt die Isar", "bricht den Loop", "drippt stoisch", "hackt den Takt", "fliegt per FPV"]
OIDA_LOCATIONS = ["Neuperlach 83", "Werkviertel", "Sendling-Deep", "U7-Schacht", "Olympia-Beton", "Stadelheim-Gate"]

# --- Flow Flips & Beat Drifts (Unerwartete Sprünge) ---
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

# --- Punchlines (kein Schreien, pure Präsenz) ---
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

# ==============================================================================
# 2. DATENSTRUKTUR & GENERATOR-KERN
# ==============================================================================

@dataclass
class TrackDetail:
    """
    Detailierte Track-Informationen für den viralen Grid.
    Alle Werte sind auf "Stoische Präsenz" optimiert.
    """
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

    def to_markdown(self) -> str:
        """Erzeugt eine lesbare Zeile für die Markdown-Tabelle."""
        return f"| {self.id} | {self.title[:30]}... | {self.key} | {self.bpm} | {self.viral_score} | {self.flow_flip[:30]}... |"

def generate_track(track_id: int) -> TrackDetail:
    """
    Generiert einen einzelnen Track mit zufälligen, aber stilistisch
    kohärenten Werten aus den definierten Pools.
    """
    title = f"{random.choice(OIDA_PREFIXES)}: {random.choice(OIDA_ACTION)} ({random.choice(OIDA_LOCATIONS)})"
    key = random.choice(KEYS)
    mode = random.choice(MODES)
    
    # BPM dynamisch aus dem Mode extrahieren
    if "140" in mode:
        bpm = 140
    elif "70" in mode:
        bpm = 70
    else: # 145
        bpm = 145

    # Viral-Score: Hoch, aber mit minimaler Varianz für "Premium-Gefühl"
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
    
    return TrackDetail(
        id=track_id,
        title=title,
        key=key,
        bpm=bpm,
        mode=mode,
        viral_score=score,
        flow_flip=flow,
        beat_drift=drift,
        prompt_style=style_prompt,
        lyrics_snippet=lyrics
    )

# ==============================================================================
# 3. DAS IMPERIUM: SYSTEM-BOOT & EXPORT
# ==============================================================================

def main():
    """Hauptfunktion. Wird durch den Befehl 'Clip Clip CLAP!' aktiviert."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🏁  OIDAHEIM 3047 - DAS IMPERIUM WACHT AUF  🏁           ║
    ║                                                              ║
    ║   Befehl empfangen: "Clip Clip CLAP!"                       ║
    ║   System-Boot erfolgreich. Generiere 100-Track VIP-Matrix... ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 1. Das Grid generieren
    grid = [generate_track(i) for i in range(1, 101)]
    
    # 2. JSON-Export (Für Suno v4.5, DAWs oder KI-Tools)
    json_filename = f"oidaheim_100_song_grid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in grid], f, ensure_ascii=False, indent=2)
    print(f"✅ JSON export completed: {json_filename}")

    # 3. Markdown-Export (Für Übersicht/Dokumentation)
    md_filename = f"oidaheim_grid_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write("# OIDAHEIM 3047: VIP-100 VIRAL MATRIX\n\n")
        f.write("| ID | Title | Key | BPM | Viral Score | Flow Flip |\n")
        f.write("|----|-------|-----|-----|-------------|-----------|\n")
        for track in grid:
            f.write(track.to_markdown() + "\n")
    print(f"✅ Markdown preview completed: {md_filename}")

    # 4. Top 3 Preview auf der Konsole anzeigen
    print("\n--- TOP 3 GRID PREVIEW (Stoische Kontrolle) ---")
    for track in grid[:3]:
        print(f"\nID #{track.id} | {track.title} [Score: {track.viral_score}]")
        print(f"Key: {track.key} | BPM: {track.bpm} | Mode: {track.mode}")
        print(f"Flow Flip: {track.flow_flip}")
        print(f"Beat Drift: {track.beat_drift}")
        print(f"Suno v4.5 Style: {track.prompt_style}")
        print(f"Lyrics Preview:\n{track.lyrics_snippet}")
        print("-" * 50)
    
    print("\n🏁 Das Imperium hat gesprochen. Das Grid ist bereit.")

if __name__ == "__main__":
    # Hier wird der Befehl ausgeführt.
    # In der realen Anwendung könntest du hier auf eine Benutzereingabe warten.
    # Für den direkten Start: "Clip Clip CLAP!" ist bereits enthalten.
    main()