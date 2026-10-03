#!/usr/bin/env python3
"""
main.py — ART DIRECTOR BEAT SYNC VIDEO EDITOR
1-Click: MP3 + Clips -> Epic Music Video
Offline-first, direct-subprocess-ffmpeg, keine Cloud-API, keine GPU-Pflicht.

=== DYNAMISCHE RHYTHMUS-SCHNITTE (DYNAMIC RHYTHM ON-POINT CUTS) ===
Neue Features für präzise, musiksynchrone Videoschnitte:

1. RHYTHM_PATTERN DETECTION:
   - intro: Anfang des Videos
   - expansion: Plötzlich längere Segmente
   - compression: Schnellere Schnitte (kurze Segmente)
   - energy_surge: Hohe Energie-Spitzen
   - buildup: Energie-Aufbau
   - stutter_repeat: Clip wiederholt sich (Repetition im Segment erkannt)
   - beat_drop: Exakte Beat-Drops (alle 4 Beats)
   - peak: Höhepunkte
   - dense_motion: Hohe Bewegungs-Dichte
   - steady: Gleichmäßige Schnitte

2. SYNC_TYPE (Synchronisations-Genauigkeit):
   - snap_drop: Präziser Schnitt auf Beat-Drops
   - energy_peak: Auf Energie-Höhepunkte
   - on_beat: Exakt auf den Beat
   - syncopated: Leicht gegen den Beat (Synkopation)
   - polyrhythm: Komplexe Rhythm-Patterns
   - breath: Atemraum in ruhigen Sektionen

3. CUT_STYLE (Schnitt-Art):
   - hard_cut: Direkter Schnitt (Intro/Outro)
   - jump_cut: Große Energie-Änderungen
   - push: Energie-Aufbau zwischen Clips
   - break: Energie-Abfall
   - whip: Schnelle Übergänge bei Bewegung
   - dissolve: Sanfter Übergang
   - fade_out: Ausblenden

Nutzung:
    python main.py                              # verarbeitet ALLE mp3s in FAVs/**
    python main.py --song "J:/path/to/song.mp3" # nur einen Song
    python main.py --limit 5                    # nur die ersten 5 (zum Testen)
    python main.py --rebuild-globe              # ClipPool-Cache komplett neu analysieren
"""
import argparse
import csv
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

# Windows-Konsolen laufen oft noch auf cp1252 statt UTF-8 -> jeder Emoji/Box-
# Drawing-Character (Banner, ✅/❌ etc.) crasht sonst mit UnicodeEncodeError.
# Erzwingt UTF-8 auf stdout/stderr, unabhängig von Systemcodepage/Terminal.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import swag_banners
import audio_analysis
import clip_pool
import db
import mp3_scanner
import song_semantics
import user_prefs
import config
from config import (DEFAULT_HASHTAG_NICHE, ENGINE_VERSION, LABEL_NAME, LOG_DIR,
                    OUTPUT_SUBDIR_BY_PLATFORM, RENDERER_BACKEND, ROOT_DIR,
                    TIKTOK_CLIP_SUBDIRS)

from creative_genome import FilmDNA, build_intent, compile_style, genome_manifest, update_film_dna
import creative_compiler
from creative_compiler import compile_creative_ir
from film_genome import compile_film_genome
from semantic_matching import calculate_semantic_match, semantic_match_reason
from timeline_builder import build_timeline
from wong_integration import init_wong_state, wong_resolve_segment
import cxx_accel

# viral-strategy.py hat einen Bindestrich im Dateinamen -> kein normales
# "import viral-strategy" möglich, daher per importlib aus dem Skriptordner
# geladen (Modulname ohne Bindestrich, damit er als Python-Identifier gültig
# bleibt). Siehe viral_strategy.build_brief() in process_song().
import importlib.util as _importlib_util
_viral_strategy_spec = _importlib_util.spec_from_file_location(
    "viral_strategy", Path(__file__).resolve().parent / "viral-strategy.py")
viral_strategy = _importlib_util.module_from_spec(_viral_strategy_spec)
_viral_strategy_spec.loader.exec_module(viral_strategy)

# WONG-Integration (optionale GenomeResolver/RLBandit-Anbindung, --wong-
# resolver) wurde nach wong_integration.py ausgelagert -- main.py ruft hier
# nur noch init_wong_state()/wong_resolve_segment() auf (siehe Import oben).

START_BANNER = r'''   
    ██████╗ ███████╗ █████╗ ████████╗    ███████╗██╗   ██╗███╗   ██╗ ██████╗
    ██╔══██╗██╔════╝██╔══██╗╚══██╔══╝    ██╔════╝╚██╗ ██╔╝████╗  ██║██╔════╝
    ██████╔╝█████╗  ███████║   ██║       ███████╗ ╚████╔╝ ██╔██╗ ██║██║
    ██╔══██╗██╔══╝  ██╔══██║   ██║       ╚════██║  ╚██╔╝  ██║╚██╗██║██║
    ██████╔╝███████╗██║  ██║   ██║       ███████║   ██║   ██║ ╚████║╚██████╗
    ╚══════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝       ╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝

🎬 Scanne Clip-Pool in
1-Click: MP3 + Clips → Epic Music Videos
Automatisches Matching von Songs und Clips basierend auf semantischen Eigenschaften.
Musikvideo-Pipeline 1-Click-1-File

██╗    ██╗███████╗   ███████╗██████╗   ██╗████████╗
██║    ██║██╔════╝   ██╔════╝██╔══██╗  ██║╚══██╔══╝
██║ █╗ ██║█████╗     █████╗  ██║  ██║  ██║   ██║
██║███╗██║██╔══╝     ██╔══╝  ██║  ██║  ██║   ██║
╚███╔███╝███████╗    ███████╗██████╔╝  ██║   ██║
 ╚══╝╚══╝ ╚══════╝   ╚══════╝╚═════╝   ╚═╝   ╚═╝'''


# === TUNING-KONSTANTEN =====================================================
RHYTHM_EXPANSION_RATIO = 1.8
RHYTHM_COMPRESSION_RATIO = 0.6
RHYTHM_ENERGY_SURGE = 0.8
RHYTHM_BUILDUP_ENERGY = 0.3
RHYTHM_BEAT_DROP_STRIDE = 4
RHYTHM_DENSE_MOTION_DENSITY = 0.7

SYNC_SNAP_DROP_ENERGY = 0.85
SYNC_ON_BEAT_ENERGY = 0.75
SYNC_SYNCOPATED_ENERGY = 0.5

CUT_INTRO_SEGMENTS = 2
CUT_OUTRO_SEGMENTS = 2
CUT_JUMP_ENERGY_DELTA = 0.4
CUT_PUSH_ENERGY_DELTA = 0.2
CUT_WHIP_DENSITY = 0.6

REWARD_HECTIC_CUTS_PER_MIN = 120.0
REWARD_HECTIC_MAX_ENERGY = 0.4
REWARD_SEMANTIC_FALLBACK = 0.7
REWARD_SYNC_WEIGHT = 0.35
REWARD_DIVERSITY_WEIGHT = 0.35
REWARD_SEMANTIC_WEIGHT = 0.3

MAX_OUTPUT_VERSION_ATTEMPTS = 9999

# Ab wie vielen bereits gültig analysierten ("frischen") Clips im Cache der
# volle ClipPool-DB-Scan (clip_pool.build_or_update_globe) übersprungen wird.
# Bei sehr großen Pools (siehe Docstring in clip_pool.py, "32k+ Clips") kostet
# allein das Scannen+Fingerprint-Vergleichen jedes einzelnen Files spürbar
# Zeit, selbst wenn am Ende so gut wie nichts neu zu analysieren ist. Sobald
# der Cache schon ausreichend gefüllt ist, ist ein neuer Scan meist unnötig --
# --rebuild-globe (setzt globe explizit auf {} zurück) erzwingt trotzdem
# immer einen vollen Scan, unabhängig von diesem Threshold.
CLIP_POOL_SKIP_SCAN_FRESH_THRESHOLD = 1000
# === /TUNING-KONSTANTEN =====================================================


