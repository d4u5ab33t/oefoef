"""
preview_render.py — Rendert EINEN Song sofort, OHNE den Clip-Pool-Cache neu
zu bauen/patchen. Nutzt den aktuellen Stand von libsync-flat-globe.db.json
1:1 (auch wenn Teile noch auf analysis_version=3 stehen, z.B. während
migrate_motion_direction.py im Hintergrund läuft) -> kein Warten auf den
vollen Cache-Rebuild nötig, nur zum schnellen Antesten der Übergänge.

Nutzung:
    python preview_render.py                      # ersten gefundenen Song
    python preview_render.py "J:/.../song.mp3"     # bestimmten Song
"""
import sys
from pathlib import Path

import db
import mp3_scanner
from config import ROOT_DIR
from creative_genome import compile_style

import main as pipeline


def main():
    song_arg = sys.argv[1] if len(sys.argv) > 1 else None

    db.init_db()
    style = compile_style("cinematic", ROOT_DIR / "styles")

    globe = db.load_flat_globe()  # <- KEIN build_or_update_globe, nutzt Cache 1:1
    print(f"[preview] Globe geladen: {len(globe)} Clips (ohne Rebuild).", flush=True)

    songs = mp3_scanner.scan_all_songs()
    if not songs:
        print("[preview] Keine Songs gefunden.", flush=True)
        return

    if song_arg:
        target = Path(song_arg).resolve()
        matches = [s for s in songs if Path(s.path).resolve() == target]
        song = matches[0] if matches else songs[0]
    else:
        song = songs[0]

    print(f"[preview] Rendere: {song.path}", flush=True)
    output_dir = ROOT_DIR / "output"
    ok = pipeline.process_song(song, globe, output_dir, style, platform="full", dry_run=False)
    print("[preview] OK" if ok else "[preview] FEHLGESCHLAGEN", flush=True)


if __name__ == "__main__":
    main()
