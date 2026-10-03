import os
import zipfile
import json

# Ordnerstruktur erstellen
directories = ["config", "engine", "agents", "dashboard"]
for d in directories:
    os.makedirs(os.path.join("SYNAPSE_OIDAHEIM_3047", d), exist_ok=True)

# 1. config/config.json
config_data = {
    "system_name": "SYNAPSE AUDIO DYNAMICS - OIDAHEIM 3047",
    "bpm_master": 140,
    "quanten_mode": "Stoic Vocal Control",
    "modules": {
        "atlas": {"completion_threshold": 0.85, "auto_ads": True},
        "orion": {"target_platforms": ["Spotify", "Netflix"], "auto_pitch": True},
        "jinx": {"viral_score_min": 9.5},
        "kairo_vega": {"next_track_pipeline": True},
        "kreon_phoenix": {"tech_merch_infra": True}
    }
}
with open("SYNAPSE_OIDAHEIM_3047/config/config.json", "w", encoding="utf-8") as f:
    json.dump(config_data, f, indent=2)

# 2. engine/oidaheim_grid_generator.py
grid_code = '''#!/usr/bin/env python3
import json
import random
from dataclasses import asdict, dataclass

KEYS = ["C Minor", "C# Minor", "F# Minor", "G Minor", "A Phrygian", "D Dorian"]
MODES = ["Quanten-Drill (140 BPM)", "Stoisch-Half Time (70 BPM)", "Push-Pull Drift (145 BPM)"]

OIDA_PREFIXES = ["Quanten-Oida", "Swalla-König", "Root-Pass", "089-Protokoll", "Sub-Quant", "Stadelheim-Vektor"]
OIDA_ACTION = ["schaltet die Matrix", "biegt die Isar", "bricht den Loop", "drippt stoisch", "hackt den Takt", "fliegt per FPV"]
OIDA_LOCATIONS = ["Neuperlach 83", "Werkviertel", "Sendling-Deep", "U7-Schacht", "Olympia-Beton", "Stadelheim-Gate"]

@dataclass
class TrackDetail:
    id: int
    title: str
    key: str
    bpm: int
    mode: str
    viral_score: float
    prompt_style: str
    lyrics_snippet: str

def generate_track(track_id: int) -> TrackDetail:
    title = f"{random.choice(OIDA_PREFIXES)}: {random.choice(OIDA_ACTION)} ({random.choice(OIDA_LOCATIONS)})"
    key = random.choice(KEYS)
    mode = random.choice(MODES)
    bpm = 140 if "140" in mode else (70 if "70" in mode else 145)
    score = round(random.uniform(9.4, 9.98), 2)
    style = f"regional drill, stoic male rap, pure vocal presence, zero shouting, {bpm} bpm, {key}, deep sub-bass"
    lyrics = "[Intro]\\nRoot-User Pass-Door. Oida... 089.\\n\\n[Verse]\\nPure Präsenz macht die Welle stumm."
    return TrackDetail(track_id, title, key, bpm, mode, score, style, lyrics)

def main():
    grid = [generate_track(i) for i in range(1, 101)]
    with open("SYNAPSE_OIDAHEIM_3047/config/oidaheim_100_song_grid.json", "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in grid], f, indent=2)
    print("✅ 100-Track VIP Viral Matrix erfolgreich exportiert!")

if __name__ == "__main__":
    main()
'''
with open("SYNAPSE_OIDAHEIM_3047/engine/oidaheim_grid_generator.py", "w", encoding="utf-8") as f:
    f.write(grid_code)

# 3. engine/atlas_completion_mon.py
atlas_code = '''#!/usr/bin/env python3
import time

def monitor_completion_rate():
    print("📊 [ATLAS MONITOR] Überwache Video completion rates...")
    completion_rate = 0.88  # Simulation
    if completion_rate >= 0.85:
        print(f"🚀 [ATLAS] Completion Rate bei {completion_rate*100}%! Schalte Ad-Budget frei.")
        print("🎵 [ORION] Track wird automatisch an Spotify & Netflix gepitcht.")
    else:
        print("⏳ [ATLAS] Warte auf höheren Engagement Score...")

if __name__ == "__main__":
    monitor_completion_rate()
'''
with open("SYNAPSE_OIDAHEIM_3047/engine/atlas_completion_mon.py", "w", encoding="utf-8") as f:
    f.write(atlas_code)

# 4. requirements.txt
reqs = "numpy\nlibrosa\ntorch\nmutagen\nrequests\npydantic\n"
with open("SYNAPSE_OIDAHEIM_3047/requirements.txt", "w", encoding="utf-8") as f:
    f.write(reqs)

# 5. README.md
readme = """# SYNAPSE AUDIO DYNAMICS - OIDAHEIM 3047
## Imperium Execution Protocol

### Quickstart:
1. Virtualenv aktivieren: `python3 -m venv venv && source venv/bin/activate`
2. Dependencies installieren: `pip install -r requirements.txt`
3. 100-Song Grid generieren: `python engine/oidaheim_grid_generator.py`
4. Atlas Monitoring starten: `python engine/atlas_completion_mon.py`

**WEISS WURSCHT DES MUSIK. 🔥**
"""
with open("SYNAPSE_OIDAHEIM_3047/README.md", "w", encoding="utf-8") as f:
    f.write(readme)

# ZIP Archiv erstellen
zip_filename = "SYNAPSE_OIDAHEIM_3047_FULL.zip"
with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, _, files in os.walk("SYNAPSE_OIDAHEIM_3047"):
        for file in files:
            full_path = os.path.join(root, file)
            arcname = os.path.relpath(full_path, start=".")
            zipf.write(full_path, arcname)
