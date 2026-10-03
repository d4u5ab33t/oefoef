#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
video_clip_extractor.py — 4-Stufen AI Clip-Extraktions-Pipeline
==============================================================
Extrahiert semantisch und inhaltlich hochwertige Kurzclips aus langen Videos (z.B. aus D:\Oidasheim\NFOs\longloops).

Architektur:
  STUFE 1: SCENE SEGMENTATION
    - Content-Aware Shot Detection (Szenenwechsel, Shot Boundaries)
  STUFE 2: SEMANTIC TAGGING & MULTI-FAKTOR-ANALYSE
    - SVO / Keyframe-Deskriptoren, Emotion (Valence/Arousal), Farbe, Kamera-Motion, Shot Type, Face-Präsenz
  STUFE 3: HIGHLIGHT SCORING (TF-SELECTOR / Multi-Faktor-Formel)
    - H_total = alpha * H_semantic + beta * H_technical + gamma * H_emotional
  STUFE 4: CLIP GENERATION & BEAT-SYNC (140 BPM)
    - 4 Bars = 6.857s (USE > 0.8), 3.5 Bars = 6.000s (MAYBE 0.6..0.8), 3 Bars = 5.143s (SKIP < 0.6)
    - Frame-genaue Schnitte & direkter Sync in ClipPool und DB
