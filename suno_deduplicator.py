#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
suno_deduplicator.py — Duplicate Finder & Safe Mover für Suno-Musikdaten (*suno*).

Sucht doppelte Songs, Cover-Arts und Metadaten in J:\\Oidasheim\\Musik\\*suno*
und verschiebt die Duplikate sicher unter Beibehaltung der Verzeichnisstruktur
nach J:\\Oidasheim\\Musik\\doppelt.

Deduplizierungs-Strategie:
  1. Multi-Stage Hash Deduplication (Dateigröße -> Head-Hash 16KB -> Full MD5).
  2. Bevorzugt Originaldateien (ohne ' (1)', ' (2)' Suffixe, kürzere & saubere Namen).
  3. Struktur-erhaltendes Verschieben (shutil.move) nach J:\\Oidasheim\\Musik\\doppelt.
  4. Kollisionsfreier Transfer: Keine Datei wird jemals überschrieben.
  5. Multi-Threaded Hashing für maximale I/O-Performance.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


DEFAULT_MUSIK_ROOT = Path(r"J:\Oidasheim\Musik")
DEFAULT_DEST_DIR = Path(r"J:\Oidasheim\Musik\doppelt")


def get_suno_directories(musik_root: Path = DEFAULT_MUSIK_ROOT) -> list[Path]:
    """Findet alle *suno* Verzeichnisse unter dem Musik-Root."""
    if not musik_root.exists():
        return []
    suno_dirs = []
    for entry in os.listdir(musik_root):
        full_p = musik_root / entry
        if full_p.is_dir() and "suno" in entry.lower() and entry.lower() != "doppelt":
            suno_dirs.append(full_p)
    return sorted(suno_dirs)


def compute_fast_hash(path: Path, head_size: int = 16384) -> str:
    """Berechnet einen schnellen Head-Hash über die ersten 16KB."""
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(head_size)
            return hashlib.md5(chunk).hexdigest()
    except Exception:
        return ""


def compute_full_md5(path: Path, chunk_size: int = 65536) -> str:
    """Berechnet den vollständigen MD5-Hash einer Datei."""
    md5 = hashlib.md5()
    try:
        with open(path, "rb") as fh:
            while chunk := fh.read(chunk_size):
                md5.update(chunk)
        return md5.hexdigest()
    except Exception:
        return ""


def select_keeper(file_group: list[Path]) -> Path:
    """Wählt deterministisch die beste Originaldatei aus einer Gruppe identischer Duplikate."""
    def _penalty(p: Path) -> tuple[int, int, int, str]:
        name = p.name
        # 1. Höhere Strafe für ' (1)', ' (2)', etc. Suffix
        has_paren_num = 1 if re.search(r"\s\(\d+\)\.[a-zA-Z0-9]+$", name) else 0
        # 2. Strafe für lange Namen
        name_len = len(name)
        # 3. Zeitstempel (ältere bevorzugt)
        try:
            mtime = int(p.stat().st_mtime)
        except Exception:
            mtime = 0
        return (has_paren_num, name_len, mtime, str(p))

    return min(file_group, key=_penalty)