def log(msg: str):
    print(msg, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "run.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass

def _count_fresh_cached_clips(globe: dict) -> int:
    """Zählt Clips im Globe-Cache, die bereits erfolgreich mit der aktuellen
    clip_pool.ANALYSIS_VERSION analysiert wurden (nicht failed, nicht
    veraltet). Basis für CLIP_POOL_SKIP_SCAN_FRESH_THRESHOLD -- ein Clip mit
    alter analysis_version oder failed=True zählt NICHT als "frisch", weil er
    beim nächsten echten Scan sowieso neu analysiert werden müsste."""
    return cxx_accel.get_cxx_engine().count_fresh_cached_clips(globe, clip_pool.ANALYSIS_VERSION)

def _safe_song_stem(song_path: str) -> str:
    """Extrahiert aus dem Songpfad einen sauberen, dateisystemsicheren Stem für Benennung & Ordner (C++ optimiert)."""
    return cxx_accel.get_cxx_engine().clean_stem(Path(song_path).stem)

def _resolve_song_output_dir(base_output_dir: Path | None, song_path: str, platform: str) -> Path:
    """Ermittelt den dedizierten Song-Ordner: ./output/<SongName>/."""
    safe_name = _safe_song_stem(song_path)
    if base_output_dir is not None:
        if base_output_dir.name.lower() == safe_name.lower():
            return base_output_dir
        return base_output_dir / safe_name
    # Standard: ./output/<SongName>
    default_root = Path(__file__).resolve().parent / "output"
    return default_root / safe_name

def _existing_output_path(output_dir: Path, song_path: str, platform: str) -> Path | None:
    """Prüft, ob für diesen Song/diese Plattform in output_dir oder seinem
    Song-Ordner bereits IRGENDEINE gerenderte Version existiert."""
    safe_name = _safe_song_stem(song_path)
    dirs_to_check = [output_dir, output_dir / safe_name]
    
    # Auch alte Pfade neben der MP3 prüfen falls vorhanden
    base_dir = _get_song_base_dir(song_path)
    old_platform_dir = OUTPUT_SUBDIR_BY_PLATFORM.get(platform, "16zu9")
    dirs_to_check.extend([base_dir / old_platform_dir / safe_name, base_dir / old_platform_dir])

    for d in dirs_to_check:
        if d.exists():
            for f in sorted(d.glob("*.mp4")):
                fname = f.name.lower()
                if safe_name.lower() in fname:
                    if platform == "tiktok" and ("tiktok" in fname or "9zu16" in fname):
                        return f
                    elif platform == "full" and ("tiktok" not in fname and "9zu16" not in fname):
                        return f
    return None

def _get_song_base_dir(song_path: str) -> Path:
    """Ermittelt den Basis-Ordner des Songs."""
    parent = Path(song_path).resolve().parent
    while parent.name.lower() in ("stems", "16zu9", "9zu16", "meta") or parent.name.lower().startswith("_demucs_tmp"):
        parent = parent.parent
    return parent

def _all_outputs_exist(song: "mp3_scanner.SongInfo", output_dir: Path | None, platforms: list) -> bool:
    """Prüft, ob für JEDE angeforderte Plattform bereits ein gerendertes Video existiert."""
    for platform in platforms:
        resolved_output_dir = _resolve_song_output_dir(output_dir, song.path, platform)
        if _existing_output_path(resolved_output_dir, song.path, platform) is None:
            return False
    return True

def _versioned_output_path(output_dir: Path, song_path: str, platform: str) -> Path:
    """Generiert einen sauberen, aussagekräftigen Video-Dateinamen."""
    safe_name = _safe_song_stem(song_path)
    platform_tag = "9zu16_tiktok" if platform == "tiktok" else "16zu9"
    for version in range(1, MAX_OUTPUT_VERSION_ATTEMPTS + 1):
        candidate = output_dir / f"{safe_name}_{platform_tag}_eng{ENGINE_VERSION}_v{version:02d}.mp4"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Konnte keinen freien Output-Dateinamen finden für '{safe_name}' in {output_dir}.")

def _detect_rhythm_pattern(segment, idx: int, timeline: list) -> str:
    if idx == 0:
        return "intro"
    if getattr(segment, "on_structure_boundary", False):
        return "beat_drop"

    prev_segment = timeline[idx - 1]
    curr_duration = segment.end_sec - segment.start_sec
    prev_duration = prev_segment.end_sec - prev_segment.start_sec
    duration_ratio = curr_duration / (prev_duration + 0.001)

    if duration_ratio > RHYTHM_EXPANSION_RATIO:
        return "expansion"
    elif duration_ratio < RHYTHM_COMPRESSION_RATIO:
        return "compression"
    elif segment.target_energy > RHYTHM_ENERGY_SURGE:
        return "energy_surge"
    elif segment.target_energy < RHYTHM_BUILDUP_ENERGY:
        return "buildup"
    elif getattr(segment, "repetition", False):
        return "stutter_repeat"
    elif getattr(segment, "structure_label", "") in ("hook", "drop") and segment.target_energy > 0.7:
        return "beat_drop"
    elif segment.section_label == "high":
        return "peak"
    elif segment.information_density > RHYTHM_DENSE_MOTION_DENSITY:
        return "dense_motion"
    else:
        return "steady"

def _calculate_sync_type(segment, idx: int, timeline: list) -> str:
    energy = segment.target_energy
    if getattr(segment, "on_structure_boundary", False):
        return "snap_drop"
    if segment.section_label == "high":
        return "snap_drop" if energy > SYNC_SNAP_DROP_ENERGY else "energy_peak"
    elif segment.section_label == "low":
        return "breath"
    elif energy > SYNC_ON_BEAT_ENERGY:
        return "on_beat"
    elif energy > SYNC_SYNCOPATED_ENERGY:
        return "syncopated"
    else:
        return "polyrhythm"

def _calculate_cut_style(segment, idx: int, timeline: list) -> str:
    if idx < CUT_INTRO_SEGMENTS:
        return "hard_cut"
    if idx >= len(timeline) - CUT_OUTRO_SEGMENTS:
        return "fade_out"
    if getattr(segment, "on_structure_boundary", False):
        return "jump_cut"
    if getattr(segment, "repetition", False):
        return "jump_cut"
    next_segment = timeline[idx + 1] if idx + 1 < len(timeline) else None
    if not next_segment:
        return "hard_cut"
    energy_delta = next_segment.target_energy - segment.target_energy
    if energy_delta < -CUT_PUSH_ENERGY_DELTA:
        return "break"
    elif energy_delta > CUT_JUMP_ENERGY_DELTA:
        return "jump_cut"
    elif energy_delta > CUT_PUSH_ENERGY_DELTA:
        return "push"
    elif next_segment.information_density > CUT_WHIP_DENSITY or abs(getattr(segment, "motion_direction", 0.0)) >= 0.4:
        return "whip"
    elif segment.section_label == "low" and getattr(segment, "sync_type", "") == "breath":
        return "dissolve"
    else:
        return "hard_cut"

# Semantic-Matching (Song<->Clip Tag-Vektor/Gender/Mood-Scoring +
# menschenlesbare Begründung) wurde nach semantic_matching.py ausgelagert --
# main.py ruft hier nur noch calculate_semantic_match()/semantic_match_reason()
# auf (siehe Import oben), keine der Detail-Funktionen (extract_vector,
# cosine_similarity, calculate_vector_match, gender_alignment_score,
# mood_tag_overlap_score) wird in main.py selbst gebraucht.

def _build_timeline_narrative(song: mp3_scanner.SongInfo, sequence: list) -> str:
    """Baut eine kompakte, lesbare Erzählung der KOMPLETTEN Clip-Timeline
    (Section-für-Section statt nur Segment-für-Segment-Zahlen). Gruppiert
    aufeinanderfolgende Segmente mit gleichem Song-Section-Label (low/mid/high)
    zu je einem Absatz und fasst pro Absatz das dominante Clip-Thema sowie den
    häufigsten Match-Grund (siehe semantic_matching.semantic_match_reason) zusammen. Landet als
    "timeline_narrative" im .edl.json und wird zusätzlich ins Log geschrieben
    (siehe process_song) -- macht auf einen Blick nachvollziehbar, WARUM WANN
    WELCHER Clip-Typ im fertigen Video läuft, statt nur eine flache Segment-
    liste ohne erkennbare Dramaturgie zu haben."""
    if not sequence:
        return "Leere Timeline."

    def _most_common(values: list, fallback: str) -> str:
        cleaned = [v for v in values if v]
        return max(set(cleaned), key=cleaned.count) if cleaned else fallback

    lines = [f"Timeline fuer '{song.title or Path(song.path).stem}' "
             f"({len(sequence)} Segmente, {sequence[-1]['end']:.1f}s gesamt):"]
    groups: list[list[dict]] = []
    for seg in sequence:
        if groups and seg["section"] == groups[-1][-1]["section"]:
            groups[-1].append(seg)
        else:
            groups.append([seg])

    for group in groups:
        section = group[0]["section"]
        start, end = group[0]["start"], group[-1]["end"]
        top_theme = _most_common([g.get("theme") for g in group], "kein dominantes Thema")
        top_reason = _most_common([g.get("match_reason") for g in group], "-")
        top_pattern = _most_common([g.get("rhythm_pattern") for g in group], "-")
        clip_names = [Path(g["clip"]).stem for g in group if g.get("clip")]
        preview = ", ".join(clip_names[:3]) + (", ..." if len(clip_names) > 3 else "")
        lines.append(
            f"  [{start:6.1f}s-{end:6.1f}s] Section={section} | {len(group)} Clip(s) | "
            f"Thema: {top_theme} | Rhythmus: {top_pattern} | Grund: {top_reason} | "
            f"Clips: {preview}"
        )
    return "\n".join(lines)

def _build_render_script(song: mp3_scanner.SongInfo, timeline: list,
                         style: Any, output_path: Path,
                         globe: dict | None = None,
                         song_mood_tags: list | None = None,
                         song_mc_gender: str | None = None,
                         song_style_weights: dict | None = None,
                         wong_state: dict | None = None,
                         song_visual_objects: list | None = None,
                         song_cluster_mask: int = 0) -> dict:
    if not timeline:
        raise ValueError("Leere Timeline: kein Render-Skript möglich.")
    
    # C++ Native Batch Klassifikation (Rhythm-Pattern, Sync-Type, Cut-Style in C++ SIMD)
    cxx_engine = cxx_accel.get_cxx_engine()
    classifications = cxx_engine.classify_timeline_batch(timeline)

    sequence = []
    vector_scores = []
    wong_agreements: list[bool] = []
    wong_rewards: list[float] = []
    for idx, (segment, (rhythm_pattern, sync_type, cut_style)) in enumerate(zip(timeline, classifications)):
        duration = round(segment.end_sec - segment.start_sec, 3)
        if duration <= 0 or not segment.clip_path:
            raise ValueError("Ungültiges Timeline-Segment im Render-Skript.")
        
        # BUGFIX (Deep-Wiring-Audit): vorher landeten cut_style/sync_type NUR
        # im sequence-Dict weiter unten (also nur im .edl.json-Manifest) --
        # das TimelineSegment-Objekt selbst (dieselbe Instanz, die gleich an
        # renderer.render_music_video() übergeben wird) blieb unverändert.
        # renderer.py konnte die Werte dadurch gar nicht lesen, obwohl
        # config.py's CUT_STYLE_*/SYNC_TYPE_*-Konstanten genau dafür gedacht
        # sind (siehe TimelineSegment.cut_style/.sync_type-Docstring). Jetzt
        # wird die bereits berechnete Klassifikation zusätzlich auf das
        # Segment selbst geschrieben, BEVOR gerendert wird.
        segment.cut_style = cut_style
        segment.sync_type = sync_type
        clip_meta = globe.get(segment.clip_path) if globe else None
        vector_similarity = calculate_semantic_match(
            clip_meta, song.tag_vector, song_mood_tags=song_mood_tags, song_mc_gender=song_mc_gender,
            song_style_weights=song_style_weights,
            song_visual_objects=song_visual_objects,
            song_cluster_mask=song_cluster_mask,
        )
        if vector_similarity is not None:
            vector_scores.append(vector_similarity)
        match_reason = semantic_match_reason(
            clip_meta, song.tag_vector, song_mood_tags=song_mood_tags, song_mc_gender=song_mc_gender,
            song_style_weights=song_style_weights,
            song_visual_objects=song_visual_objects,
            song_cluster_mask=song_cluster_mask,
        )
        wong_info = wong_resolve_segment(segment, idx, sync_type, wong_state)
        if wong_info and wong_info.get("wong_reward_prediction") is not None:
            wong_rewards.append(wong_info["wong_reward_prediction"])
        if wong_info and wong_info.get("wong_agrees_with_oefoef") is not None:
            wong_agreements.append(wong_info["wong_agrees_with_oefoef"])
        sequence.append({
            "start": round(segment.start_sec, 3),
            "end": round(segment.end_sec, 3),
            "duration": duration,
            "clip": segment.clip_path,
            "clip_in": round(segment.clip_in_point, 3),
            "effect": segment.transition or "cut",
            "rhythm_sync": sync_type,
            "rhythm_pattern": rhythm_pattern,
            "cut_style": cut_style,
            "section": segment.section_label,
            "structure": segment.structure_label,
            "on_structure_boundary": segment.on_structure_boundary,
            "theme": segment.theme,
            "target_energy": round(segment.target_energy, 4),
            "information_density": round(segment.information_density, 4),
            "speed_factor": round(getattr(segment, "speed_factor", 1.0), 3),
            "repetition": bool(getattr(segment, "repetition", False)),
            "fx": list(getattr(segment, "fx", ()) or ()),
            "mc_gender": getattr(segment, "mc_gender", "unknown"),
            "vector_similarity": vector_similarity,
            "match_reason": match_reason,
            "wong_pick": wong_info.get("wong_pick") if wong_info else None,
            "wong_reward_prediction": wong_info.get("wong_reward_prediction") if wong_info else None,
            "wong_reason": wong_info.get("wong_reason") if wong_info else None,
            "wong_agrees_with_oefoef": wong_info.get("wong_agrees_with_oefoef") if wong_info else None,
        })
    return {
        "version": "synapse-edl-v1",
        "project": song.title or Path(song.path).stem,
        "artist": song.artist,
        "source_audio": song.path,
        "output": str(output_path),
        "style": style.name,
        "avg_vector_similarity": round(sum(vector_scores) / len(vector_scores), 4) if vector_scores else None,
        "wong_agreement_rate": round(sum(wong_agreements) / len(wong_agreements), 4) if wong_agreements else None,
        "wong_avg_reward_prediction": round(sum(wong_rewards) / len(wong_rewards), 4) if wong_rewards else None,
        "sequence": sequence,
        "timeline_narrative": _build_timeline_narrative(song, sequence),
    }

# Obergrenze für das MP4-"comment"-Tag: die vollständige timeline_narrative
# kann bei sehr langen Songs/vielen Segmenten mehrere zehntausend Zeichen
# lang werden -- manche Player/Tag-Reader (v.a. ältere QuickTime-/Windows-
# Explorer-Property-Panels) kürzen oder verschlucken sehr lange Comment-Tags
# stillschweigend. Lieber hart selbst kürzen + auf das ohnehin geschriebene
# .edl.json verweisen, als riskieren, dass der Tag im Player halb kaputt
# ankommt.
MP4_COMMENT_MAX_CHARS = 6000
# Kapitel-Titel bewusst kurz halten: manche MP4-Kapitel-UIs (Autoradios,
# manche Handy-Player) schneiden sehr lange Kapitelnamen ab oder brechen das
# Layout -- ein knapper, aber informativer Titel pro Clip ist robuster als
# ein möglichst vollständiger.
CHAPTER_MATCH_REASON_MAX_CHARS = 70

def _build_storyline(song: mp3_scanner.SongInfo, audio: Any, semantics: dict | None) -> str:
    """Baut aus dem bereits vorhandenen Song-Kontext (Struktur-Erkennung aus
    audio_analysis, Mood-Tags/Slang aus song_semantics) eine kurze, lesbare
    Video-Storyline -- anders als _build_timeline_narrative (die die fertige
    CLIP-Auswahl Section-für-Section dokumentiert) beschreibt diese Funktion
    einen dramaturgischen BOGEN (Intro -> Aufbau -> Höhepunkt -> Ende) rein
    aus dem, was der Song selbst hergibt, BEVOR irgendein Clip gematcht wurde.
    Gedacht als kreativer Kontext für --renderer unreal (siehe
    unreal_renderer.render_music_video/_write_manifest, landet dort im
    Manifest als "storyline" fürs spätere Set-Dressing im Sequencer), rein
    additiv -- beeinflusst NICHT die eigentliche Clip-Auswahl/Timeline."""
    title = song.title or Path(song.path).stem
    artist = song.artist or "Unknown Artist"
    semantics = semantics or {}
    mood_tags = list(semantics.get("mood_tags") or [])
    slang_hits = list((semantics.get("slang") or {}).keys())

    if getattr(audio, "structure", None):
        arc = " -> ".join(label for _, _, label in audio.structure)
    else:
        arc = "intro -> verse -> hook -> outro"

    mood_str = ", ".join(mood_tags[:4]) if mood_tags else "kein dominanter Mood-Tag erkannt"
    slang_str = ", ".join(slang_hits[:4]) if slang_hits else "-"

    return (
        f"'{title}' von {artist}: dramaturgischer Bogen {arc} "
        f"(BPM={audio.bpm:.0f}, {audio.duration_sec:.0f}s). "
        f"Stimmung/Vibe: {mood_str}. Slang/Szene-Bezug: {slang_str}. "
        f"MC-Stimmlage: {getattr(audio, 'mc_gender', 'unknown')}. "
        "Bild-Idee: das Video öffnet auf einem stehenden Establishing-Shot "
        "(siehe Unreal-Start-Image), bevor die eigentliche Clip-Dramaturgie "
        "im Takt der erkannten Struktur einsetzt."
    )


def _build_video_metadata(song: mp3_scanner.SongInfo, render_script: dict, platform: str) -> dict:
    """Baut aus dem bereits vorhandenen render_script (siehe
    _build_render_script) die MP4-Metadata/Kapitelmarken für den Renderer
    (siehe renderer._write_ffmetadata_file): globale Tags (Titel, Artist,
    Kommentar mit der kompletten Timeline-Dramaturgie) + EIN Kapitel pro
    Clip-Segment. Jeder Kapiteltitel beantwortet direkt im MP4-Container
    selbst -- ohne das separate .edl.json/.genome.json zu brauchen --
    WANN (Kapitel-Start/Ende = Segment-Zeit im fertigen Video), WAS (Clip-
    Dateiname, Song-Section), WIE (Rhythmus-Pattern/Cut-Style/Energie) und
    WARUM (semantischer match_reason, siehe semantic_matching.semantic_match_reason) dieser
    Clip an dieser Stelle verwendet wurde.

    Rein additiv/informativ -- beeinflusst weder Clip-Auswahl noch Render;
    bei leerer/fehlender sequence wird ein leeres {"tags": {}, "chapters": []}
    zurückgegeben, renderer.py embedded dann einfach keine Metadata (siehe
    dortiger `if metadata and (...)`-Check)."""
    sequence = render_script.get("sequence") or []
    if not sequence:
        return {"tags": {}, "chapters": []}

    narrative = render_script.get("timeline_narrative") or ""
    comment = narrative
    if len(comment) > MP4_COMMENT_MAX_CHARS:
        comment = (comment[:MP4_COMMENT_MAX_CHARS]
                   + f"\n... (gekürzt -- vollständige Fassung in {Path(render_script['output']).with_suffix('.edl.json').name})")

    tags = {
        "title": render_script.get("project") or Path(song.path).stem,
        "artist": render_script.get("artist") or "Unknown Artist",
        "genre": render_script.get("style") or "",
        "date": time.strftime("%Y-%m-%d"),
        "comment": comment,
        "description": (f"oefoef Beat-Sync-Video | {len(sequence)} Clip-Segmente | "
                         f"engine {ENGINE_VERSION} | platform={platform} | "
                         f"Herkunft/Match-Grund je Clip siehe Kapitelmarken."),
        "encoding_tool": f"oefoef engine {ENGINE_VERSION}",
    }

    chapters = []
    for idx, seg in enumerate(sequence, start=1):
        start_sec, end_sec = seg.get("start"), seg.get("end")
        if start_sec is None or end_sec is None or end_sec <= start_sec:
            continue
        clip_name = Path(seg["clip"]).stem if seg.get("clip") else "?"
        reason = (seg.get("match_reason") or "-")
        if len(reason) > CHAPTER_MATCH_REASON_MAX_CHARS:
            reason = reason[:CHAPTER_MATCH_REASON_MAX_CHARS - 1] + "…"
        title = (f"{idx:03d} {clip_name} | Section={seg.get('section', '-')} | "
                 f"{seg.get('rhythm_pattern', '-')}/{seg.get('cut_style', '-')} | "
                 f"E={seg.get('target_energy', 0.0):.2f} | Grund: {reason}")
        chapters.append({"start_sec": start_sec, "end_sec": end_sec, "title": title})

    return {"tags": tags, "chapters": chapters}

def _compute_render_reward(timeline: list, globe: dict | None = None,
                           song_tag_vector=None, song_mood_tags: list | None = None,
                           song_mc_gender: str | None = None,
                           song_style_weights: dict | None = None) -> float:
    if not timeline: return 0.0
    vector_scores = []
    if globe and song_tag_vector:
        for seg in timeline:
            score = calculate_semantic_match(globe.get(seg.clip_path), song_tag_vector, song_mood_tags=song_mood_tags, song_mc_gender=song_mc_gender, song_style_weights=song_style_weights)
            if score is not None: vector_scores.append(score)
    semantic_score = sum(vector_scores) / len(vector_scores) if vector_scores else REWARD_SEMANTIC_FALLBACK
    
    # C++ Native Multi-Reward Engine
    cxx_engine = cxx_accel.get_cxx_engine()
    res = cxx_engine.compute_timeline_reward(timeline, semantic_score=semantic_score)
    return res.get("reward", 0.0)

def _finalize_song_artifacts(song, audio, timeline, style, output_path, full_globe, semantics, resolved_label, resolved_default_niche, platform, log) -> dict:
    """Generates all post-render artifacts cleanly structured inside ./output/<Song>/meta/."""
    dna_dict = {}
    bundle = {}
    safe_name = _safe_song_stem(song.path)
    meta_dir = output_path.parent / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    try:
        dna = FilmDNA()
        mood_tags = list(semantics.get("mood_tags") or []) if semantics else []
        for segment in timeline:
            clip_meta = full_globe.get(segment.clip_path)
            if clip_meta is None: continue
            intent = build_intent(segment.section_label, segment.target_energy, style, mood_tags)
            update_film_dna(dna, intent, clip_meta)
        
        film_genome = compile_film_genome(song.tag_vector, audio.sections, timeline, style)
        manifest_path = meta_dir / f"{safe_name}_{platform}.genome.json"
        manifest = genome_manifest(song, style, dna)
        manifest["film_genome"] = film_genome.to_dict()
        manifest["song_semantics"] = semantics
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        dna_dict = dna.to_dict()
        log(f"  🧬 Film-DNA & Genome -> meta/{manifest_path.name}")

        # Viral-Strategy-Brief
        try:
            semantics_for_brief = semantics or {}
            strategy = viral_strategy.build_brief(
                artist=song.artist or "Unknown Artist",
                track=song.title or Path(song.path).stem,
                release=time.strftime("%Y-%m-%d"),
                label=resolved_label,
                mood_tags=semantics_for_brief.get("mood_tags"),
                slang=list((semantics_for_brief.get("slang") or {}).keys()),
                niche=resolved_default_niche,
            )
            strategy_path = meta_dir / f"{safe_name}_{platform}.strategy.json"
            strategy_path.write_text(json.dumps(strategy, indent=2, ensure_ascii=False), encoding="utf-8")
            log(f"  📈 Viral-Strategy-Brief -> meta/{strategy_path.name} (Hook: [{strategy['hook_framework']}])")
        except Exception as e:
            log(f"  ⚠️ Viral-Strategy-Brief übersprungen ({e})")

        # Upload Metadata
        try:
            metadata_platform = "youtube" if platform == "full" else "tiktok"
            semantics_for_meta = semantics or {}
            metadata = viral_strategy.build_platform_metadata(
                artist=song.artist or "Unknown Artist",
                track=song.title or Path(song.path).stem,
                release=time.strftime("%Y-%m-%d"),
                label=resolved_label,
                platform=metadata_platform,
                mood_tags=semantics_for_meta.get("mood_tags"),
                slang=list((semantics_for_meta.get("slang") or {}).keys()),
                niche=resolved_default_niche,
            )
            metadata_path = meta_dir / f"{safe_name}_{platform}.metadata.json"
            metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
            csv_path = meta_dir / f"metadata_{metadata_platform}.csv"
            write_header = not csv_path.exists()
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["filename", "title", "description", "tags", "hashtags", "best_post_time"])
                if write_header: writer.writeheader()
                writer.writerow({
                    "filename": output_path.name,
                    "title": metadata["title"],
                    "description": metadata["description"].replace("\n", " | "),
                    "tags": ", ".join(metadata["tags"]),
                    "hashtags": metadata["hashtags"],
                    "best_post_time": metadata["best_post_time"] or "",
                })
            log(f"  📝 Upload-Metadaten -> meta/{metadata_path.name} (+ {csv_path.name})")
        except Exception as e:
            log(f"  ⚠️ Upload-Metadaten übersprungen ({e})")

        # Director Compiler Stack (.director.json)
        try:
            import director_compiler
            director_data = director_compiler.compile_director_stack(
                audio, timeline, song.path, project_name=song.title or Path(song.path).stem
            )
            director_path = meta_dir / f"{safe_name}_{platform}.director.json"
            director_path.write_text(json.dumps(director_data, indent=2, ensure_ascii=False), encoding="utf-8")
            log(f"  🎬 Director-Compiler-Stack -> meta/{director_path.name}")
        except Exception as e:
            log(f"  ⚠️ Director-Compiler-Stack übersprungen ({e})")

        # Creative Compiler C+ Stack (.cplus.json)
        try:
            cplus_path = meta_dir / f"{safe_name}_{platform}.cplus.json"
            if not cplus_path.exists():
                cplus_data = compile_creative_ir(song, audio, timeline, style, semantics=semantics)
                cplus_path.write_text(json.dumps(cplus_data, indent=2, ensure_ascii=False), encoding="utf-8")
            log(f"  🧠 C+ Creative Compiler -> meta/{cplus_path.name}")
        except Exception as e:
            log(f"  ⚠️ C+ Creative Compiler Export übersprungen ({e})")

        # OpenTimelineIO Export (.otio)
        try:
            import otio_export
            otio_target = meta_dir / f"{safe_name}_{platform}.otio"
            otio_path = otio_export.export_otio(timeline, song.path, otio_target)
            log(f"  🎞️ OpenTimelineIO -> meta/{Path(otio_path).name}")
        except Exception as e:
            log(f"  ⚠️ OTIO-Export übersprungen ({e})")

        # Setcard HTML, Meta-Asset JSON & Mastered MP3
        try:
            import gdrive_discord_publisher
            bundle = gdrive_discord_publisher.build_release_bundle(
                output_path, audio_path=Path(song.path), meta_dir=meta_dir
            )
            setcard_fn = Path(bundle.get('setcard_file', '')).name
            meta_fn = Path(bundle.get('meta_file', '')).name
            audio_fn = Path(bundle.get('audio_path', '')).name if bundle.get('audio_path') else '–'
            log(f"  📄 Setcard HTML -> meta/{setcard_fn}")
            log(f"  🏷️ Meta Asset JSON -> meta/{meta_fn}")
            log(f"  🔊 Mastered MP3 Audio -> {audio_fn}")
        except Exception as e:
            log(f"  ⚠️ Setcard/Release-Bundle übersprungen ({e})")

    except Exception as e:
        log(f"❌ [main] Artifact-Generierung fehlgeschlagen: {e}")
    
    return {"dna": dna_dict, "bundle": bundle}

