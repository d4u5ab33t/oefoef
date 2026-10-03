#!/usr/bin/env python3
"""
SUNO v7 ULTRA-NATIVE PROMPT ENGINE & BEATSYNC EDL EXPORTER
Extends database trees, provides AI prompt enhancement, EP batch generation,
and exports BeatSync JSON/EDL timelines for Oidasheim 3047.
"""

import os
import json
import sqlite3
import random
from pathlib import Path
from datetime import datetime

WORKSPACE_DIR = Path(r"J:\Oidasheim")
DB_PATH = WORKSPACE_DIR / "oefoef" / "suno_prompt_index.db"

SUBGENRES_3047 = [
    {"name": "Bavarian Drill / IT-Hybrid", "bpm_range": [138, 150], "key": "C minor", "vibe": "Technical, cold, aggressive, Munich dialect, sub-bass slides"},
    {"name": "Stoic Cyberpunk 3047 Trap", "bpm_range": [140, 160], "key": "G minor", "vibe": "Paranoid, thermal-scan, futuristic, tunnel-vision, glitch SFX"},
    {"name": "Golden Age Boom-Bap 90s", "bpm_range": [85, 95], "key": "D minor", "vibe": "Dusty MPC drums, vinyl crackle, warm live bass, vocal scratches"},
    {"name": "Quanten-Trap & Alpine Brass", "bpm_range": [145, 165], "key": "F minor", "vibe": "Detuned alpine horn samples, wobbling sub-bass, hybrid flow"},
    {"name": "Oida Swag 420 Weed-Dubstep", "bpm_range": [135, 145], "key": "A minor", "vibe": "Heavy half-time drops, wobbling sub, reggae-rap phrasing"},
    {"name": "Industrial G-Funk Munich", "bpm_range": [92, 102], "key": "E minor", "vibe": "Whistling synths, sliding 808s, laid-back arrogancy"},
    {"name": "Isar-Glitch Techno-Rap", "bpm_range": [128, 138], "key": "B minor", "vibe": "4-to-the-floor kick, distorted server drones, fast staccato"},
    {"name": "Stadelheim Ambient-Drill", "bpm_range": [130, 144], "key": "C minor", "vibe": "Eerie pads, distant sirens, whispered stoic phrasing"}
]