def find_duplicates(
    suno_dirs: list[Path],
    workers: int = 32,
    log=print,
) -> tuple[list[tuple[Path, Path]], dict[str, Any]]:
    """Findet alle Duplikate über alle Suno-Verzeichnisse hinweg."""
    log(f"[dedup] Scanne Dateien in {len(suno_dirs)} Suno-Verzeichnissen...")
    t0 = time.time()
    
    all_files: list[Path] = []
    by_size: dict[int, list[Path]] = defaultdict(list)

    for sdir in suno_dirs:
        for root, _, files in os.walk(sdir):
            for f in files:
                p = Path(root) / f
                try:
                    sz = p.stat().st_size
                    if sz > 0:
                        by_size[sz].append(p)
                        all_files.append(p)
                except Exception:
                    pass

    total_files = len(all_files)
    candidate_groups = [flist for sz, flist in by_size.items() if len(flist) > 1]
    candidate_files_count = sum(len(l) for l in candidate_groups)
    log(f"[dedup] {total_files} Dateien gescannt. {candidate_files_count} Dateien in {len(candidate_groups)} Größen-Kandidatengruppen.")

    # Phase 1: Fast Head Hash (16KB)
    log(f"[dedup] Phase 1: Berechne Head-Hashes mit {workers} Worker-Threads...")
    candidate_files = [f for grp in candidate_groups for f in grp]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        head_hashes = list(executor.map(compute_fast_hash, candidate_files))

    by_size_and_head: dict[tuple[int, str], list[Path]] = defaultdict(list)
    for p, h in zip(candidate_files, head_hashes):
        if h:
            by_size_and_head[(p.stat().st_size, h)].append(p)

    head_candidate_groups = [flist for flist in by_size_and_head.values() if len(flist) > 1]
    head_files_to_full_hash = [f for grp in head_candidate_groups for f in grp]
    log(f"[dedup] Phase 2: {len(head_files_to_full_hash)} Dateien erfordern vollständigen MD5-Abgleich...")

    # Phase 2: Full MD5 Hash
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        full_hashes = list(executor.map(compute_full_md5, head_files_to_full_hash))

    by_full_md5: dict[str, list[Path]] = defaultdict(list)
    for p, fh in zip(head_files_to_full_hash, full_hashes):
        if fh:
            by_full_md5[fh].append(p)

    dupes_to_move: list[tuple[Path, Path]] = [] # (duplicate_path, keeper_path)
    total_duplicate_bytes = 0
    ext_stats: dict[str, int] = defaultdict(int)

    for md5_hash, file_list in by_full_md5.items():
        if len(file_list) <= 1:
            continue
        keeper = select_keeper(file_list)
        for p in file_list:
            if p != keeper:
                dupes_to_move.append((p, keeper))
                try:
                    total_duplicate_bytes += p.stat().st_size
                except Exception:
                    pass
                ext_stats[p.suffix.lower()] += 1

    elapsed = time.time() - t0
    log(f"[dedup] Analyse abgeschlossen in {elapsed:.2f}s: {len(dupes_to_move)} Duplikate gefunden ({total_duplicate_bytes / (1024*1024):.2f} MB).")

    stats = {
        "total_files": total_files,
        "candidate_files": candidate_files_count,
        "duplicate_count": len(dupes_to_move),
        "duplicate_bytes": total_duplicate_bytes,
        "ext_stats": dict(ext_stats),
        "elapsed": elapsed,
    }

    return dupes_to_move, stats


def move_duplicates_to_destination(
    dupes_to_move: list[tuple[Path, Path]],
    dest_root: Path = DEFAULT_DEST_DIR,
    source_root: Path = DEFAULT_MUSIK_ROOT,
    dry_run: bool = False,
    log=print,
) -> dict[str, int]:
    """Verschiebt gefundene Duplikate sicher nach J:\\Oidasheim\\Musik\\doppelt."""
    dest_root.mkdir(parents=True, exist_ok=True)
    log(f"\n[dedup] Verschiebe {len(dupes_to_move)} Duplikate nach: {dest_root}...")

    stats = {
        "moved": 0,
        "skipped": 0,
        "errors": 0,
    }

    t0 = time.time()

    for idx, (dupe_path, keeper_path) in enumerate(dupes_to_move, 1):
        if not dupe_path.exists():
            stats["skipped"] += 1
            continue

        try:
            # Berechne relativen Pfad zu J:\Oidasheim\Musik
            try:
                rel_path = dupe_path.relative_to(source_root)
            except ValueError:
                rel_path = Path(dupe_path.parent.name) / dupe_path.name

            target_path = dest_root / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Kollisionsvermeidung am Zielort
            if target_path.exists() and target_path != dupe_path:
                stem = target_path.stem
                suffix = target_path.suffix
                counter = 1
                while target_path.exists():
                    target_path = target_path.parent / f"{stem}_dup{counter}{suffix}"
                    counter += 1

            if not dry_run:
                shutil.move(str(dupe_path), str(target_path))

            stats["moved"] += 1

        except Exception as e:
            stats["errors"] += 1
            log(f"[dedup] Fehler beim Verschieben von {dupe_path.name}: {e}")

        if idx % 1000 == 0 or idx == len(dupes_to_move):
            pct = (idx / len(dupes_to_move)) * 100.0
            log(f"[dedup] Fortschritt: {idx}/{len(dupes_to_move)} ({pct:.1f}%) | Verschoben: {stats['moved']} | Fehler: {stats['errors']}")

    elapsed = time.time() - t0
    log(f"[dedup] Verschiebung abgeschlossen in {elapsed:.2f}s.")

    return stats