def process_song(song: mp3_scanner.SongInfo, candidate_globe: dict, output_dir: Path | None,
                 style, platform: str = "full", dry_run: bool = False,
                 audio: Any = None, label: str | None = None,
                 default_niche: str | None = None, full_globe: dict | None = None,
                 renderer_backend: str = RENDERER_BACKEND,
                 wong_state: dict | None = None, force: bool = False,
                 tag_source_clips: bool = True, publish: bool = False,
                 webhook_enabled: bool = True, custom_webhook: str | None = None,
                 song_index: int = 1, total_songs: int = 1) -> bool:
    full_globe = full_globe if full_globe is not None else candidate_globe
    resolved_label = label or LABEL_NAME
    resolved_default_niche = default_niche or DEFAULT_HASHTAG_NICHE
    track_title = song.title or Path(song.path).stem
    artist_name = song.artist or "Unknown Artist"

    resolved_output_dir = _resolve_song_output_dir(output_dir, song.path, platform)
    output_path = _versioned_output_path(resolved_output_dir, song.path, platform)
    meta_dir = resolved_output_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    # ── Visuelle Song-Header Box ─────────────────────────────────────────────
    border = "═" * 78
    log(f"\n╔{border}╗")
    log(f"║ 🎵 TRACK [{song_index}/{total_songs}]: {track_title[:42]:<42} ARTIST: {artist_name[:16]:<16} ║")
    log(f"║ 📂 AUDIO:  {str(song.path)[-68:]:<68} ║")
    log(f"║ 🎯 PROFIL: {platform.upper():<10} 📁 ZIEL: {str(output_path.name)[-55:]:<55} ║")
    log(f"║ 🗂️ ORDNER: {str(resolved_output_dir)[-68:]:<68} ║")
    log(f"╚{border}╝")

    if not dry_run and not force:
        existing = _existing_output_path(resolved_output_dir, song.path, platform)
        if existing is not None:
            log(f"⚡ [Status] Video existiert bereits -> übersprungen: {existing.name} (--force erzwingt Re-Render).")
            return True
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    # ── [1/6] Audio- & Beat-Analyse ──────────────────────────────────────────
    log(f"\n┌─ [1/6] 🎵 Audio- & Takt-Analyse ──────────────────────────────────────────")
    if audio is None:
        try:
            audio = audio_analysis.analyze_song(song.path)
        except Exception as e:
            log(f"❌ Audioanalyse fehlgeschlagen, überspringe Song: {e}")
            return False

    log(f"  • Tempo / Dauer:       {audio.bpm:.1f} BPM | {audio.duration_sec:.1f}s")
    log(f"  • Beatgrid / Drops:    {len(audio.beat_times)} Beats detektiert")
    log(f"  • Stimmlage (Akustik): {audio.mc_gender} @ {audio.vocal_pitch_hz:.0f} Hz")
    if audio.repetition_windows:
        log(f"  • Schnelle Loops:      {len(audio.repetition_windows)} Repetitions-Zone(n) identifiziert")
    if audio.structure:
        struct_summary = " -> ".join(f"{lbl}({round(e - s)}s)" for s, e, lbl in audio.structure)
        log(f"  • Song-Struktur:       {struct_summary}")

    # ── [2/6] Semantik & Self-Learning Regie ──────────────────────────────────
    log(f"\n┌─ [2/6] 🧠 Semantik & Self-Learning Regie ─────────────────────────────────")
    semantics = song_semantics.get_semantics_for_song(song.path)
    song_mood_tags: list[str] = []
    song_style_weights: dict = {}
    beat_switch_intensity = 0.0
    if semantics:
        beat_switch_intensity = max(0.0, min(1.0, (semantics.get("beat_switch_count") or 0) / 4.0))
        song_mood_tags = list(semantics.get("mood_tags") or [])
        song_style_weights = dict(semantics.get("style_weights") or {})
        if song_mood_tags:
            song.tag_vector = mp3_scanner.build_tag_vector(
                [song.genre, song.mood, song.comment, song.title, song.lyrics] + song_mood_tags
            )
        slang_hits = list((semantics.get("slang") or {}).keys())
        movements = semantics.get("movements") or []
        log(f"  • Mood-Tags:           {', '.join(song_mood_tags) if song_mood_tags else '–'}")
        log(f"  • Slang / Keywords:    {', '.join(slang_hits) if slang_hits else '–'}")
        if movements:
            log(f"  • Tempo-Movements:     {movements} BPM")
        weed_hits = [t for t in song_mood_tags if t in song_semantics.WEED_VOCAB]
        weed_vibe_score = semantics.get("weed_vibe_score") or 0.0
        if weed_hits or weed_vibe_score > 0:
            log(f"  • 🌿 420-Weed Vibe:    Score={weed_vibe_score:.2f} | Tags={', '.join(weed_hits) or '–'}")

    lyrics_mc_gender = semantics.get("mc_gender") if semantics else None
    acoustic_mc_gender = audio.mc_gender
    if lyrics_mc_gender == "dual":
        fused_mc_gender = "dual"
    elif lyrics_mc_gender in ("female", "male"):
        if acoustic_mc_gender in ("female", "male") and acoustic_mc_gender != lyrics_mc_gender:
            fused_mc_gender = "dual"
        else:
            fused_mc_gender = lyrics_mc_gender
    elif acoustic_mc_gender in ("female", "male"):
        fused_mc_gender = acoustic_mc_gender
    else:
        fused_mc_gender = "unknown"
    audio.mc_gender = fused_mc_gender
    log(f"  • Fused MC-Gender:     {audio.mc_gender} (Akustik={acoustic_mc_gender}, Lyrics={lyrics_mc_gender or '–'})")

    song_id = db.upsert_song(
        path=song.path, bpm=audio.bpm, duration_sec=audio.duration_sec,
        tag_vector=song.tag_vector, beatgrid=audio.beat_times, sections=audio.sections,
        music_dna=audio.music_dna,
    )

    try:
        from self_learning import get_global_learning_engine
        learning_engine = get_global_learning_engine()
        suggested_director = learning_engine.choose_director_style(strategy="thompson")
        suggested_pacing = learning_engine.choose_pacing_strategy()
    except Exception:
        suggested_director = "cunningham"
        suggested_pacing = "beat_locked"

    if style is None or getattr(style, "name", "cinematic") in ("cinematic", "auto"):
        style = compile_style(suggested_director, ROOT_DIR / "styles")
    log(f"  • Regie-Archetyp:      '{suggested_director}' | Pacing: '{suggested_pacing}'")

    # ── [3/6] Timeline-Konstruktion & Rhythm-Matching ─────────────────────────
    log(f"\n┌─ [3/6] 🎬 Timeline-Konstruktion & Rhythm-Matching ────────────────────────")
    recent_used = db.get_recent_usage_ranges()
    timeline = build_timeline(
        song.tag_vector, audio, candidate_globe, recent_used, style=style, platform=platform,
        song_tags=song_mood_tags, song_path=song.path,
        beat_switch_intensity=beat_switch_intensity,
        pacing_strategy=suggested_pacing,
        song_semantics=semantics,
    )
    
    boundary_cuts = sum(1 for seg in timeline if seg.on_structure_boundary)
    cut_density = len(timeline) / (audio.duration_sec / 60.0) if audio.duration_sec > 0 else 0
    log(f"  • Segmente / Schnitte: {len(timeline)} Schnitte ({cut_density:.1f} Cuts/Min)")
    log(f"  • Boundary Snapping:   {boundary_cuts} Cut(s) exakt auf Takt-/Struktur-Grenzen")
    if beat_switch_intensity > 0:
        log(f"  • Polyrhythmik:        Intensität={beat_switch_intensity:.2f} ({semantics.get('beat_switch_count', 0)} Beat-Switches)")

    render_script = _build_render_script(
        song, timeline, style, output_path, globe=full_globe,
        song_mood_tags=song_mood_tags, song_mc_gender=audio.mc_gender,
        song_style_weights=song_style_weights, wong_state=wong_state,
        song_visual_objects=(semantics.get("visual_objects") if semantics else None),
        song_cluster_mask=(semantics.get("cluster_mask") if semantics else 0),
    )
    script_path = meta_dir / f"{_safe_song_stem(song.path)}_{platform}.edl.json"
    script_path.write_text(json.dumps(render_script, indent=2, ensure_ascii=False), encoding="utf-8")

    avg_vector_similarity = render_script.get("avg_vector_similarity")
    sim_str = f"{avg_vector_similarity:.2f}" if avg_vector_similarity is not None else "–"
    log(f"  • Vektor-Ähnlichkeit:  {sim_str} (Song <-> Clips Match-Score)")

    wong_agreement_rate = render_script.get("wong_agreement_rate")
    if wong_agreement_rate is not None:
        wong_avg_reward = render_script.get("wong_avg_reward_prediction")
        reward_str = f"{wong_avg_reward:.2f}" if wong_avg_reward is not None else "n/a"
        log(f"  • WONG-Vergleich:      {wong_agreement_rate * 100:.0f}% Übereinstimmung | Ø Reward={reward_str}")

    # C+ Creative Compiler OS (SongIR / SceneIR / Self-Critic)
    try:
        cplus_manifest = compile_creative_ir(song, audio, timeline, style, semantics=semantics, log_fn=log)
        cplus_path = meta_dir / f"{_safe_song_stem(song.path)}_{platform}.cplus.json"
        cplus_path.write_text(json.dumps(cplus_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log(f"  ⚠️ C+ Compiler Analyse übersprungen ({e})")

    # ── [4/6] Video-Rendering & Encoding ─────────────────────────────────────
    log(f"\n┌─ [4/6] ⚡ Video-Rendering & Encoding ─────────────────────────────────────")
    render_start_time = time.time()
    video_metadata = _build_video_metadata(song, render_script, platform)
    
    if dry_run:
        log(f"  ⚡ [Dry-Run] Rendering übersprungen -> EDL validiert: {script_path.name}")
    else:
        try:
            rendered_path = None
            if renderer_backend == "unreal":
                try:
                    import unreal_renderer
                    storyline = _build_storyline(song, audio, semantics)
                    log(f"  🎮 Starte Unreal Engine Movie Render Queue Backend...")
                    rendered_path = unreal_renderer.render_music_video(
                        timeline, song.path, str(output_path), log=log, platform=platform,
                        metadata=video_metadata, storyline=storyline,
                    )
                except Exception as e:
                    log(f"  ⚠️ Unreal-Renderer fehlgeschlagen ({e}) -> Fallback auf FFmpeg Backend.")
                    renderer_backend = "ffmpeg"

            if renderer_backend != "unreal":
                import renderer
                log(f"  🚀 Starte Direct-Subprocess FFmpeg Renderer (Platform: {platform})...")
                rendered_path = renderer.render_music_video(
                    timeline, song.path, str(output_path), log=log,
                    platform=platform, metadata=video_metadata, globe=full_globe
                )

            if not rendered_path or not Path(rendered_path).is_file():
                raise RuntimeError("Renderer meldete keinen gültigen Output.")
                
            render_duration = time.time() - render_start_time
            file_size_mb = Path(rendered_path).stat().st_size / (1024 * 1024)
            log(f"  ✅ Render abgeschlossen in {render_duration:.1f}s ({file_size_mb:.2f} MB) -> {Path(rendered_path).name}")

        except Exception as e:
            log(f"❌ [main] Rendering fehlgeschlagen: {e}\n{traceback.format_exc()}")
            return False

        db.record_usage_many([
            {"clip_path": seg.clip_path, "song_id": song_id, "position_in_render": pos, "clip_in": seg.clip_in_point, "clip_out": seg.clip_in_point + (seg.end_sec - seg.start_sec)}
            for pos, seg in enumerate(timeline)
        ])

    # ── [5/6] Artefakt-Generierung (DNA, Genome, Setcard, Meta) ───────────────
    log(f"\n┌─ [5/6] 📦 Artefakt-Generierung (DNA, Genome, Setcard, Meta) ─────────────")
    artifacts_res = {}
    if dry_run:
        log("  ℹ️ [Dry-run] Keine Artefakte erzeugt (kein Video gerendert).")
    else:
        artifacts_res = _finalize_song_artifacts(
            song, audio, timeline, style, output_path, full_globe, semantics,
            resolved_label, resolved_default_niche, platform, log
        )

    reward = _compute_render_reward(
        timeline, globe=full_globe, song_tag_vector=song.tag_vector,
        song_mood_tags=song_mood_tags, song_mc_gender=audio.mc_gender,
        song_style_weights=song_style_weights
    )

    if not dry_run:
        if output_path.exists() and output_path.stat().st_size > 1024 * 1024:
            db.record_experience(
                song_id, {"sections": len(audio.sections), "bpm": audio.bpm},
                {"segments": len(timeline), "style": style.name}, reward, [],
                "Deterministic resolver: energy, semantic tags, information density and continuity.",
                artifacts_res.get("dna", {}),
            )
        match_reasons = {seg["clip"]: seg["match_reason"] for seg in render_script.get("sequence", []) if seg.get("match_reason")}
        clip_pool.update_learned_from_render(full_globe, timeline, reward, save_cb=db.save_flat_globe, match_reasons=match_reasons)
        log(f"  🎯 Render-Reward: {reward:.2f} (Feedback in {len(set(s.clip_path for s in timeline))} Clips gespeichert)")

        try:
            import self_learning
            learner = self_learning.get_global_learner()
            director_style = getattr(style, "name", "cunningham") if style else "cunningham"
            res = learner.record_render_outcome(
                song=song, audio=audio, timeline=timeline, reward=reward,
                director=director_style, pacing_strategy=suggested_pacing, globe=full_globe,
            )
            log(f"  🧠 Self-Learning: Bandit aktualisiert (Director '{director_style}', Pulls: {res.get('total_renders')})")
        except Exception as e:
            log(f"  ⚠️ Self-Learning Feedback Warnung: {e}")

        if tag_source_clips and getattr(config, "TAG_SOURCE_CLIPS_ENABLED", True):
            try:
                import clip_tagging
                clip_tagging.tag_clips_after_render(timeline, full_globe, song, render_script, platform, log=log)
            except Exception as e:
                log(f"  ⚠️ Quell-Clip-Tagging übersprungen ({e})")

    # ── [6/6] Webhook Gateway & Cloud Distribution ───────────────────────────
    log(f"\n┌─ [6/6] 📡 Webhook Gateway & Release-Distribution ────────────────────────")
    if dry_run:
        log("  ℹ️ [Dry-run] Webhook-Versand übersprungen.")
    elif not webhook_enabled and not publish:
        log("  ℹ️ Webhook-Versand übersprungen (--no-webhook aktiv).")
    else:
        if output_path.exists() and output_path.stat().st_size > 1024 * 1024:
            try:
                import gdrive_discord_publisher
                target_webhooks = [custom_webhook] if custom_webhook else None
                pub_res = gdrive_discord_publisher.publish_release(
                    video_path=output_path,
                    audio_path=Path(song.path),
                    webhook_urls=target_webhooks,
                    upload_gdrive=publish,
                    log_fn=log
                )
                if pub_res.get("discord_posted"):
                    log(f"  🎉 Webhook-Übertragung erfolgreich! Setcard & Meta an Discord gepostet ({pub_res.get('webhooks_sent')} Ziel(e)).")
                else:
                    log(f"  ⚠️ Webhook konnte nicht zugestellt werden (Fehler: {pub_res.get('webhooks_failed')} gescheitert).")
            except Exception as e:
                log(f"  ❌ Fehler beim Webhook-Posting: {e}")
        else:
            log("  ⚠️ Video-Datei fehlt oder ist zu klein für Webhook-Versand.")

    log(f"\n🏁 [FERTIG] Song erfolgreich verarbeitet -> {output_path.name}")
    return True

def main():
    print(swag_banners.get_swag_banner(), flush=True)
    print(START_BANNER, flush=True)
    run_start_time = time.time()
    
    parser = argparse.ArgumentParser(description="1-Click MP3 + Clips -> Epic Music Video Pipeline")
    parser.add_argument("--song", type=str, default=None, help="Nur diesen einen Song verarbeiten (Pfad).")
    parser.add_argument("--limit", type=int, default=None, help="Nur die ersten N gefundenen Songs verarbeiten.")
    parser.add_argument("--rebuild-globe", action="store_true", help="Clip-Pool-Cache (flat-globe) komplett neu analysieren.")
    parser.add_argument("--output-dir", type=str, default=None, help="Zielordner für fertige Videos.")
    parser.add_argument("--style", type=str, default="cinematic", help="Lokales Genome-Style-Paket.")
    parser.add_argument("--platform", choices=("full", "tiktok"), default="full", help="Ausgabeprofil (full = 16:9, tiktok = 9:16).")
    parser.add_argument("--renderer", choices=("ffmpeg", "unreal"), default=RENDERER_BACKEND,
                        help="Render-Backend ('ffmpeg' oder 'unreal').")
    parser.add_argument("--dry-run", action="store_true", help="Nur Analyse und EDL-Erzeugung, kein Video rendern.")
    parser.add_argument("--force", action="store_true",
                        help="Rendert auch dann eine neue Version, wenn für Song+Plattform bereits ein Video existiert.")
    parser.add_argument("--skip-semantics-scan", action="store_true", help="Überspringt den automatischen song_semantics-Scan.")
    parser.add_argument("--wong-resolver", action="store_true",
                        help="Fragt WONGs GenomeResolver+RLBandit pro Segment als Vergleichssignal ab.")
    parser.add_argument("--no-clip-tags", action="store_true",
                        help="Deaktiviert das nachträgliche Schreiben von Tags in Quell-Clip-Dateien.")
    parser.add_argument("--webhook", type=str, default=None,
                        help="Benutzerdefinierte Discord-Webhook-URL für Setcard- & Meta-Postings.")
    parser.add_argument("--no-webhook", action="store_true",
                        help="Deaktiviert das automatische Posten der Setcard und Meta-Assets an Discord.")
    parser.add_argument("--publish", action="store_true",
                        help="Lädt fertige Videos, gemasterte MP3s und Setcards auf Google Drive hoch und postet sie in Webhooks.")
    # SYNAPSE Ecosystem Switches
    parser.add_argument("--synapse", action="store_true", help="Aktiviert das SYNAPSE AUDIO DYNAMICS Ökosystem.")
    parser.add_argument("--synapse-node", type=str, default=None, help="Fokussiert Ausführung auf spezifischen Node.")
    parser.add_argument("--synapse-mastering", choices=("trap", "pop", "edm", "boombap", "cinematic"), default="cinematic",
                        help="Masteringprofil für VEGA Neural DSP Engine.")
    parser.add_argument("--feedback-loop", action="store_true", help="Führt die Feedback-Schleife zwischen data und brain.bug aus.")
    parser.add_argument("--libsync", "--libsync-stats", dest="libsync_stats", action="store_true", help="Zeigt LibSync Flat Globe Statistik.")
    parser.add_argument("--libsync-repair", action="store_true", help="Repariert Flat Globe Cache.")
    parser.add_argument("--vector-tree-stats", "--vector-tree", dest="vector_tree_stats", action="store_true", help="Zeigt Vektor-Baum Metriken.")
    parser.add_argument("--rebuild-vector-tree", action="store_true", help="Baut Hierarchischen Vektor-Baum neu auf.")
    parser.add_argument("--self-learning-stats", action="store_true", help="Zeigt Self-Learning Status.")
    parser.add_argument("--sync-brain-bug", action="store_true", help="Führt den vollständigen bidirektionalen Abgleich mit brain.bug aus.")
    parser.add_argument("--dedup-suno", action="store_true", help="Sucht und verschiebt doppelte Suno-Dateien nach Musik/doppelt.")
    parser.add_argument("--tag-suno-m4a", action="store_true", help="Führt den Massen-Tagger für M4A-Audiodateien aus.")
    parser.add_argument("--cxx-status", action="store_true", help="Zeigt detaillierte C++ Acceleration Engine Diagnosedaten.")
    parser.add_argument("--prune-dead", "--prune-dead-clips", "--clean-clippool", "--prune-failed", dest="prune_dead_clips", action="store_true",
                        help="Prüft den Clip-Pool blitzschnell auf tote und fehlerhafte Einträge und entfernt sie aus Index und Vektor-Baum.")
    args = parser.parse_args()

    if args.prune_dead_clips:
        log("🧹 [Clip-Pool] Starte Fast-Update & Bereinigung toter und fehlerhafter Einträge...")
        globe, dead = db.prune_dead_clips(log=log)
        globe, failed = db.prune_failed_clips(log=log)
        total_removed = len(dead) + len(failed)
        log(f"✅ [Clip-Pool] Bereinigung abgeschlossen: {total_removed} Einträge ({len(dead)} tot, {len(failed)} fehlerhaft) entfernt. {len(globe)} aktive Clips verbleiben.")
        sys.exit(0)


    if args.sync_brain_bug:
        from brain_bug_sync import run_brain_bug_sync
        run_brain_bug_sync(log=log)
        sys.exit(0)

    if args.dedup_suno:
        from suno_deduplicator import run_deduplication
        run_deduplication(log=log)
        sys.exit(0)

    if args.tag_suno_m4a:
        from m4a_suno_tagger import main as run_tagger
        run_tagger()
        sys.exit(0)

    # Feedback Loop Auto-Sync
    from brain_feedback_loop import BrainFeedbackLoop
    fb_loop = BrainFeedbackLoop()
    if args.feedback_loop:
        log("[main] Manuelle Feedback-Schleife gestartet (--feedback-loop)...")
        fb_loop.run_feedback_cycle()
        sys.exit(0)
    else:
        fb_loop.sync_all_data_files()

    db.init_db()

    cxx_engine = cxx_accel.get_cxx_engine()
    status_info = cxx_engine.get_status_info()
    if cxx_engine.is_native_active:
        log(f"⚡ [C++ Accel] Native C++20 Beschleuniger aktiv ({status_info['version']})")
    else:
        log(f"⚡ [C++ Accel] SIMD Vectorized Fallback Engine aktiv ({status_info['engine_label']})")

    if args.cxx_status:
        log("\n" + "=" * 60)
        log("📊 [C++ Accel Engine Detaillierte Diagnose]")
        log("=" * 60)
        for k, v in status_info.items():
            log(f"  • {k:25s}: {v}")
        log("=" * 60 + "\n")
        sys.exit(0)

    if args.vector_tree_stats or args.rebuild_vector_tree:
        import vector_tree
        tree = vector_tree.get_global_vector_tree()
        if args.rebuild_vector_tree:
            log("[main] Baue Hierarchischen Vektor-Baum neu auf (--rebuild-vector-tree)...")
            globe = db.load_flat_globe()
            n = tree.build_from_globe(globe, force_rebuild=True)
            log(f"[main] Vektor-Baum neu aufgebaut: {n} Clips indiziert.")
        st = tree.stats()
        log(f"[main] Hierarchischer Vektor-Baum: {st['total_leaves']} Blätter, {len(st['domains'])} Domänen, Dimension={st['dimension']}.")
        for dom_name, dinfo in st['domains'].items():
            log(f"  • {dom_name:20s}: {dinfo['leaf_count']} Clips, {dinfo['sub_clusters']} Sub-Cluster, Ø Belohnung: {dinfo['mean_reward']:.2f}")
        sys.exit(0)

    if args.self_learning_stats:
        import self_learning
        learner = self_learning.get_global_learner()
        st = learner.stats()
        log(f"[main] Self-Learning Engine Status (--self-learning-stats):")
        log(f"  • Gesamte gelernte Renders: {st['total_renders_learned']} (Letzter Reward: {st['last_render_reward']:.2f})")
        log(f"  • Regie-Bandit (Director Arms):")
        for dname, dinfo in st['directors'].items():
            log(f"    - {dname:15s}: {dinfo['pulls']} Pulls, Ø Reward = {dinfo['mean_reward']:.3f}")
        log(f"  • Schnitt-Pacing Bandit:")
        for pname, pinfo in st['pacing'].items():
            log(f"    - {pname:15s}: {pinfo['pulls']} Pulls, Ø Reward = {pinfo['mean_reward']:.3f}")
        log(f"  • Gelernte Szenen-Übergänge im Graph: {st['transition_count']}")
        log(f"  • Aktive BPM-Resonanz-Klassen: {', '.join(st['resonance_brackets'])}")
        sys.exit(0)

    if args.libsync_stats:
        log("[main] LibSync Flat Globe Diagnose (--libsync-stats):")
        summary = db.libsync_stats()
        log(f"  - Gesamte Clips im Cache: {summary['total_clips']}")
        log(f"  - Abspielbare Clips: {summary['playback_ok_clips']}")
        log(f"  - Fehlgeschlagene Clips: {summary['failed_clips']}")
        g = summary['gender_breakdown']
        log(f"  - MC-Gender Aufschlüsselung: Weiblich={g['female']} | Männlich={g['male']} | Duett/Beide={g['dual']} | Neutral/Unbekannt={g['neutral_or_unknown']}")
        ar = summary['aspect_ratios']
        ar_str = ", ".join(f"{k}: {v}" for k, v in ar.items()) or "keine"
        log(f"  - Seitenverhältnisse: {ar_str}")
        sys.exit(0)

    if args.libsync_repair:
        log("[main] LibSync Flat Globe Auto-Reparatur (--libsync-repair)...")
        globe, repaired = db.repair_flat_globe(log=log)
        log(f"[main] Fertig: {repaired} Clip(s) repariert / aktualisiert.")
        sys.exit(0)

    style = compile_style(args.style, ROOT_DIR / "styles")
    log(f"🎨 [Genome] Style Compiler: {style.name} (deterministisch)")
    if args.synapse or getattr(config, 'SYNAPSE_ENABLED', False):
        log("🧠 [SYNAPSE AUDIO DYNAMICS] Ecosystem Kernel aktiv: 'Resonanz erzeugen. Werte erschaffen. Unsterblichkeit codieren.'")
        if args.synapse_node:
            node_key = args.synapse_node.upper()
            node_role = getattr(config, 'SYNAPSE_NODES', {}).get(node_key, "Custom Node")
            log(f"⚡ [SYNAPSE] Target Node: {node_key} ({node_role})")
        log(f"⚡ [SYNAPSE] Target Mastering Profile (VEGA): {args.synapse_mastering.upper()}")

    if user_prefs.has_preferences():
        log("👤 [User-Taste] Nutzergeschmack aktiv (user_preferences.yaml geladen).")
    else:
        log("👤 [User-Taste] Kein Nutzergeschmack konfiguriert (Standard-Gewichtung).")

    if args.skip_semantics_scan:
        log("📖 [Semantik] Song-Semantik-Scan übersprungen.")
    else:
        try:
            song_semantics.scan_and_learn(log=log)
        except Exception as e:
            log(f"⚠️ [Semantik] Song-Semantik-Scan Warnung: {e}")

    try:
        all_semantics = db.get_all_song_semantics()
        learned_niche = viral_strategy.learn_default_niche(all_semantics)
        log(f"🎯 [Viral] Gelernte Standard-Hashtag-Nische: '{learned_niche}'")
    except Exception as e:
        learned_niche = DEFAULT_HASHTAG_NICHE
        log(f"🎯 [Viral] Niche-Lernen Fallback auf Default '{learned_niche}': {e}")

    log("🔍 [Clip-Pool] Lade / synchronisiere Flat-Globe Index...")
    globe = {} if args.rebuild_globe else db.load_flat_globe()
    fresh_cached = _count_fresh_cached_clips(globe)
    if not args.rebuild_globe and fresh_cached > CLIP_POOL_SKIP_SCAN_FRESH_THRESHOLD:
        log(f"⚡ [Clip-Pool] {fresh_cached} frische Clips im Cache (> {CLIP_POOL_SKIP_SCAN_FRESH_THRESHOLD}) -> Schneller Start.")
    else:
        try:
            globe = clip_pool.build_or_update_globe(globe, log=log, save_every=25, on_progress=db.save_flat_globe)
        except KeyboardInterrupt:
            log("🛑 Abgebrochen durch Benutzer (Ctrl+C).")
            sys.exit(130)
    log(f"📁 [Clip-Pool] Bereit: {len(globe)} indizierte Quell-Clips.")

    wong_state = init_wong_state(globe, log) if args.wong_resolver else None

    no_explicit_args = len(sys.argv) == 1
    platforms = ["full", "tiktok"] if no_explicit_args else [args.platform]
    if no_explicit_args:
        log("🚀 [Batch] Kein Parameter übergeben -> Auto-Batch: alle Songs, 16:9 + 9:16 TikTok.")

    tiktok_globe = None
    if "tiktok" in platforms:
        before = len(globe)
        tiktok_globe = clip_pool.filter_globe_to_subdirs(globe, subdirs=TIKTOK_CLIP_SUBDIRS)
        log(f"📱 [TikTok] Vertikaler Clip-Pool vorbereitet: {len(tiktok_globe)}/{before} Clips aktiv.")

    if args.song:
        target = Path(args.song).resolve()
        if target.is_file():
            info = mp3_scanner._read_tags_mutagen(str(target))
            info.tag_vector = mp3_scanner.build_tag_vector(
                [info.genre, info.mood, info.comment, info.title, info.lyrics]
            )
            songs = [info]
        else:
            all_songs = mp3_scanner.scan_all_songs()
            songs = [s for s in all_songs if Path(s.path).resolve() == target]
            if not songs:
                target_str = str(target).lower()
                songs = [s for s in all_songs if str(Path(s.path).resolve()).lower() == target_str]
            if not songs:
                log(f"❌ [main] Song nicht gefunden: {args.song}")
                sys.exit(1)
    else:
        songs = mp3_scanner.scan_all_songs()
        if args.limit: songs = songs[: args.limit]

    output_dir = Path(args.output_dir) if args.output_dir else None
    ok, failed, skipped = 0, 0, 0
    interrupted = False

    if not args.dry_run and not args.force:
        skip_paths = {s.path for s in songs if _all_outputs_exist(s, output_dir, platforms)}
        if skip_paths:
            for s in songs:
                if s.path in skip_paths:
                    log(f"⏭️ [Übersprungen] Alle {len(platforms)} Plattform-Versionen vorhanden: {Path(s.path).name}")
            skipped += len(skip_paths) * len(platforms)
            songs = [s for s in songs if s.path not in skip_paths]

    total_tasks = len(songs) * len(platforms)
    log(f"\n🚀 [Start] {len(songs)} Song(s) zur Verarbeitung ({total_tasks} Gesamtaufgaben).")
    if not args.no_webhook:
        log("📡 [Webhook] Automatischer Setcard- & Meta-Webhook-Dispatch aktiv nach jedem Render.")

    AUDIO_PREFETCH_WORKERS = 2
    audio_pool = ThreadPoolExecutor(max_workers=AUDIO_PREFETCH_WORKERS)
    try:
        pending_futures = [
            audio_pool.submit(audio_analysis.analyze_song, songs[j].path)
            for j in range(min(AUDIO_PREFETCH_WORKERS, len(songs)))
        ]

        for i, song in enumerate(songs):
            current_future = pending_futures.pop(0)
            next_idx = i + AUDIO_PREFETCH_WORKERS
            if next_idx < len(songs):
                pending_futures.append(
                    audio_pool.submit(audio_analysis.analyze_song, songs[next_idx].path)
                )
            try:
                audio = current_future.result()
            except KeyboardInterrupt:
                interrupted = True
                break
            except Exception as e:
                log(f"❌ [main] Audioanalyse fehlgeschlagen für {song.path}: {e}")
                failed += len(platforms)
                continue
                
            for platform in platforms:
                platform_globe = tiktok_globe if platform == "tiktok" else globe
                try:
                    success = process_song(
                        song, platform_globe, output_dir, style,
                        platform=platform, dry_run=args.dry_run, audio=audio,
                        label=LABEL_NAME, default_niche=learned_niche,
                        full_globe=globe, renderer_backend=args.renderer,
                        wong_state=wong_state, force=args.force,
                        tag_source_clips=not args.no_clip_tags, publish=args.publish,
                        webhook_enabled=not args.no_webhook, custom_webhook=args.webhook,
                        song_index=i + 1, total_songs=len(songs)
                    )
                except KeyboardInterrupt:
                    log(f"🛑 [main] Abgebrochen (Ctrl+C) bei {song.path} ({platform}).")
                    interrupted = True
                    break
                except Exception as e:
                    log(f"❌ [main] Fehler bei {song.path} ({platform}): {e}\n{traceback.format_exc()}")
                    success = False
                if success: ok += 1
                else: failed += 1
            if interrupted: break
    finally:
        audio_pool.shutdown(wait=False, cancel_futures=True)

    elapsed = time.time() - run_start_time
    elapsed_str = f"{elapsed / 60:.1f} Min" if elapsed >= 60 else f"{elapsed:.1f}s"

    border = "═" * 78
    log(f"\n╔{border}╗")
    log(f"║                      ✨ PIPELINE ABSCHLUSS-BERICHT ✨                         ║")
    log(f"╠{border}╣")
    log(f"║  • Erfolgreich abgeschlossen: {ok:<48} ║")
    log(f"║  • Bereits vorhanden (Skip):  {skipped:<48} ║")
    log(f"║  • Fehlgeschlagen:            {failed:<48} ║")
    log(f"║  • Gesamte Ausführungszeit:   {elapsed_str:<48} ║")
    if not args.no_webhook:
        log(f"║  • Webhook Status:            Aktiv (Setcard HTML & Meta JSON versendet)       ║")
    log(f"║  • Google Drive Cloud Ordner: https://drive.google.com/drive/folders/1sa62Q... ║")
    if interrupted:
        log(f"║  ⚠️ VORZEITIG DURCH BENUTZER ABGEBROCHEN (Ctrl+C)                              ║")
    log(f"╚{border}╝\n")

    if interrupted: sys.exit(130)

if __name__ == "__main__":
    main()
