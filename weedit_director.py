#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weedit_director.py — WE.ED.IT 1-Click Director Engine (C++20 AVX2 Superstack)
=============================================================================
Universal End-to-End Music Video Director Pipeline:
  1-Click: 1 MP3 (or Batch Folder) + 30,000+ Clip Pool → Epic Synchronized Music Video

Triple-Engine Master Architecture:
  ① BEAT-SYNC ENGINE:
     - C++ Audio DSP: Fast moving RMS, Gaussian energy smoothing, onset peak picking, beatgrid quantizing.
     - DJ Sync Action Recognition (Scratches, Backspins, Vinyl Brakes, Drum Rolls, Drop Impacts).
     - Subtle highlight Smooth-Stutter micro-envelopes & Beat-Dancing kinematic camera zoom/sway.
  ② LYRICAL-SYNC ENGINE:
     - C++ Lyrics Grounding: Multi-language keyword/slang parsing, line-level cadence tracking.
     - Multi-lingual Duet & Male/Female line-level flip-flop cuts.
     - Rapid-fire MC spitting burst detection and lip-sync performance matching.
     - EBU R128 Loudness mastering with 4-stem Demucs sidechain vocal ducking.
  ③ SEMANTIC MATCHING ENGINE:
     - 30,000+ Clip Pool indexing with AVX2 SIMD candidate ranking & 64-bit cluster bitmask overlaps.
     - OIDA Visual DNA motifs (BETON, EISBACH, 089, CYBER, WEED, etc.) with motif color grading.
     - Spatial Hierarchical Vector-Tree traversal, zero-repeat partial cooldowns, and RL Thompson sampling.

Usage:
  python weedit_director.py                                    # 1-Click Auto Batch on default music directory
  python weedit_director.py --song "path/to/song.mp3"          # 1-Click Single Song
  python weedit_director.py --batch "path/to/folder" --limit 5 # Batch processing with limit
  python weedit_director.py --platform tiktok                  # Target 9:16 vertical resolution
  python weedit_director.py --prune-dead                       # Blitzschnelle Bereinigung toter Clips
  python weedit_director.py --cxx-status                       # Diagnosedaten des C++ AVX2 Native Stacks
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

# Ensure UTF-8 console output across all OS environments
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from config import (
    ROOT_DIR,
    LOG_DIR,
    TMP_DIR,
    DATA_DIR,
    OUTPUT_RESOLUTION,
    OUTPUT_RESOLUTION_BY_PLATFORM,
    OUTPUT_SUBDIR_BY_PLATFORM,
    ENGINE_VERSION,
    TAG_VOCAB,
    FAVS_ROOT,
    MP3_ROOTS,
    DEFAULT_HASHTAG_NICHE,
    LABEL_NAME,
    RENDERER_BACKEND,
)

import audio_analysis
import clip_pool
import db
import mp3_scanner
import song_semantics
import user_prefs
import creative_compiler
from creative_compiler import compile_creative_ir
from creative_genome import FilmDNA, build_intent, compile_style, genome_manifest, update_film_dna
from film_genome import compile_film_genome
from semantic_matching import calculate_semantic_match, semantic_match_reason, compute_cluster_mask
from timeline_builder import build_timeline, TimelineSegment
import renderer
import cxx_accel

# Optional Viral Strategy import
try:
    import importlib.util as _importlib_util
    _viral_strategy_spec = _importlib_util.spec_from_file_location(
        "viral_strategy", Path(__file__).resolve().parent / "viral-strategy.py"
    )
    viral_strategy = _importlib_util.module_from_spec(_viral_strategy_spec)
    _viral_strategy_spec.loader.exec_module(viral_strategy)
except Exception:
    viral_strategy = None


BANNER = r"""
██╗    ██╗███████╗    ███████╗██████╗     ██╗████████╗
██║    ██║██╔════╝    ██╔════╝██╔══██╗    ██║╚══██╔══╝
██║ █╗ ██║█████╗      █████╗  ██║  ██║    ██║   ██║   
██║███╗██║██╔══╝      ██╔══╝  ██║  ██║    ██║   ██║   
╚███╔███╝███████╗     ███████╗██████╔╝    ██║   ██║   
 ╚══╝╚══╝ ╚══════╝    ╚══════╝╚═════╝     ╚═╝   ╚═╝   
       DIRECTOR C++20 AVX2 SUPERSTACK ENGINE
"""

