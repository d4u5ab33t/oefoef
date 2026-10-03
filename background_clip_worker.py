#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
background_clip_worker.py — Hintergrund-Worker für schonendes Einlesen neuer Clips
und semantische Aufwertung/Anreicherung bestehender Clips mit Low Priority.

Features:
  - Läuft mit Windows BELOW_NORMAL_PRIORITY_CLASS (kein Ruckeln/Lag für den User).
  - Erkennt und analysiert neue Clips im ClipPool (_raw_reorga__).
  - Wertet bestehende Clips mit CONCEPT_CLUSTERS, Objekt-Grounding und detailreichen
    Beschreibungen auf.
  - Speichert Fortschritt atomar alle N Clips in libsync-flat-globe.db.json.
  - Unterbrechungs- und neustartsicher.

Nutzung:
    python background_clip_worker.py               # Führt Ingestion + Enrichment im Hintergrund aus
    python background_clip_worker.py --loop        # Dauerhafter Hintergrund-Dämon (prüft alle X Minuten)
    python background_clip_worker.py --ingest-only # Nur neue Clips einlesen
    python background_clip_worker.py --enrich-only # Nur bestehende Clips beschreiben
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

import db
import clip_pool
from config import CLIP_POOL_DIR, TAG_VOCAB
from mp3_scanner import build_tag_vector
from creative_genome import information_density
from semantic_matching import (
    CONCEPT_CLUSTERS,
    CLUSTER_BITS,
    CLUSTER_EMOJIS,
    extract_clip_terms,
    compute_cluster_mask,
)


def set_low_priority():
    """Setzt die Prozesspriorität unter Windows auf BELOW_NORMAL_PRIORITY_CLASS."""
    if sys.platform == "win32":
        try:
            # BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            # IDLE_PRIORITY_CLASS = 0x00000040
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetPriorityClass(handle, 0x00004000)
            print("[worker] Prozesspriorität erfolgreich auf 'BELOW NORMAL' (Low Priority) gesetzt.")
        except Exception as e:
            print(f"[worker] Hinweis: Konnte Prozesspriorität nicht anpassen ({e}).")


def enrich_clip_metadata(path: str, meta: dict) -> tuple[dict, bool]:
    """Wertet die Metadaten und Beschreibung eines einzelnen Clips auf."""
    changed = False

    # 1. Tags anreichern
    existing_tags = set(t.lower() for t in (meta.get("tags") or []))
    path_tags = set(clip_pool._tags_from_path(path))
    new_tags = sorted(existing_tags | path_tags)

    if new_tags != (meta.get("tags") or []):
        meta["tags"] = new_tags
        changed = True

    # 2. Term-Menge & Konzept-Cluster
    clip_terms = extract_clip_terms(meta)
    cluster_mask = compute_cluster_mask(clip_terms)
    if meta.get("cluster_mask") != cluster_mask:
        meta["cluster_mask"] = cluster_mask
        changed = True

    # 3. Active Clusters ermitteln
    active_cluster_names = []
    for cname, cbit in CLUSTER_BITS.items():
        if cluster_mask & cbit:
            active_cluster_names.append(CLUSTER_EMOJIS.get(cname, cname))

    # 4. Gender & Gender Vector
    gv = clip_pool._gender_vector(new_tags, path=path)
    if meta.get("gender_vector") != gv:
        meta["gender_vector"] = gv
        changed = True

    female_hits = gv.get("female", [])
    male_hits = gv.get("male", [])
    expected_gender = "dual" if (female_hits and male_hits) else ("female" if female_hits else ("male" if male_hits else "neutral"))
    if meta.get("gender") != expected_gender:
        meta["gender"] = expected_gender
        changed = True

    # 5. Tag Vector & Information Density
    if "vector" not in meta or not meta["vector"] or not any(meta["vector"]):
        vec = build_tag_vector(new_tags)
        if vec != meta.get("vector"):
            meta["vector"] = vec
            changed = True

    info_dens = information_density(meta)
    if meta.get("information_density") != info_dens:
        meta["information_density"] = info_dens
        changed = True

    # 6. Detaillierte semantische Beschreibung generieren
    w = meta.get("width", 0)
    h = meta.get("height", 0)
    aspect = "16:9" if (w > h and h > 0) else ("9:16" if (h > w) else "1:1")
    dur = meta.get("duration", 0.0)
    motion = meta.get("motion_score", 0.0)
    motion_label = "high-motion" if motion > 0.65 else ("mid-motion" if motion > 0.3 else "calm")

    desc_parts = [f"[{aspect}, {dur:.1f}s, {motion_label} ({motion:.2f})]"]
    if active_cluster_names:
        desc_parts.append(", ".join(active_cluster_names[:3]))
    elif new_tags:
        desc_parts.append(", ".join(new_tags[:4]))
    if expected_gender in ("male", "female", "dual"):
        desc_parts.append(f"MC: {expected_gender}")

    objects = meta.get("objects") or []
    if objects:
        obj_names = [o if isinstance(o, str) else o.get("label", "") for o in objects]
        obj_names = [o for o in obj_names if o]
        if obj_names:
            desc_parts.append(f"Obj: {', '.join(obj_names[:3])}")

    desc_parts.append(f"Density: {info_dens:.2f}")
    new_desc = " | ".join(desc_parts)

    # Learned Feedback Suffix bewahren falls vorhanden
    learned = meta.get("learned")
    if learned and learned.get("uses", 0) > 0:
        new_desc = clip_pool._apply_learned_suffix(new_desc, learned)

    if meta.get("description") != new_desc:
        meta["description"] = new_desc
        changed = True

    return meta, changed