def clean_empty_directories(root_dirs: list[Path], log=print) -> int:
    """Entfernt leere Ordner in den Quellverzeichnissen nach dem Verschieben."""
    removed = 0
    for rdir in root_dirs:
        for dirpath, dirnames, filenames in os.walk(rdir, topdown=False):
            dp = Path(dirpath)
            if dp == rdir:
                continue
            try:
                if not os.listdir(dp):
                    dp.rmdir()
                    removed += 1
            except Exception:
                pass
    if removed > 0:
        log(f"[dedup] {removed} leere Unterordner bereinigt.")
    return removed


def run_deduplication(
    suno_dirs: list[Path] | None = None,
    dest_dir: Path = DEFAULT_DEST_DIR,
    dry_run: bool = False,
    clean_empty: bool = True,
    workers: int = 32,
    log=print,
) -> dict[str, Any]:
    """Führt die vollständige Deduplizierung und Verschiebung durch."""
    if suno_dirs is None:
        suno_dirs = get_suno_directories(DEFAULT_MUSIK_ROOT)

    dupes, scan_stats = find_duplicates(suno_dirs, workers=workers, log=log)
    
    if not dupes:
        log("\n✅ Keine doppelten Dateien gefunden. Alle Dateien sind eindeutig.")
        return scan_stats

    move_stats = move_duplicates_to_destination(
        dupes_to_move=dupes,
        dest_root=dest_dir,
        source_root=DEFAULT_MUSIK_ROOT,
        dry_run=dry_run,
        log=log,
    )

    if clean_empty and not dry_run:
        clean_empty_directories(suno_dirs, log=log)

    log(f"\n╔════════════════════════════════════════════════════════════════════════════════╗")
    log(f"║ 🎯 SUNO DEDUPLIZIERUNG & VERSCHIEBUNG ABSCHLUSS-REPORT                         ║")
    log(f"╠════════════════════════════════════════════════════════════════════════════════╣")
    log(f"║ • Gescannte Suno-Dateien:   {scan_stats['total_files']:<50} ║")
    log(f"║ • Gefundene Duplikate:      {scan_stats['duplicate_count']:<50} ║")
    log(f"║ • Verschoben nach 'doppelt':{move_stats['moved']:<50} ║")
    log(f"║ • Duplikat-Datenvolumen:    {scan_stats['duplicate_bytes'] / (1024*1024):.2f} MB{' ' * 38} ║")
    log(f"║ • Aufteilung Dateitypen:    {str(scan_stats['ext_stats'])[:50]:<50} ║")
    log(f"║ • Fehler / Warnungen:       {move_stats['errors']:<50} ║")
    log(f"║ • Zielordner:               {str(dest_dir):<50} ║")
    log(f"╚════════════════════════════════════════════════════════════════════════════════╝")

    return {**scan_stats, **move_stats}


def main():
    parser = argparse.ArgumentParser(description="Suno Music Duplicate Finder & Safe Mover")
    parser.add_argument("--dest-dir", type=str, default=str(DEFAULT_DEST_DIR), help="Zielordner für Duplikate")
    parser.add_argument("--dry-run", action="store_true", help="Nur scannen, keine Dateien verschieben")
    parser.add_argument("--no-clean-empty", action="store_true", help="Leere Ordner nicht entfernen")
    parser.add_argument("--workers", type=int, default=32, help="Anzahl paralleler Hashing-Threads")
    args = parser.parse_args()

    suno_dirs = get_suno_directories(DEFAULT_MUSIK_ROOT)
    run_deduplication(
        suno_dirs=suno_dirs,
        dest_dir=Path(args.dest_dir),
        dry_run=args.dry_run,
        clean_empty=not args.no_clean_empty,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