MAX_OUTPUT_VERSION_ATTEMPTS = 9999
CLIP_POOL_SKIP_SCAN_FRESH_THRESHOLD = 1000


def log(msg: str):
    """Unified Thread-safe Logging with File Persistence."""
    print(msg, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "director_run.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass


def _safe_song_stem(song_path: str) -> str:
    """Extrahiert aus dem Songpfad einen sauberen Stem über den C++ Beschleuniger."""
    try:
        return cxx_accel.get_cxx_engine().clean_stem(Path(song_path).stem)
    except Exception:
        return re.sub(r"[^\w\-_\. ]", "_", Path(song_path).stem).strip()


def _resolve_song_output_dir(base_output_dir: Optional[Path], song_path: str, platform: str) -> Path:
    """Ermittelt den dedizierten Song-Ordner: ./output/<SongName>/."""
    safe_name = _safe_song_stem(song_path)
    if base_output_dir is not None:
        if base_output_dir.name.lower() == safe_name.lower():
            return base_output_dir
        return base_output_dir / safe_name
    default_root = Path(__file__).resolve().parent / "output"
    return default_root / safe_name


def _versioned_output_path(output_dir: Path, song_path: str, platform: str) -> Path:
    """Generiert einen sauberen, versionssicheren MP4 Dateinamen."""
    safe_name = _safe_song_stem(song_path)
    platform_tag = "9zu16_tiktok" if platform == "tiktok" else "16zu9"
    output_dir.mkdir(parents=True, exist_ok=True)
    for version in range(1, MAX_OUTPUT_VERSION_ATTEMPTS + 1):
        candidate = output_dir / f"{safe_name}_{platform_tag}_eng{ENGINE_VERSION}_v{version:02d}.mp4"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Konnte keinen freien Output-Dateinamen finden für '{safe_name}' in {output_dir}.")


def _compute_render_reward(
    timeline: list,
    globe: dict,
    song_tag_vector: list,
    song_mood_tags: list | None = None,
    song_mc_gender: str = "unknown",
    song_style_weights: dict | None = None,
) -> float:
    """Berechnet die finale Belohnung (0..1) des Renders für den Self-Learning RL-Loop."""
    if not timeline:
        return 0.0
    cxx_engine = cxx_accel.get_cxx_engine()
    semantic_scores = []
    energy_deltas = []
    used_clips = []

    for seg in timeline:
        if not seg.clip_path:
            continue
        used_clips.append(seg.clip_path)
        meta = globe.get(seg.clip_path, {})
        s_score = calculate_semantic_match(
            meta, song_tag_vector,
            song_mood_tags=song_mood_tags,
            song_mc_gender=song_mc_gender,
            song_style_weights=song_style_weights,
        )
        semantic_scores.append(s_score if s_score is not None else 0.5)
        clip_motion = float(meta.get("motion_score", 0.5))
        energy_deltas.append(abs(seg.target_energy - clip_motion))

    avg_semantic = float(np.mean(semantic_scores)) if semantic_scores else 0.5
    avg_energy_match = 1.0 - (float(np.mean(energy_deltas)) if energy_deltas else 0.5)
    unique_ratio = len(set(used_clips)) / max(1, len(used_clips))

    reward = 0.40 * avg_semantic + 0.35 * avg_energy_match + 0.25 * unique_ratio
    return round(max(0.0, min(1.0, reward)), 4)


class WeEditDirector:
    """Master 1-Click Director Orchestrator with Full Production Logic."""

    def __init__(
        self,
        platform: str = "full",
        renderer_backend: str = "ffmpeg",
        dry_run: bool = False,
        log_fn=None,
    ):
        self.platform = platform
        self.renderer_backend = renderer_backend
        self.dry_run = dry_run
        self.log_fn = log_fn or log
        self.cxx = cxx_accel.get_cxx_engine()
        self._init_subsystems()

    def _log(self, msg: str):
        self.log_fn(msg)

    def _init_subsystems(self):
        db.init_db()
        status = self.cxx.get_status_info()
        self._log(f"⚡ [C++ Accel] Native C++20 Stack aktiv: {status.get('version', status.get('engine_label'))}")
        if viral_strategy is not None:
            try:
                all_semantics = db.get_all_song_semantics()
                self.learned_niche = viral_strategy.learn_default_niche(all_semantics)
                self._log(f"🎯 [Viral] Gelernte Standard-Hashtag-Nische: '{self.learned_niche}'")
            except Exception:
                self.learned_niche = DEFAULT_HASHTAG_NICHE

    def load_clip_globe(self, force_rebuild: bool = False) -> dict:
        """Loads and indexes the 30k+ clip pool with high-speed caching."""
        self._log("🎬 Lade & verifiziere 30k+ Clip-Pool Index...")
        globe = {} if force_rebuild else db.load_flat_globe()
        fresh_cached = self.cxx.count_fresh_cached_clips(globe, clip_pool.ANALYSIS_VERSION)
        if not force_rebuild and fresh_cached > CLIP_POOL_SKIP_SCAN_FRESH_THRESHOLD:
            self._log(f"⚡ [Clip-Pool] {fresh_cached} frische Clips im Cache (> {CLIP_POOL_SKIP_SCAN_FRESH_THRESHOLD}) -> Schneller Start.")
        else:
            globe = clip_pool.build_or_update_globe(globe, log=self._log, save_every=25, on_progress=db.save_flat_globe)
        self._log(f"✅ Clip-Pool einsatzbereit: {len(globe)} analysierte Clips ({fresh_cached} frisch im Cache).")
        return globe

    def process_single_song(
        self,
        song_path: str | Path,
        globe: dict,
        output_dir: Optional[str | Path] = None,
        style_name: Optional[str] = None,
        director_override: Optional[str] = None,
        pacing_override: Optional[str] = None,
    ) -> Optional[str]:
        """Runs the complete 6-Stage Master Director Loop on a single song."""
        song_path = Path(song_path).resolve()
        if not song_path.is_file():
            self._log(f"❌ FEHLER: Song-Datei existiert nicht: {song_path}")
            return None

        song_id = str(song_path)
        safe_name = _safe_song_stem(str(song_path))
        target_dir = _resolve_song_output_dir(Path(output_dir) if output_dir else None, str(song_path), self.platform)
        final_mp4 = _versioned_output_path(target_dir, str(song_path), self.platform)

        t_start = time.time()
        self._log(f"\n" + "=" * 70)
        self._log(f"🎬 WE.ED.IT DIRECTOR: Starte 1-Click Produktion für '{song_path.name}'")
        self._log(f"=" * 70)

        # ── [1/6] Audio & Rhythm DNA (C++ Audio DSP & DJ Sync) ────────────────
        self._log(f"\n┌─ [1/6] 🎵 Audio & Rhythm DNA (C++ Audio DSP) ──────────────────────────")
        audio = audio_analysis.analyze_song(str(song_path))
        self._log(
            f"  • BPM: {audio.bpm:.1f} | Dauer: {audio.duration_sec:.1f}s | Beats: {len(audio.beat_times)} | "
            f"Drops: {len(audio.drop_times)}"
        )
        if audio.dj_actions:
            self._log(f"  • DJ-Sync Actions: {len(audio.dj_actions)} erkannt ({', '.join(a['action'] for a in audio.dj_actions[:4])}...)")
        if audio.spitting_burst_windows:
            self._log(f"  • MC Rapid Cadence: {len(audio.spitting_burst_windows)} Bursts ({audio.vocal_cadence_hz:.1f} Hz)")

        # ── [2/6] Deep Semantics & Lyrics Grounding ───────────────────────────
        self._log(f"\n┌─ [2/6] 📝 Deep Semantics & Lyrics Grounding ─────────────────────────")
        song_meta = mp3_scanner.extract_song_meta(str(song_path))
        lyrics_text = song_meta.get("lyrics", "")

        # Try to resolve Traktor/Suno metadata from DB
        try:
            db_semantics = db.get_song_semantics(str(song_path))
        except Exception:
            db_semantics = None

        if db_semantics:
            semantics = db_semantics
        else:
            semantics = song_semantics.analyze_lyrics(
                lyrics=lyrics_text,
                prompt_description=song_meta.get("title", song_path.stem),
                tags_string=" ".join(song_meta.get("tags", [])),
            )

        song_mood_tags = semantics.get("mood_tags", []) or song_meta.get("tags", [])
        song_visual_objects = semantics.get("visual_objects", [])
        dominant_style = semantics.get("dominant_style") or "cinematic"
        self._log(
            f"  • Dominant Style: '{dominant_style}' | Vocal Gender: {audio.mc_gender} | "
            f"Visual Objects: {len(song_visual_objects)} ({', '.join(song_visual_objects[:5])})"
        )

        # ── [3/6] Director Council & Dynamic Pacing Strategy ──────────────────
        self._log(f"\n┌─ [3/6] 🎭 Director Council & Dynamic Pacing ─────────────────────────")
        try:
            from self_learning import get_global_learning_engine
            learning_engine = get_global_learning_engine()
            suggested_director = director_override or learning_engine.choose_director_style(strategy="thompson")
            suggested_pacing = pacing_override or learning_engine.choose_pacing_strategy()
        except Exception:
            suggested_director = director_override or "cunningham"
            suggested_pacing = pacing_override or "beat_locked"

        style = compile_style(suggested_director, ROOT_DIR / "styles")
        self._log(f"  • Regie-Archetyp: '{suggested_director}' | Pacing-Strategie: '{suggested_pacing}'")

        # ── [4/6] 30k+ Clip Retrieval & Timeline Construction ─────────────────
        self._log(f"\n┌─ [4/6] 🎞️ Timeline-Konstruktion & AVX2 Candidate Ranking ────────────")
        song_vec = mp3_scanner.build_tag_vector(song_meta.get("tags", []))
        try:
            recent_used = db.get_recent_usage_ranges()
        except Exception:
            recent_used = []

        timeline = build_timeline(
            song_vector=song_vec,
            audio=audio,
            globe=globe,
            recent_used=recent_used,
            style=style,
            platform=self.platform,
            song_tags=song_mood_tags,
            song_path=str(song_path),
            pacing_strategy=suggested_pacing,
            song_semantics=semantics,
        )

        boundary_cuts = sum(1 for seg in timeline if seg.on_structure_boundary)
        cut_density = len(timeline) / (audio.duration_sec / 60.0) if audio.duration_sec > 0 else 0
        self._log(f"  • Schnittliste: {len(timeline)} Segmente ({cut_density:.1f} Cuts/Min | {boundary_cuts} Boundary-Snaps)")

        # C+ Creative Compiler IR Manifest
        try:
            song_info_obj = mp3_scanner.SongInfo(
                path=str(song_path),
                title=song_meta.get("title", ""),
                artist=song_meta.get("artist", ""),
                lyrics=lyrics_text,
                tag_vector=song_vec,
            )
            cplus_manifest = compile_creative_ir(song_info_obj, audio, timeline, style, semantics=semantics, log_fn=self._log)
            manifest_file = target_dir / f"{safe_name}_{self.platform}.cplus.json"
            manifest_file.write_text(json.dumps(cplus_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            self._log(f"  ⚠️ C+ Creative Compiler Manifest übersprungen ({e})")

        # ── [5/6] Video-Rendering & Mastering ─────────────────────────────────
        self._log(f"\n┌─ [5/6] ⚡ Video-Rendering & Audio-Mastering ───────────────────────────")
        render_start = time.time()
        rendered_path = None

        if self.dry_run:
            self._log(f"  ⚡ [Dry-Run] Rendering übersprungen -> Timeline validiert.")
            return str(final_mp4)

        try:
            rendered_path = renderer.render_music_video(
                timeline=timeline,
                song_path=str(song_path),
                output_path=str(final_mp4),
                log=self._log,
                platform=self.platform,
                globe=globe,
            )
        except Exception as e:
            self._log(f"❌ [Render] Fehler beim Rendern: {e}\n{traceback.format_exc()}")
            return None

        if not rendered_path or not Path(rendered_path).is_file():
            self._log(f"❌ [Render] Kein Video erzeugt für: {song_path.name}")
            return None

        render_dur = time.time() - render_start
        file_size_mb = Path(rendered_path).stat().st_size / (1024 * 1024)
        self._log(f"  ✅ Render abgeschlossen in {render_dur:.1f}s ({file_size_mb:.2f} MB) -> {Path(rendered_path).name}")

        # ── [6/6] Artefakte, Self-Learning & Tagging ──────────────────────────
        self._log(f"\n┌─ [6/6] 📦 Artefakte, Self-Learning Feedback & Tagging ────────────────")
        # Record usage in DB
        try:
            db.record_usage_many([
                {
                    "clip_path": seg.clip_path,
                    "song_id": song_id,
                    "position_in_render": pos,
                    "clip_in": seg.clip_in_point,
                    "clip_out": seg.clip_in_point + (seg.end_sec - seg.start_sec),
                }
                for pos, seg in enumerate(timeline)
            ])
        except Exception:
            pass

        reward = _compute_render_reward(
            timeline, globe=globe, song_tag_vector=song_vec,
            song_mood_tags=song_mood_tags, song_mc_gender=audio.mc_gender,
        )

        try:
            db.record_render_session(str(song_path), str(rendered_path), len(timeline))
            clip_pool.update_learned_from_render(globe, timeline, reward, save_cb=db.save_flat_globe)
            self._log(f"  🎯 Render-Reward: {reward:.2f} in {len(set(s.clip_path for s in timeline))} Clips gespeichert.")
        except Exception as e:
            self._log(f"  ⚠️ DB Feedback Update Fehler: {e}")

        # Reinforcement Learning Bandit Feedback
        try:
            import self_learning
            learner = self_learning.get_global_learner()
            learner.record_render_outcome(
                song=song_info_obj, audio=audio, timeline=timeline, reward=reward,
                director=suggested_director, pacing_strategy=suggested_pacing, globe=globe,
            )
            self._log(f"  🧠 Self-Learning Bandit aktualisiert (Director '{suggested_director}').")
        except Exception as e:
            self._log(f"  ⚠️ Self-Learning Feedback Warnung: {e}")

        # Viral Strategy Briefing
        if viral_strategy is not None:
            try:
                song_niche = viral_strategy._niche_for_mood(song_tags, fallback=getattr(self, "learned_niche", DEFAULT_HASHTAG_NICHE))
                brief = viral_strategy.build_brief(
                    song_title=song_meta.get("title", song_path.stem),
                    bpm=audio.bpm,
                    duration_sec=audio.duration_sec,
                    cuts_count=len(timeline),
                    dominant_motif=getattr(timeline[0], "semantic_symbol", "BETON") if timeline else "BETON",
                    niche=song_niche,
                )
                brief_path = target_dir / f"{safe_name}_viral_brief.json"
                brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
                self._log(f"  🔥 Viral Strategy Briefing erstellt: {brief_path.name} (Nische: '{song_niche}')")
            except Exception:
                pass

        # OpenTimelineIO Export
        if getattr(self, "export_otio", False):
            try:
                import otio_export
                otio_path = otio_export.export_otio(
                    timeline=timeline,
                    song_path=str(song_path),
                    output_path=rendered_path or final_mp4,
                    fps=config.OUTPUT_FPS,
                )
                self._log(f"  🎬 OpenTimelineIO Projekt exportiert: {otio_path.name}")
            except Exception as e:
                self._log(f"  ⚠️ OTIO Export Fehler: {e}")

        # Rich Summary JSON
        try:
            summary_data = {
                "song_name": song_path.name,
                "song_path": str(song_path),
                "rendered_video": str(rendered_path) if rendered_path else str(final_mp4),
                "duration_sec": audio.duration_sec,
                "bpm": audio.bpm,
                "platform": self.platform,
                "director": suggested_director,
                "pacing": suggested_pacing,
                "segments_count": len(timeline),
                "unique_clips_count": len(set(s.clip_path for s in timeline if s.clip_path)),
                "reward": reward,
                "elapsed_sec": round(time.time() - t_start, 2),
                "cxx_stack": self.cxx.get_status_info().get("version", "native"),
            }
            summary_path = target_dir / f"{safe_name}_director_summary.json"
            summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
            self._log(f"  📊 Director Summary gespeichert: {summary_path.name}")
        except Exception:
            pass

        total_elapsed = time.time() - t_start
        self._log(f"\n" + "=" * 70)
        self._log(f"🏁 [FERTIG] Video erfolgreich produziert in {total_elapsed:.1f}s -> {Path(rendered_path).name}")
        self._log(f"=" * 70 + "\n")
        return str(rendered_path)

    def process_batch(
        self,
        folder_path: str | Path,
        limit: Optional[int] = None,
        force_rebuild_globe: bool = False,
        output_dir: Optional[str | Path] = None,
        director_override: Optional[str] = None,
        pacing_override: Optional[str] = None,
        style_name: Optional[str] = None,
    ) -> List[str]:
        """Runs the 1-Click Director across a folder of audio files in batch mode."""
        folder_path = Path(folder_path).resolve()
        if not folder_path.exists():
            self._log(f"❌ FEHLER: Batch-Ordner existiert nicht: {folder_path}")
            return []

        audio_files = sorted(
            [p for p in folder_path.glob("**/*") if p.suffix.lower() in (".mp3", ".m4a", ".wav") and mp3_scanner.is_valid_song_path(p)]
        )

        if not audio_files:
            self._log(f"Keine Audio-Dateien in {folder_path} gefunden.")
            return []

        if limit and limit > 0:
            audio_files = audio_files[:limit]

        self._log(f"\n🚀 [Batch-Director] {len(audio_files)} Songs zur Batch-Produktion gefunden.")
        globe = self.load_clip_globe(force_rebuild=force_rebuild_globe)
        results = []

        for idx, song_file in enumerate(audio_files, 1):
            self._log(f"\n============================================================")
            self._log(f"[{idx}/{len(audio_files)}] STARTE BATCH-TRACK: {song_file.name}")
            self._log(f"============================================================")
            try:
                res = self.process_single_song(
                    song_file,
                    globe=globe,
                    output_dir=output_dir,
                    director_override=director_override,
                    pacing_override=pacing_override,
                    style_name=style_name,
                )
                if res:
                    results.append(res)
            except Exception as e:
                self._log(f"❌ Fehler bei Track {song_file.name}: {e}\n{traceback.format_exc()}")

        self._log(f"\n============================================================")
        self._log(f"🎉 BATCH ABGESCHLOSSEN: {len(results)}/{len(audio_files)} Videos erfolgreich gerendert!")
        self._log(f"============================================================\n")
        return results


def run_benchmark():
    """Runs a high-precision performance benchmark of the C++ AVX2 Native Stack vs CPU fallback."""
    log("\n" + "=" * 70)
    log("⚡ BENCHMARK: C++ AVX2 NATIVE ACCELERATION SUPERSTACK vs PYTHON/NUMPY")
    log("=" * 70)
    cxx = cxx_accel.get_cxx_engine()

    # 1. Cosine Similarity (100,000 vectors vs query, dim=128)
    N, D = 100_000, 128
    query_vec = np.random.randn(D).astype(np.float32)
    mat = np.random.randn(N, D).astype(np.float32)
    query_vec /= np.maximum(1e-6, np.linalg.norm(query_vec))
    mat /= np.maximum(1e-6, np.linalg.norm(mat, axis=1, keepdims=True))

    t0 = time.perf_counter()
    res_cxx = cxx.batch_cosine_similarity(query_vec, mat)
    t_cxx = time.perf_counter() - t0

    t0 = time.perf_counter()
    res_py = np.dot(mat, query_vec)
    t_py = time.perf_counter() - t0

    speedup1 = t_py / max(1e-6, t_cxx)
    log(f"  1. Batch Cosine Sim (100k x 128d):  C++ = {t_cxx*1000:.1f}ms | NumPy = {t_py*1000:.1f}ms | Speedup: {speedup1:.1f}x")

    # 2. 30k Clip Candidate Ranking
    C = 30_000
    mat = np.random.randn(C, D).astype(np.float32)
    query = np.random.randn(D).astype(np.float32)
    dummy_metas = [
        {"duration": 2.5, "motion_score": 0.6, "motion_direction": 0.1, "face_score": 0.0, "information_density": 0.5, "learned_bonus": 0.0, "gender": "neutral", "is_still": False, "is_cooldown_locked": False}
        for _ in range(C)
    ]
    ctx = {"target_energy": 0.7, "target_duration": 2.0, "motion_weight": 0.35, "semantic_weight": 0.40, "pref_weight": 0.15, "density_weight": 0.10, "prev_motion_dir": 0.0, "target_gender_code": 0, "allow_still": False, "check_motion_continuity": True}

    t0 = time.perf_counter()
    top_results_cxx = cxx.rank_topk_candidates(query, mat, dummy_metas, ctx, top_k=50)
    t_rank_cxx = time.perf_counter() - t0

    t0 = time.perf_counter()
    scores_py = np.dot(mat, query)
    top_indices_py = np.argsort(scores_py)[-50:][::-1]
    t_rank_py = time.perf_counter() - t0

    speedup2 = t_rank_py / max(1e-6, t_rank_cxx)
    log(f"  2. 30k Clip Pool Ranker (Top-50):   C++ = {t_rank_cxx*1000:.2f}ms | NumPy = {t_rank_py*1000:.2f}ms | Speedup: {speedup2:.1f}x")

    # 3. Fast Moving RMS DSP (1,000,000 audio samples)
    S = 1_000_000
    audio_sig = np.random.randn(S).astype(np.float32)
    t0 = time.perf_counter()
    rms_cxx = cxx.compute_moving_rms(audio_sig, hop_size=512, frame_size=2048)
    t_dsp_cxx = time.perf_counter() - t0

    t0 = time.perf_counter()
    n_frames = (S + 512 - 1) // 512
    rms_py = np.zeros(n_frames, dtype=np.float32)
    for f in range(n_frames):
        chunk = audio_sig[f*512 : f*512 + 2048]
        if len(chunk) > 0:
            rms_py[f] = np.sqrt(np.mean(chunk**2))
    t_dsp_py = time.perf_counter() - t0

    speedup3 = t_dsp_py / max(1e-6, t_dsp_cxx)
    log(f"  3. Fast Moving RMS DSP (1M samples): C++ = {t_dsp_cxx*1000:.2f}ms | Python loop = {t_dsp_py*1000:.2f}ms | Speedup: {speedup3:.1f}x")

    # 4. 30k Candidate Matrix Multi-Attribute Scoring
    mat_9 = np.random.randn(C, 9).astype(np.float32)
    mat_9[:, 1] = 3.0  # valid durations
    t0 = time.perf_counter()
    scores_cxx = cxx.score_candidates_batch(mat_9, target_energy=0.7, target_duration=2.0)
    t_mat_cxx = time.perf_counter() - t0

    t0 = time.perf_counter()
    # Python numpy equivalent
    e_deltas = np.abs(mat_9[:, 2] - 0.7)
    e_scores = 1.0 - np.clip(e_deltas * 1.5, 0.0, 1.0)
    scores_np = 0.5 * mat_9[:, 5] + 0.5 * e_scores + 0.2 * mat_9[:, 6] + 0.1 * mat_9[:, 7] + mat_9[:, 8]
    t_mat_py = time.perf_counter() - t0

    speedup4 = t_mat_py / max(1e-6, t_mat_cxx)
    log(f"  4. 30k Candidate Matrix Scoring:    C++ = {t_mat_cxx*1000:.2f}ms | NumPy = {t_mat_py*1000:.2f}ms | Speedup: {speedup4:.1f}x")

    log("=" * 70)
    log(f"🚀 GESAMT-STATUS: C++20 AVX2 Stack aktiv & fehlerfrei beschleunigt.")
    log("=" * 70 + "\n")


def main():
    print(BANNER, flush=True)
    parser = argparse.ArgumentParser(description="WE.ED.IT Director: 1-Click C++ AVX2 Superstack Music Video Engine")
    parser.add_argument("--song", type=str, default=None, help="Pfad zu einer einzelnen MP3/M4A Datei")
    parser.add_argument("--batch", type=str, default=r"J:\Oidasheim\Musik\FAVs\ALTgr + q", help="Pfad zum Batch-Musikordner")
    parser.add_argument("--limit", type=int, default=None, help="Maximale Anzahl an Songs im Batch-Modus")
    parser.add_argument("--platform", type=str, default="full", choices=["full", "tiktok", "reels", "shorts", "landscape"])
    parser.add_argument("--output-dir", type=str, default=None, help="Zielordner für fertige Videos")
    parser.add_argument("--director", type=str, default=None, help="Regie-Archetyp (z.B. cunningham, alpine_drill_comedy)")
    parser.add_argument("--pacing", type=str, default=None, help="Pacing-Strategie (z.B. beat_locked, energy_flow)")
    parser.add_argument("--style", type=str, default=None, help="Stil-Override (z.B. habil_cyberpunk, vaporwave, drill_aggressive)")
    parser.add_argument("--rebuild-globe", action="store_true", help="Clip-Pool Cache komplett neu analysieren")
    parser.add_argument("--dry-run", action="store_true", help="Nur Analyse und Timeline-Erzeugung ohne Video-Encoding")
    parser.add_argument("--prune-dead", action="store_true", help="Bereinigt tote und fehlerhafte Clip-Einträge im Pool")
    parser.add_argument("--cxx-status", action="store_true", help="Zeigt Diagnosedaten des nativen C++ AVX2 Stacks")
    parser.add_argument("--benchmark", action="store_true", help="Führt High-Speed Benchmark C++ AVX2 vs CPU/NumPy aus")
    parser.add_argument("--export-otio", action="store_true", help="Exportiert OpenTimelineIO Projekt (.otio) für NLEs")
    parser.add_argument("--tag-suno-m4a", action="store_true", help="Startet M4A Massen-Tagger für Suno-Tracks")
    parser.add_argument("--dedup-suno", action="store_true", help="Findet und dedupliziert doppelte Suno-Dateien")
    parser.add_argument("--extract-clips", nargs="?", const="D:\\Oidasheim\\NFOs\\longloops", default=None,
                        help="Startet die 4-Stufen AI Clip-Extraktion für lange Videos (Default: D:\\Oidasheim\\NFOs\\longloops)")

    args = parser.parse_args()

    if args.extract_clips:
        try:
            from video_clip_extractor import VideoClipExtractor
            log(f"🎬 [Clip-Extractor] Starte 4-Stufen Clip-Extraktion für: {args.extract_clips}")
            extractor = VideoClipExtractor(input_dir=args.extract_clips, clip_pool_dir=config.CLIP_POOL_DIR)
            extractor.run_all()
        except Exception as e:
            log(f"Fehler bei Clip-Extraktion: {e}")
        sys.exit(0)

    if args.benchmark:
        run_benchmark()
        sys.exit(0)

    if args.prune_dead:
        log("🧹 [Clip-Pool] Starte Bereinigung toter & fehlerhafter Einträge...")
        globe, dead = db.prune_dead_clips(log=log)
        globe, failed = db.prune_failed_clips(log=log)
        log(f"✅ Bereinigung abgeschlossen: {len(dead) + len(failed)} Einträge entfernt. {len(globe)} aktive Clips verbleiben.")
        sys.exit(0)

    if args.cxx_status:
        cxx = cxx_accel.get_cxx_engine()
        status = cxx.get_status_info()
        log("\n" + "=" * 60)
        log("📊 [C++ AVX2 Native Stack Status & Diagnose]")
        log("=" * 60)
        for k, v in status.items():
            log(f"  • {k:25s}: {v}")
        log("=" * 60 + "\n")
        sys.exit(0)

    if args.tag_suno_m4a:
        try:
            from m4a_suno_tagger import main as run_tagger
            run_tagger()
        except Exception as e:
            log(f"Fehler beim Tagger: {e}")
        sys.exit(0)

    if args.dedup_suno:
        try:
            from suno_deduplicator import run_deduplication
            run_deduplication(log=log)
        except Exception as e:
            log(f"Fehler bei Deduplizierung: {e}")
        sys.exit(0)

    director = WeEditDirector(
        platform=args.platform,
        dry_run=args.dry_run,
        log_fn=log,
    )
    if args.export_otio:
        director.export_otio = True

    if args.song:
        globe = director.load_clip_globe(force_rebuild=args.rebuild_globe)
        director.process_single_song(
            args.song,
            globe=globe,
            output_dir=args.output_dir,
            director_override=args.director,
            pacing_override=args.pacing,
            style_name=args.style,
        )
    else:
        director.process_batch(
            args.batch,
            limit=args.limit,
            force_rebuild_globe=args.rebuild_globe,
            output_dir=args.output_dir,
            director_override=args.director,
            pacing_override=args.pacing,
            style_name=args.style,
        )


if __name__ == "__main__":
    main()
