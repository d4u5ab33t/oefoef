"""
otio_export.py — Exportiert eine fertige oefoef-Timeline (list[TimelineSegment])
zusätzlich als OpenTimelineIO-Projekt (.otio), das sich direkt in DaVinci
Resolve, Adobe Premiere Pro oder Foundry Nuke öffnen/importieren lässt.

Rein additiv: der Export läuft NACH dem eigentlichen ffmpeg-Rendering bzw.
NACH dem Schreiben des .edl.json (siehe main.py::process_song) und hat keinen
Einfluss auf Clip-Auswahl, Timeline-Aufbau oder das gerenderte Video selbst.
Ein Fehler hier (z.B. fehlende opentimelineio-Installation) darf den Render
nie zum Absturz bringen -- main.py fängt das entsprechend ab, analog zu den
anderen Post-Render-Artefakten in main._finalize_song_artifacts.

MAPPING oefoef -> OTIO:
- TimelineSegment.clip_in_point + (end_sec - start_sec) -> Clip.source_range
  (der ZEITBEREICH IM QUELLCLIP -- die Position AUF der Zeitleiste ergibt
  sich in OTIO automatisch aus der Reihenfolge der Clips in der Track).
- TimelineSegment.clip_path -> ExternalReference.target_url (file://-URI).
- TimelineSegment.cut_style in {"dissolve","fade_out"} -> echte OTIO-
  Transition (SMPTE_Dissolve) zwischen den betroffenen Clips. Alle anderen
  cut_styles (hard_cut/jump_cut/push/break/whip) bleiben harte Schnitte --
  das entspricht dem, was renderer.py für diese Styles tatsächlich tut
  (Kamera-/Zoom-Effekte, keine echten Video-Transitions).
- Alle übrigen Segment-Felder (theme, camera, lighting, color, section_label,
  structure_label, sync_type, motion_direction/_score, target_energy,
  speed_factor, scratch, fx) landen 1:1 als Clip.metadata["oefoef"] -- jedes
  Tool, das OTIO-Metadata ausliest, hat so vollen Zugriff auf die komplette
  oefoef-Dramaturgie-Information pro Clip, ohne zusätzlich das .edl.json
  parsen zu müssen.

WICHTIG -- Speed-Ramp (TimelineSegment.speed_factor != 1.0): wird bewusst
NICHT als OTIO-LinearTimeWarp gesetzt. Der ffmpeg-Renderer wendet die Rampe
direkt auf den Rohclip an (setpts-Filter, siehe renderer.py); der hier
referenzierte source_range bezieht sich auf die UNVERÄNDERTE Clip-Quelle.
Ein zusätzlicher LinearTimeWarp würde die Rampe bei einem NLE-Import
fälschlich ein zweites Mal anwenden. speed_factor bleibt daher nur Info in
metadata, nicht als aktive OTIO-Zeitmanipulation.
"""
from pathlib import Path

import opentimelineio as otio

# Wie viel Überlappung (Sekunden) eine dissolve/fade_out-Transition auf JEDER
# Seite vom vorherigen/nächsten Clip "leiht" -- analog zu PUSH_FADE_XFADE_SEC
# in config.py, aber eigene Konstante, weil OTIO-Transitions ein anderes
# Timing-Modell haben (in_offset/out_offset statt eval=frame-ffmpeg-Filter).
OTIO_TRANSITION_OVERLAP_SEC = 0.35
OTIO_DISSOLVE_CUT_STYLES = {"dissolve", "fade_out"}


def _file_url(path: str) -> str:
    """Absoluter Dateipfad -> file://-URI (plattformübergreifend, inkl.
    Windows-Laufwerksbuchstaben und Leerzeichen/Sonderzeichen im Pfad)."""
    return Path(path).resolve().as_uri()


def _segment_metadata(seg) -> dict:
    """Alle für NLE-Nutzer/Downstream-Tools interessanten oefoef-Felder, die
    OTIO selbst nicht kennt -- siehe Modul-Docstring."""
    return {
        "theme": seg.theme,
        "semantic_symbol": seg.semantic_symbol,
        "camera": seg.camera,
        "lighting": seg.lighting,
        "color": seg.color,
        "section_label": seg.section_label,
        "structure_label": seg.structure_label,
        "on_structure_boundary": bool(seg.on_structure_boundary),
        "cut_style": seg.cut_style,
        "sync_type": seg.sync_type,
        "target_energy": round(seg.target_energy, 4),
        "information_density": round(seg.information_density, 4),
        "motion_score": round(seg.motion_score, 4),
        "motion_direction": round(seg.motion_direction, 4),
        "speed_factor": round(seg.speed_factor, 3),
        "repetition": bool(seg.repetition),
        "scratch": bool(seg.scratch),
        "fx": list(seg.fx or ()),
    }

def _make_clip(seg, rate: float, index: int) -> "otio.schema.Clip":
    duration = max(0.0, seg.end_sec - seg.start_sec)
    clip = otio.schema.Clip(
        name=f"{index:03d}_{Path(seg.clip_path).stem}",
        media_reference=otio.schema.ExternalReference(target_url=_file_url(seg.clip_path)),
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(seg.clip_in_point * rate, rate),
            duration=otio.opentime.RationalTime(duration * rate, rate),
        ),
    )
    clip.metadata["oefoef"] = _segment_metadata(seg)
    return clip


def build_otio_timeline(timeline: list, song_path: str, project_name: str,
                        fps: float = 30.0) -> "otio.schema.Timeline":
    """Baut aus einer fertigen oefoef-Timeline (list[TimelineSegment]) ein
    In-Memory OTIO-Timeline-Objekt. Getrennt von export_otio(), damit
    Aufrufer/Tests das Objekt auch ohne Diskschreiben inspizieren können."""
    if not timeline:
        raise ValueError("Leere Timeline: kein OTIO-Export möglich.")

    otio_timeline = otio.schema.Timeline(name=project_name)
    otio_timeline.metadata["oefoef"] = {"source_audio": song_path}
    track = otio.schema.Track(name="oefoef_video")
    otio_timeline.tracks.append(track)

    for i, seg in enumerate(timeline):
        track.append(_make_clip(seg, fps, i))
        # Dissolve/Fade-Out-Transition NACH diesem Clip einfügen, falls das
        # NÄCHSTE Segment das verlangt -- main.py._calculate_cut_style setzt
        # cut_style auf dem Segment, das EINGESCHNITTEN wird, die Transition
        # liegt also zwischen clip[i] und clip[i+1], ausgelöst durch
        # clip[i+1]s cut_style.
        if i + 1 < len(timeline) and timeline[i + 1].cut_style in OTIO_DISSOLVE_CUT_STYLES:
            overlap = otio.opentime.RationalTime(OTIO_TRANSITION_OVERLAP_SEC * fps, fps)
            track.append(otio.schema.Transition(
                transition_type=otio.schema.TransitionTypes.SMPTE_Dissolve,
                in_offset=overlap, out_offset=overlap,
            ))

    return otio_timeline


def export_otio(timeline: list, song_path: str, output_path, fps: float = 30.0):
    """Baut die OTIO-Timeline und schreibt sie neben das Video (gleicher
    Stem, Endung .otio -- siehe main.py::process_song, analog zu .edl.json/
    .genome.json). Gibt den geschriebenen Path zurück."""
    output_path = Path(output_path)
    otio_timeline = build_otio_timeline(timeline, song_path, output_path.stem, fps=fps)
    otio_path = output_path.with_suffix(".otio")
    otio.adapters.write_to_file(otio_timeline, str(otio_path))
    return otio_path
