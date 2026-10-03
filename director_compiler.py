"""
director_compiler.py — "Director Compiler Stack"-Fassade über bereits
vorhandene Bausteine (audio_analysis, timeline_builder, creative_genome).

BEWUSSTE DESIGN-ENTSCHEIDUNG: Dies ist KEINE Neuimplementierung der 6
Compiler-Stufen (Music/Emotion/Motion/Color/Camera/Shot) als eigenständige,
voneinander unabhängige Analyse-Pipelines. Das würde die bereits in
audio_analysis.py/timeline_builder.py/creative_genome.py laufende (bewährte)
Logik komplett duplizieren und zwei parallele Wahrheiten über denselben Song
erzeugen, die mit der Zeit auseinanderlaufen können.

Stattdessen organisiert dieses Modul die von main.py::process_song bereits
berechneten Werte (audio_analysis.AudioAnalysis + die fertige
list[TimelineSegment] aus timeline_builder.build_timeline) NACHTRÄGLICH in
genau die 6-Layer-AST-Struktur des WE.ED.IT-OIDA-Pitches -- als eigenes,
lesbares Export-/Doku-Artefakt (.director.json neben .edl.json/.genome.json/
.otio, siehe main.py). Es beeinflusst NICHT die Clip-Auswahl oder den
Timeline-Aufbau selbst; ändert sich morgen die interne Berechnung eines
Layers (z.B. wie audio_analysis Struktur erkennt), zieht dieses Modul
automatisch nach, weil es nichts davon selbst neu berechnet.

Die 6 Stufen aus dem Pitch UND ihre reale Datenquelle hier:
  1. Music Compiler   -> audio.structure / audio.bpm            (compile_music_layer)
  2. Emotion Compiler  -> TimelineSegment.target_energy/theme    (compile_emotion_layer)
  3. Motion Compiler   -> TimelineSegment.motion_score/_direction (compile_motion_layer)
  4. Color Compiler    -> TimelineSegment.color/lighting          (compile_color_layer)
  5. Camera Compiler   -> TimelineSegment.camera/cut_style        (compile_camera_layer)
  6. Shot Compiler     -> die komplette Timeline als Shot-Liste   (compile_shot_layer)
"""
from pathlib import Path
from typing import Any

def _group_by_structure(timeline: list) -> list[list]:
    """Gruppiert aufeinanderfolgende TimelineSegments mit gleichem
    structure_label (Intro/Verse/Hook/Bridge/Breakdown/Outro) zu Blöcken --
    dieselbe Gruppierungsidee wie main.py::_build_timeline_narrative, hier
    aber als eigenständiger Helper, weil alle 6 Layer unten dieselbe
    Blockbildung brauchen und nicht 6x getrennt gruppieren sollen."""
    groups: list[list] = []
    for seg in timeline:
        if groups and seg.structure_label == groups[-1][-1].structure_label:
            groups[-1].append(seg)
        else:
            groups.append([seg])
    return groups


def _most_common(values: list, fallback: str = "-"):
    cleaned = [v for v in values if v]
    return max(set(cleaned), key=cleaned.count) if cleaned else fallback


def _avg(values: list) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0

def compile_music_layer(audio: Any) -> list[dict]:
    """Stufe 1 (Music Compiler): die von audio_analysis erkannte Song-
    Struktur als "musikalische Partitur" -- ein Block pro Intro/Verse/Hook/
    Bridge/Breakdown/Outro mit BPM und Zeitfenster. Ohne echte
    Struktur-Erkennung (audio.structure leer) wird ein einziger Block über
    die gesamte Songdauer zurückgegeben, damit die nachgelagerten Layer
    trotzdem eine (grobe) Blockeinteilung zum Gruppieren haben."""
    if audio.structure:
        return [
            {"label": label, "start_sec": round(start, 3), "end_sec": round(end, 3),
             "bpm": round(audio.bpm, 1)}
            for start, end, label in audio.structure
        ]
    return [{"label": "verse", "start_sec": 0.0, "end_sec": round(audio.duration_sec, 3),
             "bpm": round(audio.bpm, 1)}]


def compile_emotion_layer(timeline: list) -> list[dict]:
    """Stufe 2 (Emotion Compiler): Energie-/Theme-"Kurve" je Struktur-Block,
    aus den von build_timeline() bereits gewählten Segmenten aggregiert
    (NICHT neu berechnet) -- Pendant zum "Emotion Curve"-Mapping aus dem
    Pitch, nur datengetrieben statt handgeschriebener Song-Phase-Tabelle."""
    layer = []
    for group in _group_by_structure(timeline):
        layer.append({
            "structure_label": group[0].structure_label,
            "start_sec": round(group[0].start_sec, 3),
            "end_sec": round(group[-1].end_sec, 3),
            "avg_target_energy": _avg([s.target_energy for s in group]),
            "dominant_theme": _most_common([s.theme for s in group]),
            "dominant_symbol": _most_common([s.semantic_symbol for s in group]),
        })
    return layer

