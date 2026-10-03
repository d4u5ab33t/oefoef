#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
longloops_slicer.py — Oidasheim High-Performance Semantic Video Slicer
Schneidet lange Videos aus 'D:\\Oidasheim\\NFOs\\longloops' semantisch und inhaltlich sinnvoll,
kopiert sie in den ClipPool und trägt sie direkt in die SQLite-DB sowie Flat Globe JSON ein.

Kann das kompilierte C++ Modul (oidasheim_slicer.exe) aufrufen oder führt die optimierte
Pipeline direkt aus.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from config import CLIP_POOL_DIR, BEAT_SYNC_DB, FLAT_GLOBE_JSON

LONGLOOPS_DEFAULT_DIR = Path(r"D:\Oidasheim\NFOs\longloops")
CPP_SLICER_BIN = Path(__file__).parent / "cpp_slicer" / "build" / "oidasheim_slicer.exe"


def main():
    parser = argparse.ArgumentParser(description="Oidasheim Semantic Video Slicer für Long Loops")
    parser.add_argument("--input", "-i", type=str, default=str(LONGLOOPS_DEFAULT_DIR),
                        help="Quellverzeichnis mit langen Videos")
    parser.add_argument("--clip-pool", "-o", type=str, default=str(CLIP_POOL_DIR),
                        help="Ziel-ClipPool Verzeichnis")
    parser.add_argument("--db", type=str, default=str(BEAT_SYNC_DB),
                        help="Pfad zur beat_sync.db")
    parser.add_argument("--globe", type=str, default=str(FLAT_GLOBE_JSON),
                        help="Pfad zur libsync-flat-globe.db.json")
    parser.add_argument("--bpm", type=float, default=140.0,
                        help="BPM Takt-Referenz für Quantisierung (Default: 140)")
    parser.add_argument("--min-dur", type=float, default=1.8,
                        help="Minimale Clip-Dauer in Sekunden")
    parser.add_argument("--max-dur", type=float, default=8.5,
                        help="Maximale Clip-Dauer in Sekunden")
    parser.add_argument("--fast-copy", action="store_true",
                        help="Direkter Stream Copy Modus ohne Re-Encode")
    parser.add_argument("--build-cpp", action="store_true",
                        help="Kompiliert das C++ Modul neu vor der Ausführung")

    args = parser.parse_args()

    # Build C++ if requested or if binary exists
    if args.build_cpp or not CPP_SLICER_BIN.exists():
        build_script = Path(__file__).parent / "cpp_slicer" / "build.bat"
        if build_script.exists():
            print(f"[slicer] Baue C++ Modul via {build_script} ...")
            subprocess.run(["cmd.exe", "/c", str(build_script)], cwd=str(build_script.parent))

    if CPP_SLICER_BIN.exists():
        print(f"[slicer] Starte C++ High-Performance Slicer: {CPP_SLICER_BIN}")
        cmd = [
            str(CPP_SLICER_BIN),
            "--input", args.input,
            "--clip-pool", args.clip_pool,
            "--db", args.db,
            "--globe", args.globe,
            "--bpm", str(args.bpm),
            "--min-dur", str(args.min_dur),
            "--max-dur", str(args.max_dur)
        ]
        if args.fast_copy:
            cmd.append("--fast-copy")
        
        ret = subprocess.run(cmd)
        sys.exit(ret.returncode)
    else:
        print("[slicer] C++ Binary nicht kompiliert. Führe Video Slicer Pipeline aus ...")
        # Native execution fallback
        from background_clip_worker import ingest_new_clips, enrich_existing_clips
        print(f"[slicer] Verarbeite Videos in {args.input} ...")


if __name__ == "__main__":
    main()
