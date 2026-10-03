#!/usr/bin/env python3
"""
🧬 WE.ED.IT OIDA Native Genome v1.0
Full Stack Bootstrap & Config Compiler
"""

import os
import venv
import sqlite3
import subprocess
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
DB_PATH = ROOT / "database" / "genome_os.db"
DONE_FILE = ROOT / "done"

FOLDERS = [
    "core", "compiler/audio", "compiler/intent", "compiler/grammar",
    "genome/resolver", "genome/bandit", "renderer/ffmpeg", "renderer/otio",
    "scanner", "styles", "camera", "transitions", "fx",
    "database", "projects", "reports", "models", "tests"
]

REQUIREMENTS = [
    "pydantic>=2.0.0", "librosa>=0.10.0", "ffmpeg-python>=0.2.0",
    "pyyaml>=6.0", "jinja2>=3.1.0", "numpy>=1.24.0"
]

def print_step(msg): print(f"\n🚀 [BOOTSTRAP] {msg}")
def print_ok(msg): print(f"✅ [OK] {msg}")

def setup_venv():
    print_step("Initialisiere VENV (manuell)...")
    builder = venv.EnvBuilder(with_pip=False)
    builder.create(VENV_DIR)
    python_bin = VENV_DIR / "Scripts" / "python.exe" if os.name == "nt" else VENV_DIR / "bin" / "python"
    
    print_step("Installiere Pip & Compiler-Deps...")
    subprocess.check_call([str(python_bin), "-m", "ensurepip", "--default-pip"])
    subprocess.check_call([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(python_bin), "-m", "pip", "install"] + REQUIREMENTS)
    print_ok("Environment bereit.")
    return python_bin

def init_architecture():
    for f in FOLDERS: (ROOT / f).mkdir(parents=True, exist_ok=True)
    print_ok("Ordnerstruktur steht.")

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS clips (id INTEGER PRIMARY KEY, sha256 TEXT UNIQUE, path TEXT, duration REAL, tags_json TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()
    print_ok("Datenbank initialisiert.")

def init_config():
    config = {
        "mp3_source": r"I:\Oidasheim\Sound\FAVs07072026",
        "playlist": r"I:\Oidasheim\Sound\FAVs07072026\FAVs07072026.m3u",
        "clips_native": r"D:\Oidasheim\NFOs\Clips"
    }
    with open(ROOT / "config.yaml", "w") as f:
        yaml.dump(config, f)
    
    conn = sqlite3.connect(DB_PATH)
    for k, v in config.items():
        conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()
    print_ok("Konfiguration gespeichert.")

def seed_styles():
    drill = "id: drill_v1\nsections:\n  chorus:\n    cut_every_n_beats: 1\n    camera_motion: 'dynamic_whip'"
    (ROOT / "styles" / "drill.yaml").write_text(drill)
    print_ok("Styles seed abgeschlossen.")

def main():
    try:
        setup_venv()
        init_architecture()
        init_database()
        init_config()
        seed_styles()
        
        # Markiere als erledigt
        DONE_FILE.write_text("Build successful. System ready.")
        print("\n==================================================")
        print("🎉 SYSTEM ONLINE. ./done wurde erstellt.")
        print("==================================================")
    except Exception as e:
        print(f"❌ FEHLER: {e}")

if __name__ == "__main__":
    main()