def compile_motion_layer(timeline: list) -> list[dict]:
    """Stufe 3 (Motion Compiler): Bewegungsprofil je Struktur-Block --
    durchschnittlicher motion_score, Netto-Bewegungsrichtung (Summe der
    motion_direction-Vorzeichen, siehe timeline_builder._motion_flow_bonus
    für dieselbe Größe auf Segment-Ebene) und Anteil "harter" Cut-Styles
    (jump_cut/whip) als grober Proxy für die wahrgenommene Schnitthärte."""
    layer = []
    for group in _group_by_structure(timeline):
        directions = [s.motion_direction for s in group]
        net_direction = "right" if sum(directions) > 0 else "left" if sum(directions) < 0 else "neutral"
        hard_cuts = sum(1 for s in group if s.cut_style in ("jump_cut", "whip"))
        layer.append({
            "structure_label": group[0].structure_label,
            "avg_motion_score": _avg([s.motion_score for s in group]),
            "net_motion_direction": net_direction,
            "hard_cut_ratio": round(hard_cuts / len(group), 4),
            "avg_speed_factor": _avg([s.speed_factor for s in group]),
        })
    return layer


def compile_color_layer(timeline: list) -> list[dict]:
    """Stufe 4 (Color Compiler): dominante Farbe/Lichtstimmung je Struktur-
    Block -- Pendant zur "Color-Narrative"-Idee aus dem Pitch, aus den
    bereits von build_intent() gesetzten TimelineSegment.color/.lighting."""
    layer = []
    for group in _group_by_structure(timeline):
        layer.append({
            "structure_label": group[0].structure_label,
            "dominant_color": _most_common([s.color for s in group]),
            "dominant_lighting": _most_common([s.lighting for s in group]),
        })
    return layer

def compile_camera_layer(timeline: list) -> list[dict]:
    """Stufe 5 (Camera Compiler): dominante Kamera-Persona + Cut-Style-
    Verteilung je Struktur-Block, aus TimelineSegment.camera/.cut_style
    (main.py::_calculate_cut_style)."""
    layer = []
    for group in _group_by_structure(timeline):
        style_counts: dict[str, int] = {}
        for s in group:
            style_counts[s.cut_style] = style_counts.get(s.cut_style, 0) + 1
        layer.append({
            "structure_label": group[0].structure_label,
            "dominant_camera": _most_common([s.camera for s in group]),
            "cut_style_distribution": style_counts,
        })
    return layer


def compile_shot_layer(timeline: list) -> list[dict]:
    """Stufe 6 (Shot Compiler): die eigentliche Shot-Liste -- kombiniert
    alle vorherigen Layer implizit, weil es einfach die fertige, bereits von
    build_timeline() aufgelöste Segmentfolge ist. Entspricht dem "RenderAST"
    aus dem Pitch, nur ohne eigene AST-Klassen: main.py::_build_render_script
    liefert dieselbe Information bereits ausführlicher (inkl. Semantik-Match/
    WONG-Vergleich) -- diese Funktion reduziert bewusst auf die für die
    6-Layer-Doku relevanten Felder, statt render_script zu duplizieren."""
    return [{
        "index": i,
        "start_sec": round(seg.start_sec, 3),
        "end_sec": round(seg.end_sec, 3),
        "clip": seg.clip_path,
        "camera": seg.camera,
        "cut_style": seg.cut_style,
        "theme": seg.theme,
    } for i, seg in enumerate(timeline)]

def compile_director_stack(audio: Any, timeline: list, song_path: str,
                           project_name: str | None = None) -> dict:
    """Baut das komplette 6-Layer-"Director Compiler Stack"-Dokument. Reines
    Reporting-/Export-Artefakt (siehe Modul-Docstring) -- wird von
    main.py::_finalize_song_artifacts als output_path.with_suffix(
    '.director.json') geschrieben, analog zu .genome.json/.strategy.json.
    Ein Fehler hier darf (wie bei den anderen Post-Render-Artefakten) nie
    den Render selbst zum Absturz bringen -- main.py fängt das entsprechend
    in einem eigenen try/except ab."""
    if not timeline:
        raise ValueError("Leere Timeline: kein Director-Compiler-Export möglich.")
    return {
        "version": "director-compiler-stack-v1",
        "project": project_name or Path(song_path).stem,
        "source_audio": song_path,
        "music": compile_music_layer(audio),
        "emotion": compile_emotion_layer(timeline),
        "motion": compile_motion_layer(timeline),
        "color": compile_color_layer(timeline),
        "camera": compile_camera_layer(timeline),
        "shots": compile_shot_layer(timeline),
    }