def run_ingestion(globe: dict, sleep_sec: float = 0.02, save_every: int = 50) -> int:
    """Findet unanalysierte Clips auf der Festplatte und liest sie mit Low-Prio ein."""
    print("[worker] Scanne ClipPool auf neue/unanalysierte Dateien ...")
    try:
        disk_clips = clip_pool.find_clips()
    except Exception as e:
        print(f"[worker] Fehler beim Suchen der Clips: {e}")
        return 0

    unseen = [p for p in disk_clips if p not in globe or globe[p].get("failed")]
    total_unseen = len(unseen)
    print(f"[worker] {len(disk_clips)} Dateien auf Disk gefunden | {len(globe)} im Cache | {total_unseen} neue Clips zu verarbeiten.")

    if total_unseen == 0:
        return 0

    processed = 0
    saved_count = 0

    for idx, path in enumerate(unseen, 1):
        try:
            meta = clip_pool.analyze_clip(path)
            meta, _ = enrich_clip_metadata(path, meta)
            globe[path] = meta
            processed += 1
            saved_count += 1

            if idx % 10 == 0 or idx == total_unseen:
                progress_pct = (idx / total_unseen) * 100.0
                print(f"[worker] Ingestion: {idx}/{total_unseen} ({progress_pct:.1f}%) -> {Path(path).name}")

            if saved_count >= save_every:
                db.save_flat_globe(globe)
                saved_count = 0

        except Exception as e:
            print(f"[worker] Fehler bei Clip {path}: {e}")
            globe[path] = {"failed": True, "error": str(e), "analyzed_at": time.time()}

        if sleep_sec > 0:
            time.sleep(sleep_sec)

    if saved_count > 0:
        db.save_flat_globe(globe)

    print(f"[worker] Ingestion abgeschlossen: {processed} neue Clips eingelesen und gespeichert.")
    return processed


def run_enrichment(globe: dict, sleep_sec: float = 0.005, save_every: int = 100) -> int:
    """Wertet alle bestehenden Einträge im Flat Globe mit Konzept-Clustern & Beschreibungen auf."""
    total_clips = len(globe)
    print(f"[worker] Starte semantische Anreicherung für {total_clips} Clips ...")

    enriched_count = 0
    saved_count = 0

    for idx, (path, meta) in enumerate(globe.items(), 1):
        if not meta or meta.get("failed"):
            continue

        meta, changed = enrich_clip_metadata(path, meta)
        if changed:
            globe[path] = meta
            enriched_count += 1
            saved_count += 1

        if idx % 500 == 0 or idx == total_clips:
            pct = (idx / total_clips) * 100.0
            print(f"[worker] Enrichment: {idx}/{total_clips} ({pct:.1f}%) | {enriched_count} Clips verbessert")

        if saved_count >= save_every:
            db.save_flat_globe(globe)
            saved_count = 0

        if sleep_sec > 0:
            time.sleep(sleep_sec)

    if saved_count > 0:
        db.save_flat_globe(globe)

    print(f"[worker] Enrichment abgeschlossen: {enriched_count} Clips aufgewertet und gespeichert.")
    return enriched_count


def main():
    parser = argparse.ArgumentParser(description="OIDASHEIM Background Clip Ingestion & Enrichment Worker")
    parser.add_argument("--ingest-only", action="store_true", help="Nur neue Clips einlesen")
    parser.add_argument("--enrich-only", action="store_true", help="Nur bestehende Clips anreichern")
    parser.add_argument("--loop", action="store_true", help="Dauerhafter Hintergrund-Dämon")
    parser.add_argument("--interval-min", type=int, default=15, help="Wartezeit zwischen Dämon-Zyklen in Minuten")
    parser.add_argument("--sleep-ms", type=int, default=15, help="Schlafzeit pro Clip in ms (schont CPU)")
    args = parser.parse_args()

    set_low_priority()
    sleep_sec = max(0.001, args.sleep_ms / 1000.0)

    while True:
        print("\n" + "=" * 60)
        print(f"[worker] Starte Worker-Zyklus um {time.strftime('%Y-%m-%d %H:%M:%S')} (Low Priority)")
        print("=" * 60)

        globe = db.load_flat_globe()

        if not args.enrich_only:
            run_ingestion(globe, sleep_sec=sleep_sec)

        if not args.ingest_only:
            run_enrichment(globe, sleep_sec=sleep_sec)

        summary = clip_pool.libsync_summary(globe)
        print("\n[worker] Flat Globe Status nach Durchlauf:")
        print(f"  • Gesamtanzahl Clips: {summary['total_clips']}")
        print(f"  • Playback OK:        {summary['playback_ok_clips']}")
        print(f"  • Gender Breakdown:   {summary['gender_breakdown']}")
        print(f"  • Seitenverhältnisse: {summary['aspect_ratios']}")

        if not args.loop:
            break

        print(f"\n[worker] Zyklus beendet. Schlafe {args.interval_min} Minuten bis zum nächsten Check...")
        time.sleep(args.interval_min * 60)


if __name__ == "__main__":
    main()
