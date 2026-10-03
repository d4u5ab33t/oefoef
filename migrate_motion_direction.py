"""
migrate_motion_direction.py — Patched-Upgrade v3/v4 -> v5 Cache-Einträge

Hebt Cache-Einträge unterhalb ANALYSIS_VERSION=5 auf den aktuellen Stand,
OHNE ffprobe/Face-Detection/Tags neu zu berechnen:
  - v3 -> braucht noch motion_direction: Frames werden neu gelesen (einziger
    teurer Teil, wie bisher)
  - v4 -> hat motion_direction schon, braucht nur noch die neuen v5-Felder
    ("ocr", "learned") als Default -> reiner Dict-Patch, KEIN Video-Decode
    nötig, quasi kostenlos

Läuft parallel über ProcessPoolExecutor, speichert alle 500 Clips einen
Zwischenstand (Ctrl+C-sicher, wie clip_pool.build_or_update_globe).
"""
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import db
from clip_pool import (
    _sample_frames,
    _motion_direction_from_frames,
    _file_fingerprint,
    ANALYSIS_VERSION,
)

_DEFAULT_LEARNED = {"uses": 0, "avg_reward": 0.0, "last_reward": None, "last_used_at": None}


def _patch_one(path: str, duration: float, stored_fp: str, analysis_version):
    """Läuft im Worker-Prozess: prüft Fingerprint, berechnet motion_direction
    NUR falls der Eintrag noch v3 ist (v4 hat es schon -> None = nichts zu tun).
    Bei geänderter/fehlender Datei wird NICHT gepatcht (bleibt unter v5 -> der
    normale main.py-Lauf übernimmt dann den vollen Re-Scan)."""
    p = Path(path)
    if not p.exists():
        return path, None, "missing"
    current_fp = _file_fingerprint(p)
    if current_fp != stored_fp:
        return path, None, "fingerprint_changed"
    motion_direction = None
    if analysis_version == 3:
        frames = _sample_frames(path, duration, samples=8)
        motion_direction = round(_motion_direction_from_frames(frames), 4)
    return path, motion_direction, "ok"


def main():
    globe = db.load_flat_globe()
    targets = [
        (path, entry.get("duration", 0.0), entry.get("fingerprint"))
        for path, entry in globe.items()
        if entry.get("analysis_version") == 3 and not entry.get("failed")
    ]
    print(f"[migrate] {len(targets)} Clips mit analysis_version=3 gefunden, "
          f"patche motion_direction ...", flush=True)

    done = 0
    skipped_missing = 0
    skipped_changed = 0
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=None) as executor:
        futures = {
            executor.submit(_patch_one, path, duration, fp): path
            for path, duration, fp in targets
        }

        try:
            for i, future in enumerate(as_completed(futures), 1):
                path, motion_direction, status = future.result()
                if status == "missing":
                    skipped_missing += 1
                elif status == "fingerprint_changed":
                    skipped_changed += 1
                else:
                    globe[path]["motion_direction"] = motion_direction
                    globe[path]["analysis_version"] = ANALYSIS_VERSION
                    done += 1

                if i % 500 == 0 or i == len(targets):
                    db.save_flat_globe(globe)
                    elapsed = time.time() - t0
                    print(f"[migrate] {i}/{len(targets)} verarbeitet "
                          f"(gepatcht={done}, fehlend={skipped_missing}, "
                          f"geändert={skipped_changed}) — {elapsed:.0f}s",
                          flush=True)
        except KeyboardInterrupt:
            print("[migrate] Abbruch — sichere Zwischenstand ...", flush=True)
            db.save_flat_globe(globe)
            raise

    db.save_flat_globe(globe)
    print(f"[migrate] Fertig: {done} Clips auf v{ANALYSIS_VERSION} gehoben, "
          f"{skipped_missing} fehlende Dateien, {skipped_changed} geänderte "
          f"Dateien (werden beim nächsten normalen main.py-Lauf regulär neu "
          f"analysiert).", flush=True)


if __name__ == "__main__":
    main()
