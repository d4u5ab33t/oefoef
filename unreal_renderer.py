"""
unreal_renderer.py — Optionales Render-Backend über Unreal Engine (Movie
Render Queue) als Alternative zum bestehenden ffmpeg-Renderer (renderer.py).

STATUS (aktualisiert): UNREAL_ENGINE_CMD/UNREAL_PROJECT_PATH in config.py
zeigen inzwischen auf eine echte, installierte UE-5.8-Engine + ein echtes
testue1-Projekt -- die Engine/Projekt-Ebene ist also eingerichtet. Was darin
aber noch FEHLT (Stand: dieser Kommentar), sind die render-spezifischen
Assets, die unreal_side/build_and_render.py fest referenziert: die Map
UNREAL_MAP ("/Game/Maps/BeatSyncStage") und das Movie-Render-Queue-Preset
UNREAL_MRQ_CONFIG ("/Game/MRQ/DefaultConfig") existieren im Content-Ordner
von testue1 nicht. BUGFIX: _check_configured() prüfte das bisher NICHT --
sobald Engine+Projekt-Pfade stimmten, lief render_music_video() den vollen
UnrealEditor-Cmd.exe-Subprocess an, der dann headless hochfuhr (mehrere
Minuten) und erst TIEF im Movie-Render-Queue-Job an der fehlenden Map
scheiterte, im schlimmsten Fall erst nach UNREAL_RENDER_TIMEOUT_SEC (1h).
_check_configured() prüft jetzt zusätzlich, ob Map+MRQ-Config tatsächlich
als Datei im Content-Ordner liegen (das "unreal"-Python-Modul ist außerhalb
des Editors nicht importierbar, siehe unreal_side/build_and_render.py --
daher reine Dateisystem-Prüfung, kein echtes Asset-Laden) und fällt sonst
weiterhin sauber+schnell mit UnrealNotConfiguredError zurück auf ffmpeg
(siehe main.py::process_song), statt main.py zum Absturz zu bringen oder
main.py stundenlang auf einen zum Scheitern verurteilten Render warten zu
lassen.

WIE ES FUNKTIONIEREN SOLL, SOBALD UNREAL INSTALLIERT/EINGERICHTET IST:
  1. render_music_video() schreibt die Timeline als JSON-Manifest (Clip-Pfad,
     Start/Ende, In-Point, Cut-Style etc. pro Segment) nach TMP_DIR.
  2. Startet UnrealEditor-Cmd.exe headless mit dem konfigurierten Projekt und
     führt darin das Companion-Skript unreal_side/build_and_render.py aus
     (über -ExecutePythonScript=), das Manifest wird per Kommandozeilen-
     Argument durchgereicht.
  3. build_and_render.py läuft INNERHALB von Unreals eingebettetem Python
     (das "unreal"-Modul ist nur dort importierbar) und baut daraus eine
     Level Sequence mit einem Media-Track pro Timeline-Segment sowie einen
     Movie Render Queue Job, der exakt auf output_path rendert.
  4. Diese Datei wartet auf den Subprocess, validiert den Output und gibt den
     Pfad zurück — identische Rückgabe-Semantik wie renderer.render_music_video
     (str | None), damit main.py beide Backends austauschbar aufrufen kann.

Bewusst NICHT enthalten: automatisches Anlegen des Unreal-Projekts selbst
(.uproject, Maps, MRQ-Preset-Assets) — das ist einmaliger, manueller Editor-
Aufwand, den kein Kommandozeilen-Skript sinnvoll ersetzen kann.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from config import (
    TMP_DIR,
    UNREAL_ENGINE_CMD,
    UNREAL_MAP,
    UNREAL_MRQ_CONFIG,
    UNREAL_PROJECT_PATH,
    UNREAL_RENDER_TIMEOUT_SEC,
    UNREAL_START_IMAGE_DURATION_SEC,
    UNREAL_START_IMAGE_PATH,
)

# Bild-Endungen, die als Start-Image-Kandidat gelten, wenn UNREAL_START_IMAGE_PATH
# auf einen Ordner statt eine einzelne Datei zeigt.
_START_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".jfif")


def _resolve_start_image(song_path: str) -> Path | None:
    """Löst UNREAL_START_IMAGE_PATH (config.py) zu einer konkreten Bilddatei
    auf. Zeigt der konfigurierte Pfad bereits auf eine Datei, wird die 1:1
    verwendet. Zeigt er auf einen Ordner (z.B. eine ganze upscayl-Batch-
    Ausgabe), wird PRO SONG deterministisch genau ein Bild daraus gewählt --
    ein stabiler Hash über song_path entscheidet den Index (gleicher Song
    bekommt bei jedem Render dasselbe Startbild, verschiedene Songs streuen
    über den ganzen Bilder-Pool), statt zufällig bei jedem Lauf zu wechseln
    oder immer stur dasselbe erste Bild zu nehmen.

    Gibt None zurück, wenn UNREAL_START_IMAGE_PATH leer/nicht gesetzt ist
    oder auf nichts Verwendbares zeigt (main.py/render_music_video machen
    dann einfach ohne Start-Image weiter statt abzustürzen)."""
    if not UNREAL_START_IMAGE_PATH:
        return None
    configured = Path(UNREAL_START_IMAGE_PATH)
    if configured.is_file():
        return configured
    if not configured.is_dir():
        return None
    candidates = sorted(
        p for p in configured.iterdir()
        if p.is_file() and p.suffix.lower() in _START_IMAGE_EXTS
    )
    if not candidates:
        return None
    digest = hashlib.sha1(song_path.encode("utf-8")).hexdigest()
    idx = int(digest, 16) % len(candidates)
    return candidates[idx]


class UnrealNotConfiguredError(RuntimeError):
    """Ausgelöst, wenn UNREAL_ENGINE_CMD/UNREAL_PROJECT_PATH in config.py
    (noch) nicht gesetzt sind oder auf nicht-existente Pfade zeigen.
    main.py fängt genau diesen Typ ab, um automatisch auf den ffmpeg-
    Renderer zurückzufallen, statt den kompletten main.py-Lauf für DIESEN
    Song abzubrechen."""


_UNREAL_SIDE_SCRIPT = Path(__file__).resolve().parent / "unreal_side" / "build_and_render.py"


def _game_path_to_content_file(game_path: str, ext: str) -> Path:
    """Wandelt einen Unreal-Asset-Pfad im Editor-Format ("/Game/Maps/Foo")
    in den zugehörigen Pfad auf der Festplatte um ("<Projekt>/Content/Maps/
    Foo.ext"). Reine String-/Pfad-Arithmetik, KEIN echtes Asset-Laden --
    das "unreal"-Python-Modul ist außerhalb des Editors nicht importierbar
    (siehe unreal_side/build_and_render.py), _check_configured() läuft aber
    bewusst außerhalb des Editors (davor, um den teuren Subprocess-Start
    überhaupt erst zu entscheiden) und kann deshalb nur prüfen, ob die
    erwartete Asset-Datei physisch existiert -- kein Ersatz für eine echte
    Asset-Validierung (kaputte/leere .uasset-Dateien fallen so NICHT auf),
    aber genug, um den häufigsten Fall (Asset schlicht noch nicht angelegt)
    schnell statt erst nach minutenlangem Engine-Hochfahren zu erkennen."""
    rel = game_path[len("/Game/"):] if game_path.startswith("/Game/") else game_path.lstrip("/")
    content_dir = Path(UNREAL_PROJECT_PATH).resolve().parent / "Content"
    return content_dir / f"{rel}{ext}"


def _check_configured() -> None:
    missing = []
    if not UNREAL_ENGINE_CMD:
        missing.append("UNREAL_ENGINE_CMD")
    if not UNREAL_PROJECT_PATH:
        missing.append("UNREAL_PROJECT_PATH")
    if missing:
        raise UnrealNotConfiguredError(
            "Unreal-Renderer angefordert, aber (noch) nicht eingerichtet — "
            f"in config.py nicht gesetzt: {', '.join(missing)}. Solange "
            "Unreal Engine nicht installiert/konfiguriert ist, bitte "
            "RENDERER_BACKEND='ffmpeg' lassen bzw. --renderer ffmpeg nutzen."
        )
    if not Path(UNREAL_ENGINE_CMD).is_file():
        raise UnrealNotConfiguredError(
            f"UNREAL_ENGINE_CMD zeigt auf keine vorhandene Datei: {UNREAL_ENGINE_CMD}"
        )
    if not Path(UNREAL_PROJECT_PATH).is_file():
        raise UnrealNotConfiguredError(
            f"UNREAL_PROJECT_PATH zeigt auf keine vorhandene Datei: {UNREAL_PROJECT_PATH}"
        )
    if not _UNREAL_SIDE_SCRIPT.is_file():
        raise UnrealNotConfiguredError(
            f"Companion-Skript fehlt: {_UNREAL_SIDE_SCRIPT} "
            "(unreal_side/build_and_render.py)."
        )
    # BUGFIX (siehe Modul-Docstring oben): Engine+Projekt-Pfade allein reichen
    # nicht -- build_and_render.py referenziert fest UNREAL_MAP/UNREAL_MRQ_CONFIG
    # als konkrete Assets. Fehlen die im Projekt (Stand testue1: ja), lief der
    # komplette UnrealEditor-Cmd.exe-Subprocess bisher trotzdem minutenlang an,
    # um erst tief in der Movie Render Queue zu scheitern. Jetzt vorab per
    # Dateisystem-Check erkannt -> sauberer, schneller Fallback auf ffmpeg.
    map_file = _game_path_to_content_file(UNREAL_MAP, ".umap")
    if not map_file.is_file():
        raise UnrealNotConfiguredError(
            f"UNREAL_MAP '{UNREAL_MAP}' existiert nicht im Projekt (erwartet: {map_file}). "
            "Die Render-Map muss einmalig im Unreal-Editor angelegt werden, "
            "bevor --renderer unreal einen echten Render versuchen kann."
        )
    mrq_config_file = _game_path_to_content_file(UNREAL_MRQ_CONFIG, ".uasset")
    if not mrq_config_file.is_file():
        raise UnrealNotConfiguredError(
            f"UNREAL_MRQ_CONFIG '{UNREAL_MRQ_CONFIG}' existiert nicht im Projekt "
            f"(erwartet: {mrq_config_file}). Das Movie-Render-Queue-Preset muss "
            "einmalig im Unreal-Editor angelegt werden, bevor --renderer unreal "
            "einen echten Render versuchen kann."
        )


def _segment_to_dict(segment: Any) -> dict:
    """Extrahiert nur die Felder, die build_and_render.py auf Unreal-Seite
    tatsächlich braucht (Media-Track-Aufbau + Cut-Metadaten) — bewusst ein
    Subset von main.py::_build_render_script's vollem .edl.json, damit das
    Manifest schlank bleibt."""
    return {
        "clip_path": segment.clip_path,
        "start_sec": round(segment.start_sec, 3),
        "end_sec": round(segment.end_sec, 3),
        "clip_in_point": round(segment.clip_in_point, 3),
        "transition": segment.transition or "cut",
        "cut_style": getattr(segment, "cut_style", None),
        "target_energy": round(segment.target_energy, 4),
        "fx": list(getattr(segment, "fx", ()) or ()),
    }


def _write_manifest(timeline: list, song_path: str, output_path: str, platform: str = "full",
                    start_image: Path | None = None, storyline: str | None = None) -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    # platform mit ins Manifest -- build_and_render.py kann daraus (analog zu
    # renderer.py/config.OUTPUT_RESOLUTION_BY_PLATFORM) die Zielauflösung der
    # Render-Sequence ableiten (9:16 für "tiktok" statt 16:9), sobald Unreal
    # eingerichtet ist. Aktuell nur durchgereicht, keine Auswirkung, solange
    # UnrealNotConfiguredError vorher greift.
    manifest = {
        "version": "unreal-mrq-manifest-v1",
        "song_path": song_path,
        "output_path": output_path,
        "platform": platform,
        "map": UNREAL_MAP,
        "mrq_config": UNREAL_MRQ_CONFIG,
        # Optionales Intro-Standbild vor dem ersten Clip-Segment (siehe
        # _resolve_start_image/config.UNREAL_START_IMAGE_PATH) -- verschiebt
        # in build_and_render.py._build_level_sequence ALLE Segmente um
        # duration_sec nach hinten, damit die Gesamt-Timeline exakt um die
        # Standbild-Dauer länger wird statt sich mit Segment 0 zu überlappen.
        "start_image": (
            {"path": str(start_image), "duration_sec": UNREAL_START_IMAGE_DURATION_SEC}
            if start_image else None
        ),
        # Kurze, aus dem Song-Kontext (Mood-Tags/Slang/Struktur, siehe
        # main.py::_build_storyline) generierte Storyline -- rein informativ/
        # kreativer Kontext fürs spätere Sequence-Set-Dressing im Unreal-
        # Editor bzw. als Logging-/Dokumentationszeile, beeinflusst (noch)
        # nicht automatisch die Clip-Auswahl selbst.
        "storyline": storyline,
        "segments": [_segment_to_dict(seg) for seg in timeline],
    }
    manifest_path = TMP_DIR / f"unreal_manifest_{uuid.uuid4().hex}.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest_path


def render_music_video(timeline: list, song_path: str, output_path: str, log=None,
                       platform: str = "full", metadata: dict | None = None,
                       storyline: str | None = None) -> str | None:
    """Signatur bewusst identisch zu renderer.render_music_video() (inkl.
    platform-Parameter), damit main.py::process_song beide Backends
    austauschbar aufrufen kann.

    metadata: wird von main.py IMMER mitgegeben (siehe renderer.py's
    ffmpeg-Metadata-Embedding), hier aber bewusst NICHT verdrahtet -- der
    Unreal-Pfad rendert über Unreals eigene Movie-Render-Queue/Encoder statt
    über den ffmpeg-Mux-Schritt in renderer.py, in den die MP4-Tags/Kapitel
    aktuell eingehängt sind. Nur entgegengenommen, damit main.py beide
    Backends mit identischen Keyword-Args aufrufen kann, ohne TypeError.

    storyline: optionaler, aus dem Song-Kontext generierter Kurztext (siehe
    main.py::_build_storyline) -- landet nur im Manifest/Log, siehe
    _write_manifest."""
    def _log(msg: str):
        if log:
            log(msg)

    if not timeline:
        raise ValueError("Leere Timeline übergeben.")

    # Wirft UnrealNotConfiguredError, solange config.py UNREAL_ENGINE_CMD/
    # UNREAL_PROJECT_PATH nicht gesetzt hat -- main.py fängt das ab und
    # rendert automatisch mit ffmpeg weiter (siehe process_song).
    _check_configured()

    start_image = _resolve_start_image(song_path)
    if start_image:
        _log(f"[unreal_renderer] Start-Image gewählt -> {start_image.name} "
             f"({UNREAL_START_IMAGE_DURATION_SEC:.1f}s vor dem ersten Clip-Segment).")
    if storyline:
        _log(f"[unreal_renderer] Storyline (Song-Kontext): {storyline}")

    manifest_path = _write_manifest(timeline, song_path, output_path, platform=platform,
                                    start_image=start_image, storyline=storyline)
    _log(f"[unreal_renderer] Manifest geschrieben -> {manifest_path} ({len(timeline)} Segmente).")

    # BUGFIX: "-game" wurde hier ENTFERNT. build_and_render.py baut die
    # LevelSequence per unreal.AssetToolsHelpers/unreal.EditorAssetLibrary und
    # startet den Render über unreal.MoviePipelinePIEExecutor -- alle drei sind
    # Editor-only-APIs (PIEExecutor = "Play In Editor", braucht laut Epic-Doku
    # zwingend eine laufende Editor-Session). Mit "-game" läuft der Prozess
    # stattdessen im reinen Game-Modus, in dem AssetToolsHelpers/
    # EditorAssetLibrary schlicht nicht existieren bzw. PIEExecutor keine
    # Session zum Hineinspielen findet -- der Job wäre nie tatsächlich
    # gerendert worden (oder sofort mit AttributeError abgestürzt). Für den
    # reinen Game-Modus gäbe es unreal.MoviePipelineInProcessExecutor, aber
    # das hilft hier nicht, weil die Asset-Erstellung sowieso Editor-Kontext
    # braucht -- daher läuft der komplette Job jetzt im Editor-Modus
    # (weiterhin -unattended/-nosplash/-nopause/-RenderOffscreen, damit keine
    # UI/Interaktion nötig ist).
    cmd = [
        str(UNREAL_ENGINE_CMD),
        str(UNREAL_PROJECT_PATH),
        UNREAL_MAP,
        "-nosplash",
        "-unattended",
        "-nopause",
        "-RenderOffscreen",
        f"-ExecutePythonScript={_UNREAL_SIDE_SCRIPT}",
        f"-OidasheimManifest={manifest_path}",
        "-log",
    ]
    _log(f"[unreal_renderer] Starte Unreal-Subprocess: {' '.join(cmd)}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=UNREAL_RENDER_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Unreal-Render-Subprocess nach {UNREAL_RENDER_TIMEOUT_SEC}s abgebrochen (Timeout)."
        )
    duration = time.time() - start

    if result.stdout:
        _log(f"[unreal_renderer] stdout (letzte 2000 Zeichen):\n{result.stdout[-2000:]}")
    if result.stderr:
        _log(f"[unreal_renderer] stderr (letzte 2000 Zeichen):\n{result.stderr[-2000:]}")

    if result.returncode != 0:
        raise RuntimeError(
            f"Unreal-Subprocess beendete sich mit Exit-Code {result.returncode} "
            f"nach {duration:.1f}s (siehe stderr oben)."
        )

    out = Path(output_path)
    if not out.is_file() or out.stat().st_size <= 0:
        raise RuntimeError(
            f"Unreal-Render meldete Erfolg (Exit 0), aber Output fehlt/leer: {output_path}"
        )

    _log(f"[unreal_renderer] Render fertig in {duration:.1f}s -> {output_path}")
    return str(out)