def seed_database():
    """Seed suno_prompt_index.db with sub-genres and prompt rules"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS hiphop_styles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        style TEXT UNIQUE,
        sound TEXT,
        structure TEXT,
        tags TEXT,
        tempo_range TEXT
    )''')
    
    for sub in SUBGENRES_3047:
        c.execute('''INSERT OR REPLACE INTO hiphop_styles (style, sound, structure, tags, tempo_range)
            VALUES (?, ?, ?, ?, ?)''', (
                sub["name"],
                sub["vibe"],
                "Intro->Verse1->PreChorus->Chorus->BeatSwitch->Verse2->Outro",
                json.dumps(["oidaheim", "suno_v6", "3047", sub["name"].lower()]),
                f"{sub['bpm_range'][0]}-{sub['bpm_range'][1]} BPM"
            ))
            
    conn.commit()
    conn.close()
    print("✅ Seeded suno_prompt_index.db with 8 Oidasheim 3047 sub-genres!")

def enhance_prompt(user_idea: str, genre_name: str = None) -> dict:
    """AI Auto-Enhancer: Expands brief ideas into full 1k/5k/3k Suno v6 prompts"""
    selected = None
    if genre_name:
        selected = next((s for s in SUBGENRES_3047 if s["name"] == genre_name), None)
    if not selected:
        selected = random.choice(SUBGENRES_3047)
        
    bpm = random.randint(selected["bpm_range"][0], selected["bpm_range"][1])
    key = selected["key"]
    title = f"{user_idea.title() if user_idea else 'Oidaheim Banger'} (v7 Ultra)"

    style_prompt = (
        f"{selected['name']}, {bpm} BPM, {key}, {selected['vibe']}, "
        f"heavy sliding 808 sub-bass, crisp hi-hat stutters, vinyl crackle, glitch audio SFX, "
        f"vocal layering, optimized for Suno v6 audio dynamics."
    )[:1000]

    lyrics_prompt = (
        f"[Intro]\n(Sub-bass rumble)\n(Vinyl crackle)\nOida... {bpm} BPM in {key}.\n\n"
        f"[Verse 1]\n[Male Vocals]\n[Aggressive Delivery]\n"
        f"Quantensprung im 089-Grid, wir schreiben den Code in der Nacht.\n"
        f"{user_idea if user_idea else 'Root-Access auf den Beat, Oidaheim übernimmt die Kontrolle.'}\n"
        f"Thermalsensor scannt den Marienplatz, die Achse bleibt stabil.\n\n"
        f"[Hook]\n[Harmonies]\n[Ad-lib: Oida!]\n"
        f"(Police sirens in distance)\n"
        f"Der Beat driftet ab, doch die Achse bleibt stoisch stehen!\n"
        f"Oidaheim 3047 – Volle Kontrolle.\n\n"
        f"[Beat Switch: {bpm} BPM -> {bpm // 2} BPM Stoic Half-Time Drop]\n"
        f"[Verse 2]\n[Whispered Flow]\n"
        f"Kein Schreien im Mikro, pure Präsenz macht die Welle stumm.\n"
        f"Sudo rm -rf auf alle Zweifel, Oida.\n\n"
        f"[Outro]\n(Tape stop edit)\nZero Noise. System Offline."
    )[:5000]

    smart_prompt = (
        f"Track Title: {title}\nGenre: {selected['name']}\nTempo: {bpm} BPM | Key: {key}\n"
        f"Vibe: {selected['vibe']}\nConcept: {user_idea if user_idea else 'Dystopian Munich Dialect Rap'}\n\n"
        f"High-energy futuristic track fusing Munich street slang with code metaphors and half-time drops."
    )[:3000]

    return {
        "title": title,
        "genre": selected["name"],
        "bpm": bpm,
        "key": key,
        "style": style_prompt,
        "lyrics": lyrics_prompt,
        "smart": smart_prompt
    }

def generate_ep_batch(album_title: str = "OIDASHEIM 3047 EP") -> list:
    """Generates a complete 10-track EP prompt grid"""
    ep_tracks = []
    for i in range(10):
        sub = SUBGENRES_3047[i % len(SUBGENRES_3047)]
        enhanced = enhance_prompt(f"Track {i+1} - {sub['name'].split('/')[0]}", sub["name"])
        enhanced["track_num"] = i + 1
        ep_tracks.append(enhanced)
    return ep_tracks

def export_beatsync_edl(track_data: dict) -> dict:
    """Exports a BeatSync EDL timeline JSON compatible with main.py & renderer.py"""
    bpm = track_data.get("bpm", 140)
    spb = 60.0 / bpm # Seconds per beat
    
    timeline_segments = [
        {"segment": 1, "type": "Intro", "start_sec": 0.0, "end_sec": round(spb * 16, 2), "vibe": "dark_ambient", "camera_motion": "slow_zoom_in"},
        {"segment": 2, "type": "Verse 1", "start_sec": round(spb * 16, 2), "end_sec": round(spb * 48, 2), "vibe": "aggressive_drill", "camera_motion": "whip_pan_fast"},
        {"segment": 3, "type": "Hook", "start_sec": round(spb * 48, 2), "end_sec": round(spb * 80, 2), "vibe": "epic_drop", "camera_motion": "sub_earthquake_shake"},
        {"segment": 4, "type": "Beat Switch", "start_sec": round(spb * 80, 2), "end_sec": round(spb * 112, 2), "vibe": "half_time_stoic", "camera_motion": "slow_rotation_glide"},
        {"segment": 5, "type": "Outro", "start_sec": round(spb * 112, 2), "end_sec": round(spb * 128, 2), "vibe": "fade_out", "camera_motion": "static_glitch"}
    ]
    
    return {
        "title": track_data.get("title", "Oidaheim Track"),
        "bpm": bpm,
        "key": track_data.get("key", "C minor"),
        "genre": track_data.get("genre", "Bavarian Drill"),
        "total_duration_sec": round(spb * 128, 2),
        "edl_version": "2.0-BeatSync",
        "segments": timeline_segments
    }

if __name__ == "__main__":
    seed_database()
    sample = enhance_prompt("Quanten-Schacht 089")
    print(f"\n⚡ Sample AI Enhanced Track: {sample['title']}")
    print(f"   BPM: {sample['bpm']} | Key: {sample['key']}")
    print(f"   Style ({len(sample['style'])} chars): {sample['style'][:100]}...")
    
    edl = export_beatsync_edl(sample)
    print(f"🎬 Exported BeatSync EDL ({len(edl['segments'])} segments, total {edl['total_duration_sec']}s)")
