#!/usr/bin/env python3
"""
WE.ED.IT v9 "Studio" - 1-Click CLI Launcher & AI Art Director
"Musik dirigiert. KI schneidet. Du kreierst."
"""
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from weedit.core.engine import WeEditEngine, WeEditConfig

BANNER = r"""
    ██╗  ██╗███████╗    ███████╗██████╗  ██╗████████╗
    ██║  ██║██╔════╝    ██╔════╝██╔══██╗ ██║╚══██╔══╝
    ██║████║█████╗      █████╗  ██║  ██║ ██║   ██║   
    ██╔==██║██╔══╝      ██╔══╝  ██║  ██║ ██║   ██║   
    ██║  ██║███████╗    ███████╗██████╔╝ ██║   ██║   
    ╚═╝  ╚═╝╚══════╝    ╚══════╝╚═════╝  ╚═╝   ╚═╝   
    WE.ED.IT v9.0 "Studio" - AI Art Director & Beat Sync Editor
"""

def main():
    print(BANNER)
    parser = argparse.ArgumentParser(description="WE.ED.IT v9 Studio AI Music Video Creator")
    parser.add_argument("--song", type=str, help="Pfad zur MP3-Datei")
    parser.add_argument("--profile", type=str, default="cinematic", choices=["cinematic", "tiktok", "fast", "quality"], help="Render Profil")
    parser.add_argument("--output-dir", type=str, help="Optionaler Ausgabenordner")
    parser.add_argument("--clip-pool", type=str, default="J:/raw_vidz/_raw_reorga__", help="Clip-Pool Quellordner")

    args = parser.parse_args()

    resolution = (3840, 2160) if args.profile == "cinematic" else (1080, 1920) if args.profile == "tiktok" else (1920, 1080)
    config = WeEditConfig(profile=args.profile, resolution=resolution, fps=30)
    config.pool_dir = args.clip_pool

    engine = WeEditEngine(config)
    engine.initialize()

    if args.song:
        output_file = engine.build_music_video(args.song, args.output_dir)
        print(f"\n✅ WE.ED.IT Studio Musikvideo erfolgreich vorbereitet: {output_file}")
    else:
        print("\nℹ️ Kein Song angegeben. Starte Test-Analyse für Systembereitschaft...")
        print("💡 Verwende: python weedit_v9_studio.py --song 'J:/Pfad/zum/Song.mp3'")

if __name__ == "__main__":
    main()