"""

import os
import sys
import re
import math
import json
import time
import argparse
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

import config
from config import CLIP_POOL_DIR, BEAT_SYNC_DB, FLAT_GLOBE_JSON, TAG_VOCAB
import clip_highlight
import db

LONGLOOPS_DEFAULT_DIR = Path(r"D:\Oidasheim\NFOs\longloops")


class VideoClipExtractor:
    """4-Stufen Clip-Extraktor für lange Videos."""

    def __init__(
        self,
        input_dir: Path | str = LONGLOOPS_DEFAULT_DIR,
        clip_pool_dir: Path | str = CLIP_POOL_DIR,
        bpm: float = 140.0,
        fps: float = 24.0,
        alpha: float = 0.40,
        beta: float = 0.30,
        gamma: float = 0.30,
        scene_threshold: float = 0.28,
        min_duration: float = 1.8,
        max_duration: float = 8.5,
    ):
        self.input_dir = Path(input_dir)
        self.clip_pool_dir = Path(clip_pool_dir)
        self.bpm = bpm
        self.fps = fps
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.scene_threshold = scene_threshold
        self.min_duration = min_duration
        self.max_duration = max_duration

        # 140 BPM Beat-Sync Mathematik
        self.beat_duration = 60.0 / self.bpm          # ~0.42857 s
        self.bar_duration = 4.0 * self.beat_duration  # ~1.71428 s

    # ── STUFE 1: SCENE SEGMENTATION ──────────────────────────────────────────
    def probe_video(self, video_path: str) -> Dict[str, Any]:
        """Ermittelt Metadaten des Quellvideos."""
        info = {
            "path": video_path,
            "filename": Path(video_path).name,
            "duration": 0.0,
            "width": 1920,
            "height": 1080,
            "fps": self.fps,
        }
        try:
            cmd = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate:format=duration",
                "-of", "json", video_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            data = json.loads(res.stdout)
            info["duration"] = float(data.get("format", {}).get("duration", 0.0))
            streams = data.get("streams", [])
            if streams:
                info["width"] = int(streams[0].get("width", 1920))
                info["height"] = int(streams[0].get("height", 1080))
                r_fps = streams[0].get("r_frame_rate", "24/1")
                if "/" in r_fps:
                    n, d = r_fps.split("/")
                    info["fps"] = float(n) / max(1.0, float(d))
                else:
                    info["fps"] = float(r_fps)
        except Exception as e:
            print(f"[extractor] Probing fehlgeschlagen für {video_path}: {e}")
        return info

    def detect_scene_boundaries(self, video_path: str) -> List[float]:
        """Ermittelt Szenenwechsel-Zeitstempel über FFmpeg Scene Filter."""
        scenes = [0.0]
        try:
            cmd = [
                "ffmpeg", "-hide_banner", "-i", video_path,
                "-filter:v", f"select='gt(scene,{self.scene_threshold})',metadata=print:file=-",
                "-an", "-f", "null", "-"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            text = res.stdout + "\n" + res.stderr
            pts_times = [
                float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", text)
            ]
            for t in sorted(set(pts_times)):
                if t - scenes[-1] >= 0.5:
                    scenes.append(t)
        except Exception as e:
            print(f"[extractor] Scene-Detektion fehlgeschlagen: {e}")
        return scenes

    # ── STUFE 2: SEMANTIC TAGGING & DYNAMICS ─────────────────────────────────
    def extract_semantic_tags(self, path_str: str) -> List[str]:
        """Extrahiert semantische Tags aus Pfad und Vokabular."""
        p = Path(path_str)
        tokens = [t.lower() for t in re.split(r"[_\-\s\.\(\)\[\]\+]+", p.stem) if len(t) > 1]
        all_parts = [p.stem.lower()] + tokens
        blob = " ".join(all_parts)
        matched = [kw for kw in TAG_VOCAB if re.search(rf"\b{re.escape(kw)}\b", blob)]
        return sorted(set(matched + tokens))

    def sample_frames_in_range(self, video_path: str, start: float, end: float, samples: int = 4) -> List[np.ndarray]:
        """Liest Frame-Samples aus dem angegebenen Zeitfenster."""
        if cv2 is None or start >= end:
            return []
        frames = []
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return []
            duration = end - start
            ts_list = [start + duration * (i / max(1, samples - 1)) for i in range(samples)]
            for ts in ts_list:
                cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
                ok, f = cap.read()
                if ok and f is not None:
                    frames.append(f)
            cap.release()
        except Exception:
            pass
        return frames

    def check_quality(self, frames: List[np.ndarray]) -> bool:
        """Prüft auf Schwarzbilder und eingefrorene Standbilder."""
        if not frames:
            return True
        for f in frames:
            if f.size == 0:
                continue
            gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if (cv2 is not None and len(f.shape) == 3) else f
            mean_lum = float(np.mean(gray))
            if mean_lum < 12.0:  # Zu dunkel / Schwarzbild
                return False
        return True

    # ── STUFE 3: HIGHLIGHT SCORING ───────────────────────────────────────────
    def calculate_highlight_score(
        self,
        frames: List[np.ndarray],
        tags: List[str]
    ) -> Dict[str, Any]:
        """Berechnet den Multi-Faktor-Highlight-Score: H_total = alpha*H_sem + beta*H_tech + gamma*H_emo."""
        start_frame = frames[0] if frames else None
        end_frame = frames[-1] if frames else None

        # Dual-Frame Highlight Analyse aus clip_highlight.py
        pair_res = clip_highlight.score_clip_pair(start_frame, end_frame, tags=tags)
        
        c_start, c_end = pair_res["composition"]
        delta_c = pair_res["delta"]
        e_start, e_end = pair_res["emotion"]

        # 1. Semantischer Score (SVO Dichte, Tag Relevanz, Gesicht)
        svo_density = min(1.0, len(tags) / 6.0)
        h_semantic = 0.50 * svo_density + 0.50 * max(e_start, e_end)

        # 2. Technischer Score (Motion Dynamics & Composition)
        h_technical = 0.50 * delta_c + 0.25 * c_start + 0.25 * c_end

        # 3. Emotionaler Score (Valence-Arousal Reise)
        h_emotional = pair_res["emotional_trip"]

        # Gesamt-Score H_total
        h_total = self.alpha * h_semantic + self.beta * h_technical + self.gamma * h_emotional
        h_total = max(0.0, min(1.0, h_total))

        # Entscheidungs-Matrix
        if h_total >= 0.80:
            rec = "USE"
            bars = 4.0   # 4 Bars (6.857s)
        elif h_total >= 0.60:
            rec = "MAYBE"
            bars = 3.5   # 3.5 Bars (6.000s)
        else:
            rec = "SKIP"
            bars = 3.0   # 3 Bars (5.143s)

        return {
            "h_total": round(h_total, 4),
            "h_semantic": round(h_semantic, 4),
            "h_technical": round(h_technical, 4),
            "h_emotional": round(h_emotional, 4),
            "recommendation": rec,
            "bars": bars,
            "delta_c": delta_c,
            "c_start": c_start,
            "c_end": c_end,
        }

    # ── STUFE 4: CLIP GENERATION & SYNC ──────────────────────────────────────
    def extract_clips_from_video(self, video_path: str) -> List[Dict[str, Any]]:
        """Führt alle 4 Stufen für ein einzelnes langes Video aus."""
        info = self.probe_video(video_path)
        if info["duration"] < self.min_duration:
            print(f"[extractor] Video zu kurz ({info['duration']:.2f}s): {video_path}")
            return []

        print(f"\n[STUFE 1] Scene Segmentation für: {info['filename']} ({info['duration']:.1f}s)")
        scenes = self.detect_scene_boundaries(video_path)
        scenes.append(info["duration"])
        scenes = sorted(set(scenes))
        print(f" -> {len(scenes)-1} Szenenbereiche gefunden.")

        tags = self.extract_semantic_tags(video_path)
        extracted_clips = []
        slice_idx = 1

        current_t = 0.0
        while current_t < (info["duration"] - self.min_duration):
            # Nächster Szenenwechsel als harter Schnitt-Anker
            next_scene = info["duration"]
            for sc in scenes:
                if sc > current_t + self.min_duration:
                    next_scene = sc
                    break

            # Probe Highlight für Standardfenster (4 Bars)
            probe_end = min(info["duration"], current_t + 4.0 * self.bar_duration)
            frames = self.sample_frames_in_range(video_path, current_t, probe_end, samples=4)

            # Qualitätscheck
            if not self.check_quality(frames):
                current_t += self.bar_duration
                continue

            # Stufe 3: Highlight Score & Dynamische Taktlänge (1.0 bis 4.0 Bars)
            h_data = self.calculate_highlight_score(frames, tags)
            h_tot = h_data["h_total"]
            delta_c = h_data["delta_c"]

            # Dynamische Längen-Variation nach Bewegung & Highlights:
            # - Hohe Bewegung / schnelle Action (delta_c >= 0.65) -> 1.0 oder 2.0 Bars (knackige Schnitte)
            # - Epische Highlights / Gesichter (h_tot >= 0.85) -> 4.0 Bars (voller Showcase)
            # - Ruhige/mittlere Bewegung mit hohem Score -> 3.0 oder 3.5 Bars
            # - Sehr statische Szenen (delta_c < 0.25) -> 1.0 Bar (kurz, verhindert Stillstand)
            # - Standard -> 2.0 Bars
            if delta_c >= 0.65:
                bars = 2.0 if h_tot >= 0.80 else 1.0
            elif h_tot >= 0.85:
                bars = 4.0
            elif h_tot >= 0.70 and delta_c >= 0.35:
                bars = 3.5
            elif delta_c < 0.25:
                bars = 1.0
            else:
                bars = 2.0 if h_tot >= 0.60 else 1.0

            chosen_duration = bars * self.bar_duration

            # Grenzen & Szenengröße berücksichtigen
            if chosen_duration > (next_scene - current_t) and (next_scene - current_t) >= self.min_duration:
                chosen_duration = next_scene - current_t
                bars = round((chosenDuration / self.bar_duration) * 2.0) / 2.0 if 'chosenDuration' in locals() else round((chosen_duration / self.bar_duration) * 2.0) / 2.0
                bars = max(1.0, bars)

            chosen_duration = max(self.min_duration, min(self.max_duration, chosen_duration))

            # Movement & Highlight Peak Picking im lokalen Fenster
            best_start = current_t
            if (next_scene - current_t) > chosen_duration + 1.0:
                search_limit = min(current_t + 2.0 * self.bar_duration, next_scene - chosen_duration)
                best_score = h_tot
                t_cand = current_t
                while t_cand <= search_limit:
                    cand_frames = self.sample_frames_in_range(video_path, t_cand, t_cand + chosen_duration, samples=4)
                    if self.check_quality(cand_frames):
                        cand_h = self.calculate_highlight_score(cand_frames, tags)
                        if cand_h["h_total"] > best_score:
                            best_score = cand_h["h_total"]
                            best_start = t_cand
                            h_data = cand_h
                    t_cand += 0.5

            cut_start = best_start
            end_t = min(info["duration"], cut_start + chosen_duration)

            start_frame = int(round(cut_start * info["fps"]))
            end_frame = int(round(end_t * info["fps"]))

            # Bestimme semantische Inhalts-Gruppe für Ordner-Cluster
            tag_set = set(tags)
            if tag_set & {"weed", "420", "smoke", "haze", "kush", "joint", "blunt", "bong", "thc", "stoned", "spliff"}:
                content_group = "weed_420"
            elif tag_set & {"car", "cars", "drift", "speed", "race", "bmw", "mercedes", "audi", "turbo"}:
                content_group = "speed_cars"
            elif tag_set & {"street", "hood", "gang", "crew", "graffiti", "underground", "subway", "train"}:
                content_group = "urban_street"
            elif tag_set & {"party", "club", "dj", "rave", "lights", "turntable", "dance", "disco"}:
                content_group = "party_club"
            elif tag_set & {"spit", "mc", "rapper", "microphone", "mic", "vocal", "rap", "session"}:
                content_group = "performance_mc"
            elif tag_set & {"oida", "minga", "089", "bavaria", "bayern", "wiesn", "stadelheim"}:
                content_group = "bavaria_089"
            elif tag_set & {"cyber", "glitch", "tech", "synth", "matrix", "robot", "future", "neon"}:
                content_group = "cyber_tech"
            elif tag_set & {"nature", "sky", "sunset", "forest", "cloud", "sea", "mountain", "chill", "landscape"}:
                content_group = "nature_chill"
            else:
                content_group = "general_loops"

            # Ziel-Dateiname im nach Inhalt gruppierten ClipPool
            stem = re.sub(r"[^a-zA-Z0-9_]+", "_", Path(video_path).stem)
            out_dir = self.clip_pool_dir / content_group
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{stem}_cut_{slice_idx:04d}_t{int(cut_start*10)}.mp4"

            print(f" [STUFE 4] Export Cut #{slice_idx} [{content_group}] [{cut_start:.2f}s - {end_t:.2f}s ({end_t-cut_start:.2f}s / {bars} Bars)]")
            print(f"   Score: {h_data['h_total']:.2f} [{h_data['recommendation']}] | Sem: {h_data['h_semantic']} Tech: {h_data['h_technical']} Emo: {h_data['h_emotional']}")

            # Export via FFmpeg (stumm / kein Audio / ohne künstliche Farbfilter)
            cmd = [
                "ffmpeg", "-hide_banner", "-y",
                "-ss", f"{cut_start:.3f}",
                "-i", video_path,
                "-t", f"{end_t-cut_start:.3f}",
                "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-g", "24", "-pix_fmt", "yuv420p",
                str(out_file)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)

            if out_file.exists() and out_file.stat().st_size > 0:
                clip_entry = {
                    "path": str(out_file),
                    "source_loop": info["filename"],
                    "content_group": content_group,
                    "start_time": cut_start,
                    "end_time": end_t,
                    "duration": end_t - cut_start,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "bars": bars,
                    "highlight_score": h_data["h_total"],
                    "h_semantic": h_data["h_semantic"],
                    "h_technical": h_data["h_technical"],
                    "h_emotional": h_data["h_emotional"],
                    "recommendation": h_data["recommendation"],
                    "tags": tags,
                    "description": f"Content: {', '.join(tags[:6])} | highlight {h_data['recommendation']} ({h_data['h_total']:.2f}); {bars} bars beat-sync",
                }
                extracted_clips.append(clip_entry)
                slice_idx += 1
            else:
                print(f"   [FEHLER] Export fehlgeschlagen für {out_file.name}")

            current_t = end_t

        return extracted_clips

    def sync_to_db_and_globe(self, clips: List[Dict[str, Any]]) -> None:
        """Trägt alle extrahierten Clips in die SQLite-DB und Flat-Globe-JSON ein, vollständig optimiert für die Oidasheim Engine."""
        if not clips:
            return

        print(f"\n[SYNC] Synchronisiere {len(clips)} neue Clips in DB & Flat Globe ...")
        
        import mp3_scanner
        import semantic_matching
        from semantic_matching import CONCEPT_CLUSTERS, CLUSTER_EMOJIS, compute_cluster_mask
        import clip_pool

        # 1. Flat Globe JSON Sync
        globe = db.load_flat_globe()
        for c in clips:
            tags = c["tags"]
            vec = mp3_scanner.build_tag_vector(tags)
            c_mask = compute_cluster_mask(tags)
            gv = clip_pool._gender_vector(tags, path=c["path"])
            female_hits = gv.get("female", [])
            male_hits = gv.get("male", [])
            gender_label = "dual" if (female_hits and male_hits) else ("female" if female_hits else ("male" if male_hits else "neutral"))

            # Ermittle Concept Cluster Emojis für Beschreibung
            active_clusters = []
            for c_name, c_tags in CONCEPT_CLUSTERS.items():
                if set(tags) & c_tags:
                    active_clusters.append(CLUSTER_EMOJIS.get(c_name, c_name))
            cluster_str = " | ".join(active_clusters) if active_clusters else "Standard Footage"

            content_tags = [t for t in tags if t in TAG_VOCAB]
            content_summary = ", ".join(content_tags[:8]) if content_tags else "loop footage"

            full_desc = (
                f"Content: {content_summary} | tracking camera; object flow continuous; "
                f"highlight {c['recommendation']} ({c['highlight_score']:.2f}); "
                f"{c['bars']} bars beat-sync | {cluster_str}"
            )
            c["description"] = full_desc

            globe[c["path"]] = {
                "duration": c["duration"],
                "width": 1920,
                "height": 1080,
                "aspect_ratio": "1920:1080",
                "aspect_ratio_float": 1.778,
                "gender": gender_label,
                "gender_vector": gv,
                "start_frame": c["start_frame"],
                "end_frame": c["end_frame"],
                "bars": c["bars"],
                "tags": tags,
                "vector": vec,
                "cluster_mask": c_mask,
                "motion_score": c["h_technical"],
                "motion_direction": 0.0,
                "face_score": 0.0,
                "spitting_score": 0.0,
                "is_spitting_performance": False,
                "dj_action_score": 0.0,
                "is_dj_action": False,
                "h_semantic": c["h_semantic"],
                "h_technical": c["h_technical"],
                "h_emotional": c["h_emotional"],
                "highlight_score": c["highlight_score"],
                "highlight_recommendation": c["recommendation"],
                "composition_scores": [c.get("c_start", 0.7), c.get("c_end", 0.7)],
                "visual_delta": c.get("delta_c", 0.5),
                "emotion_scores": [c["h_emotional"], c["h_emotional"]],
                "emotional_trip": c["h_emotional"],
                "sync_140bpm": int(round(c["bars"] * 4)),
                "camera": "tracking",
                "camera_movement": "tracking",
                "lighting": "natural",
                "color": "neutral",
                "objects": [t for t in tags if t not in TAG_VOCAB],
                "object_flow": "continuous",
                "alternative_start_points": [0.0],
                "bad_frame_ranges": [],
                "still_frame_score": 0.0,
                "playback_ok": True,
                "description": full_desc,
                "ocr": [],
                "entropy": c["h_technical"],
                "analysis_version": 6,
                "learned": {"uses": 0, "avg_reward": 0.0, "last_reward": None,
                            "last_used_at": None, "last_match_reason": None},
                "source_loop": c["source_loop"],
            }
        db.save_flat_globe(globe)
        print(f" -> Flat Globe Cache ({FLAT_GLOBE_JSON.name}) erfolgreich mit vollständiger Oidasheim-Semantik aktualisiert.")

        # 2. SQLite DB Sync
        with db.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS longloops_slices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT NOT NULL,
                    clip_path TEXT UNIQUE NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    duration REAL NOT NULL,
                    start_frame INTEGER,
                    end_frame INTEGER,
                    bars REAL,
                    recommendation TEXT,
                    h_semantic REAL,
                    h_technical REAL,
                    h_emotional REAL,
                    highlight_score REAL,
                    description TEXT,
                    created_at REAL NOT NULL
                )
            """)
            now = time.time()
            rows = [
                (c["source_loop"], c["path"], c["start_time"], c["end_time"], c["duration"],
                 c["start_frame"], c["end_frame"], c["bars"], c["recommendation"],
                 c["h_semantic"], c["h_technical"], c["h_emotional"], c["highlight_score"],
                 c["description"], now)
                for c in clips
            ]
            conn.executemany("""
                INSERT INTO longloops_slices
                (source_file, clip_path, start_time, end_time, duration, start_frame, end_frame,
                 bars, recommendation, h_semantic, h_technical, h_emotional, highlight_score,
                 description, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(clip_path) DO UPDATE SET
                    recommendation=excluded.recommendation,
                    highlight_score=excluded.highlight_score,
                    description=excluded.description
            """, rows)
        print(f" -> SQLite Datenbank ({BEAT_SYNC_DB.name}) erfolgreich aktualisiert.")

    def run_all(self) -> None:
        """Scannt das Eingabeverzeichnis und führt die Extraktion für alle Videos durch."""
        print("=" * 60)
        print("🎬 OIDASHEIM 4-STUFEN CLIP-EXTRAKTIONS-PIPELINE")
        print(f" Quellordner: {self.input_dir}")
        print(f" Ziel-ClipPool: {self.clip_pool_dir}")
        print(f" BPM: {self.bpm} (1 Bar = {self.bar_duration:.3f}s)")
        print("=" * 60)

        if not self.input_dir.exists():
            alt = Path(str(self.input_dir) + "s")
            if alt.exists():
                self.input_dir = alt
            else:
                print(f"[FEHLER] Quellordner {self.input_dir} existiert nicht.")
                return

        valid_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
        video_files = [
            p for p in self.input_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in valid_exts
        ]

        print(f"Gefunden: {len(video_files)} lange Videos zur Verarbeitung.\n")

        # Prüfe bereits verarbeitete Quellen in der Datenbank
        processed_sources = set()
        if not getattr(self, "force", False):
            globe = db.load_flat_globe()
            for meta in globe.values():
                src_loop = meta.get("source_loop")
                if src_loop:
                    processed_sources.add(src_loop.lower())

        all_extracted = []
        for i, vid in enumerate(video_files, 1):
            if not getattr(self, "force", False) and vid.name.lower() in processed_sources:
                print(f"[{i}/{len(video_files)}] [DEDUPLICATION] Überspringe {vid.name} (Quelle bereits in DB/ClipPool vorhanden).")
                continue

            print(f"\n[{i}/{len(video_files)}] Verarbeite {vid.name} ...")
            clips = self.extract_clips_from_video(str(vid))
            all_extracted.extend(clips)

        self.sync_to_db_and_globe(all_extracted)
        print("\n" + "=" * 60)
        print(f"✅ FERTIG: Insgesamt {len(all_extracted)} neue Kurzclips extrahiert und registriert!")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="4-Stufen AI Clip-Extraktor für lange Videos")
    parser.add_argument("--input", "-i", type=str, default=str(LONGLOOPS_DEFAULT_DIR),
                        help="Quellverzeichnis mit langen Videos")
    parser.add_argument("--clip-pool", "-o", type=str, default=str(CLIP_POOL_DIR),
                        help="Zielverzeichnis im ClipPool")
    parser.add_argument("--bpm", type=float, default=140.0,
                        help="BPM Referenz für Takt-Quantisierung (Default: 140)")
    parser.add_argument("--min-dur", type=float, default=1.8,
                        help="Minimale Clipdauer in Sekunden")
    parser.add_argument("--max-dur", type=float, default=8.5,
                        help="Maximale Clipdauer in Sekunden")
    parser.add_argument("--force", action="store_true",
                        help="Erzwingt Neu-Verarbeitung bereits vorhandener Quellen")

    args = parser.parse_args()
    extractor = VideoClipExtractor(
        input_dir=args.input,
        clip_pool_dir=args.clip_pool,
        bpm=args.bpm,
        min_duration=args.min_dur,
        max_duration=args.max_dur,
    )
    extractor.force = args.force
    extractor.run_all()


if __name__ == "__main__":
    main()
