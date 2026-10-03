"""
clip_pool.py — analysiert den ClipPool (_raw_reorga__) einmalig und cached
das Ergebnis in libsync-flat-globe.db.json. Läuft komplett offline:

  - ffprobe für die Cliplänge (einziger externer Prozess, sehr schnell)
  - Tags aus Ordner-/Dateinamen (dein Pool ist vermutlich thematisch sortiert,
    z.B. .../nature/forest_walk.mp4 -> Tag "nature")
  - Motion- UND Face-Score aus DENSELBEN gesampleten Frames (ein einziger
    OpenCV-Decode-Pass mit fester Sample-Anzahl statt vollem Video-Decode
    -> Kosten pro Clip sind unabhängig von der Cliplänge, entscheidend bei
    zehntausenden Clips)

Ergebnis pro Clip landet im flat globe cache und wird bei erneutem Lauf nur
neu berechnet, wenn sich mtime/größe der Datei geändert hat.

v5 zusätzlich:
  - "ocr": Text-in-Frame-Erkennung via Tesseract (optional, siehe
    _ocr_text_from_frames -> ohne installiertes Tesseract bleibt es [])
  - "learned": laufende Statistik aus dem Render-Feedback (siehe
    update_learned_from_render()) -> "description" bekommt automatisch einen
    "| learned: …" Suffix, sobald ein Clip mind. einmal gerendert wurde.
    Dadurch nähern sich Clip-Beschreibung und Render-Erfahrung über die Zeit
    gegenseitig an, statt zwei getrennte, statische Datentöpfe zu bleiben.
"""
import hashlib
import json
import os
import re
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from config import (CLIP_POOL_DIR, CLIP_POOL_SUBDIRS, FFPROBE_BIN, HAAR_CASCADE_PATH,
                    STILL_FRAME_SCORE_MAX, TAG_VOCAB)
from creative_genome import information_density
from mp3_scanner import build_tag_vector
from clip_highlight import (score_clip_pair, select_clip_duration,
                            get_clip_highlight_score as _calc_highlight_score)

try:
    import cv2
except ImportError:
    cv2 = None

# Optional: Text-in-Frame-Erkennung für "ocr" (siehe _ocr_text_from_frames).
# Braucht zusätzlich zum pip-Paket die Tesseract-OCR-Engine als System-Binary
# (https://github.com/UB-Mannheim/tesseract/wiki für Windows) -> ohne das
# bleibt "ocr" einfach [], das Skript läuft trotzdem normal weiter.
try:
    import pytesseract
except ImportError:
    pytesseract = None

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
# v4: + motion_direction (horizontale Bewegungsrichtung, siehe _motion_direction_from_frames)
# v5: + ocr (Text-in-Frame via Tesseract, optional) + learned (Render-Feedback-Loop,
#     siehe update_learned_from_render() -- wird bei Reanalyse NICHT überschrieben)
# v6: + Content-Tags direkt in "description" (statt rein technischer Kamera-/
#     Qualitätsdaten) + erweitertes TAG_VOCAB (Oidaheim/Hip-Hop-Attitude, siehe
#     config.py) -- Bump erzwingt Reanalyse, damit bereits gecachte Clips die
#     neuen Vokabel-Treffer TATSÄCHLICH in Tags/Vektor/Description bekommen.
# HINWEIS: Weed/420-Vokabular wurde zu config.TAG_VOCAB hinzugefügt, OHNE
# ANALYSIS_VERSION zu bumpen (bewusst zurückgenommen -- ein Bump hätte bei
# der nächsten Ausführung eine komplette Reanalyse ALLER gecachten Clips
# erzwungen, unabhängig von --rebuild-globe, und damit einen frisch fertig-
# gestellten mehrstündigen Scan zunichtegemacht). Die neuen Begriffe greifen
# dadurch vorerst nur bei neu hinzukommenden/geänderten Clips; bereits
# gecachte Clips bekommen sie erst bei einem SPÄTEREN, bewusst ausgelösten
# Reanalyse-Lauf (Version manuell hochzählen, wenn das gewünscht ist).
ANALYSIS_VERSION = 6


def _has_cv2_api(*names: str) -> bool:
    return cv2 is not None and all(hasattr(cv2, name) for name in names)


def find_clips(subdirs: list | None = None) -> list:
    """Findet alle Video-Clips im Pool. Wenn `subdirs` (oder mangels expliziter
    Angabe die Config CLIP_POOL_SUBDIRS) gesetzt ist, wird NUR in diesen
    Unterordnern gesucht (z.B. nur "subdir1","subdir2" statt des kompletten
    Pools) — praktisch, um den Analyse-Lauf gezielt auf frisch hinzugefügte
    Ordner zu begrenzen. Leer/nicht gesetzt -> kompletter Pool wie bisher."""
    if not CLIP_POOL_DIR.exists():
        raise FileNotFoundError(f"ClipPool nicht gefunden: {CLIP_POOL_DIR}")
    active = subdirs if subdirs else CLIP_POOL_SUBDIRS
    dirs_to_scan = [CLIP_POOL_DIR / sub for sub in active] if active else [CLIP_POOL_DIR]
    clips = []
    for d in dirs_to_scan:
        if not d.exists():
            print(f"[clip_pool] Warnung: ClipPool-Subdir nicht gefunden, übersprungen: {d}")
            continue
        for root, _, files in os.walk(d):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in VIDEO_EXTS:
                    clips.append(os.path.join(root, f))
    return sorted(set(clips))


def filter_globe_to_subdirs(globe: dict, subdirs: list | None = None) -> dict:
    """Schränkt einen bereits geladenen Globe-Cache auf bestimmte ClipPool-
    Unterordner ein (z.B. nur "subdir1","subdir2"), UNABHÄNGIG davon, ob diese
    gerade neu analysiert wurden — der Cache kann ja noch Einträge aus früheren
    vollständigen Scans enthalten. Leer/nicht gesetzt (weder Argument noch
    Config CLIP_POOL_SUBDIRS) -> Globe unverändert (kompletter Pool).

    Wird von main.py genutzt, um EINEN Render gezielt auf einen Teil des Pools
    zu begrenzen, ohne den restlichen Cache auf der Platte zu verlieren oder
    neu bauen zu müssen — die volle globe bleibt der on-disk-Wahrheitsstand,
    nur die für DIESEN Render genutzte Kandidatenliste wird eingeschränkt."""
    active = subdirs if subdirs else CLIP_POOL_SUBDIRS
    if not active:
        return globe
    prefixes = []
    for sub in active:
        sub_dir = CLIP_POOL_DIR / sub
        try:
            prefixes.append(str(sub_dir.resolve()))
        except OSError:
            prefixes.append(str(sub_dir))
    filtered = {}
    for path, meta in globe.items():
        try:
            resolved = str(Path(path).resolve())
        except OSError:
            resolved = path
        if any(resolved == p or resolved.startswith(p + "\\") or resolved.startswith(p + "/")
               for p in prefixes):
            filtered[path] = meta
    return filtered


def _file_fingerprint(path: Path) -> str:
    """Schnelles Fingerprint über Größe+mtime statt vollem Hash (Performance
    bei tausenden Clips) -> reicht um Cache-Invalidierung zu erkennen."""
    st = path.stat()
    return hashlib.md5(f"{st.st_size}-{st.st_mtime}".encode()).hexdigest()


_FEMALE_GENDER_TERMS = frozenset({
    # English
    "female", "woman", "women", "girl", "girls", "lady", "ladies", "chick",
    "chicks", "queen", "queens", "singer_f", "model_f", "bitch", "bitches",
    "she", "her", "miss", "babe", "babes",
    # German / Bavarian
    "frau", "frauen", "rapperin", "saengerin", "sängerin", "weiblich",
    "maedchen", "mädchen", "dirndl", "braut", "chaya", "dame", "oide",
    "maderl", "sie",
    # Spanish / Latino
    "chica", "chicas", "mujer", "mujeres", "niña", "niñas", "reina", "mami",
    "dama", "ella",
    # French
    "femme", "femmes", "fille", "filles", "reine", "elle", "rappeuse",
    "chanteuse",
    # Italian
    "donna", "donne", "ragazza", "ragazze", "regina", "signora", "lei",
    # Russian / Slavic
    "девушка", "женщина", "девочка", "она", "рэперша", "певица",
})

_MALE_GENDER_TERMS = frozenset({
    # English
    "male", "man", "men", "boy", "boys", "guy", "guys", "dude", "dudes",
    "bro", "bros", "king", "kings", "singer_m", "model_m", "he", "him",
    "mister", "sir", "boyz",
    # German / Bavarian
    "mann", "männer", "maenner", "bruder", "brueder", "rapper", "saenger",
    "sänger", "maennlich", "männlich", "knabe", "kerl", "kerle", "haberer",
    "bazi", "oida", "er", "ihn", "brudi",
    # Spanish / Latino
    "chico", "chicos", "hombre", "hombres", "niño", "niños", "rey", "papi",
    "caballero", "él", "el", "hermano", "tio",
    # French
    "homme", "hommes", "garçon", "garcon", "garcons", "roi", "mec", "mecs",
    "il", "frère", "frere", "gars", "rappeur", "chanteur",
    # Italian
    "uomo", "uomini", "ragazzo", "ragazzi", "re", "signore", "lui", "fratello",
    # Russian / Slavic
    "парень", "мужчина", "мальчик", "он", "братан", "рэпер", "певец",
})


def _ffprobe_clip_info(path: str) -> tuple[float, int, int]:
    """Liest Dauer + Dimensionen (Breite, Höhe) in einem einzigen ffprobe-Aufruf."""
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "format=duration:stream=width,height",
             "-of", "json", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, stdin=subprocess.DEVNULL,
        )
        data = json.loads(out.stdout)
        dur = float(data.get("format", {}).get("duration") or 0.0)
        streams = data.get("streams", [])
        w = int(streams[0].get("width", 0)) if streams else 0
        h = int(streams[0].get("height", 0)) if streams else 0
        return dur, w, h
    except Exception:
        return 0.0, 0, 0


def _ffprobe_duration(path: str) -> float:
    dur, _, _ = _ffprobe_clip_info(path)
    return dur


def _tags_from_path(path: str) -> list:
    """Nutzt Ordner- und Dateinamen als semantische Tags, gematcht gegen TAG_VOCAB
    plus die reinen Ordnernamen und Token-Bestandteile selbst."""
    p = Path(path)
    try:
        rel_parts = list(p.relative_to(CLIP_POOL_DIR).parts[:-1])
    except ValueError:
        rel_parts = [p.parent.name] if p.parent else []
    tokens = [t.lower() for t in re.split(r"[_\-\s\.\(\)\[\]\+]+", p.stem) if len(t) > 1]
    all_parts = [p.stem] + rel_parts + tokens
    blob = " ".join(all_parts).lower().replace("_", " ").replace("-", " ")
    matched_vocab = [kw for kw in TAG_VOCAB if re.search(rf"\b{re.escape(kw)}\b", blob)]
    folder_tags = [seg.lower() for seg in all_parts if len(seg) > 2]
    return sorted(set(matched_vocab + folder_tags))


def _gender_vector(tags: list, path: str | None = None) -> dict:
    values = set(t.lower() for t in tags)
    if path:
        values.update(t.lower() for t in re.findall(r"[a-zA-ZäöüÄÖÜß]+", path))
    female_hits = sorted(values & _FEMALE_GENDER_TERMS)
    male_hits = sorted(values & _MALE_GENDER_TERMS)
    return {
        "female": female_hits,
        "male": male_hits,
        "unknown": not bool(female_hits or male_hits),
    }


_SPITTING_MC_TERMS = frozenset({
    "spit", "spitting", "rapper", "rapping", "bars", "flow", "rhyme", "rhymes",
    "freestyle", "mic", "microphone", "mc", "vocal", "vocals", "singer", "singing",
    "lip_sync", "lipsync", "performance", "rap", "stage", "close_up", "portrait",
    "headshot", "mouth", "facetime", "rapstar", "session", "studio"
})


def _spitting_score(tags: list, face_score: float, motion_score: float, path: str | None = None) -> float:
    """Berechnet einen Score (0..1) wie gut sich der Clip als Lip-Sync MC Rapper Performance-Shot
    (spitting bars / Gesang / Mikrofon / Nahaufnahme) eignet."""
    values = set(t.lower() for t in tags)
    if path:
        values.update(t.lower() for t in re.findall(r"[a-zA-ZäöüÄÖÜß0-9]+", path))

    hits = len(values & _SPITTING_MC_TERMS)
    tag_factor = min(1.0, hits * 0.35)

    face_factor = min(1.0, face_score * 1.2) if face_score > 0 else 0.0
    motion_factor = 1.0 - abs(0.5 - motion_score)

    if tag_factor > 0 and face_factor > 0:
        base = 0.45 * tag_factor + 0.40 * face_factor + 0.15 * motion_factor
        return round(min(1.0, base + 0.20), 3)
    elif face_factor > 0.4:
        return round(0.30 * tag_factor + 0.50 * face_factor + 0.20 * motion_factor, 3)
    elif tag_factor > 0:
        return round(0.50 * tag_factor + 0.50 * motion_factor * 0.5, 3)

    return 0.0


def get_clip_spitting_score(meta: dict) -> float:
    """Liefert den LibSync Spitting/Performance-Score eines Clips, mit Rückwärtskompatibilität."""
    if not meta or not isinstance(meta, dict):
        return 0.0
    if "spitting_score" in meta:
        return float(meta["spitting_score"] or 0.0)
    tags = meta.get("tags") or []
    face_score = float(meta.get("face_score", 0.0))
    motion_score = float(meta.get("motion_score", 0.5))
    path = meta.get("path") or ""
    return _spitting_score(tags, face_score, motion_score, path=path)


_DJ_ACTION_TERMS = frozenset({
    "dj", "turntable", "turntables", "vinyl", "mixer", "crossfader", "jogwheel", "deck", "decks",
    "pioneer", "technics", "club_dj", "headphones", "scratch", "scratching", "hands_on_vinyl",
    "drop_the_beat", "slipmat", "serato", "traktor", "plattenspieler", "soundclash", "club",
    "party", "rave", "stage", "performance"
})


def _dj_action_score(tags: list, motion_score: float, face_score: float, path: str | None = None) -> float:
    """Berechnet einen Score (0..1) wie gut sich der Clip für DJ Sync Actions
    (Scratching, Turntables, Mixer, Drop-Gesten, Club-Performance) eignet."""
    values = set(t.lower() for t in tags)
    if path:
        values.update(t.lower() for t in re.findall(r"[a-zA-ZäöüÄÖÜß0-9]+", path))

    hits = len(values & _DJ_ACTION_TERMS)
    tag_factor = min(1.0, hits * 0.35)
    motion_factor = 1.0 - abs(0.5 - motion_score)

    if tag_factor > 0:
        base = 0.60 * tag_factor + 0.25 * motion_factor + 0.15 * min(1.0, face_score * 1.5)
        return round(min(1.0, base + 0.20), 3)
    elif "scratch" in values or "vinyl" in values or "turntable" in values:
        return 0.85
    return 0.0


def get_clip_dj_action_score(meta: dict) -> float:
    """Liefert den DJ Sync Action Score eines Clips."""
    if not meta or not isinstance(meta, dict):
        return 0.0
    if "dj_action_score" in meta:
        return float(meta["dj_action_score"] or 0.0)
    tags = meta.get("tags") or []
    face_score = float(meta.get("face_score", 0.0))
    motion_score = float(meta.get("motion_score", 0.5))
    path = meta.get("path") or ""
    return _dj_action_score(tags, motion_score, face_score, path=path)


def get_clip_highlight_score(meta: dict) -> float:
    """Liefert den Dual-Frame Highlight Score eines Clips."""
    return _calc_highlight_score(meta)


def _motion_score_from_frames(frames: list) -> float:
    """Grober Motion-Proxy aus bereits gelesenen Sample-Frames: mittlere
    normalisierte Grauwert-Differenz zwischen aufeinanderfolgenden Samples.
    Ersetzt den früheren vollen ffmpeg-Scene-Filter-Decode (der bei 32k Clips
    schlicht zu langsam war) durch eine Wiederverwendung der Frames, die für
    die Face-Detection ohnehin schon gelesen werden -> nur EIN Decode-Pass
    pro Clip statt zwei."""
    if len(frames) < 2:
        return 0.0
    diffs = []
    prev = None
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if cv2 is not None else None
        if gray is None:
            return 0.0
        small = cv2.resize(gray, (64, 36))  # winzig -> Diff ist praktisch kostenlos
        if prev is not None:
            diff = np.mean(np.abs(small.astype(np.int16) - prev.astype(np.int16))) / 255.0
            diffs.append(diff)
        prev = small
    return float(min(1.0, np.mean(diffs) * 4)) if diffs else 0.0  # *4: sinnvoll auf 0..1 spreizen


def _motion_direction_from_frames(frames: list) -> float:
    """Grobe horizontale Bewegungsrichtung als Wert in [-1, 1], via Phasen-
    korrelation zwischen den ohnehin für Motion-/Face-Score gelesenen Sample-
    Frames (kein zusätzlicher Decode-Pass). Negativ = Bildinhalt driftet über
    den Clip hinweg nach LINKS, positiv = nach RECHTS, ~0 = keine klare
    horizontale Tendenz (z.B. statischer Clip oder reine Vertikalbewegung).

    Wird in renderer.py genutzt, um den Push/Fade-Übergang am Segmentende NUR
    dann auszulösen, wenn es eine tatsächliche, eindeutige Bewegungsrichtung
    im Bild gibt (statt wie zuvor zufällig links/rechts zu würfeln) — und um
    die Push-Richtung so zu wählen, dass sie die im Bild bereits sichtbare
    Bewegung fortsetzt (z.B. MC läuft/schwenkt nach links -> Bild schupst und
    fadet ebenfalls nach links aus)."""
    if len(frames) < 3 or not _has_cv2_api("phaseCorrelate", "cvtColor", "resize"):
        return 0.0
    shifts = []
    prev = None
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (64, 36)).astype(np.float32)
        if prev is not None:
            try:
                (dx, _dy), _response = cv2.phaseCorrelate(prev, small)
                shifts.append(dx)
            except cv2.error:
                pass
        prev = small
    if not shifts:
        return 0.0
    mean_shift = float(np.mean(shifts))
    # Sample-Frames sind 64px breit -> +-6px mittlere Verschiebung zwischen
    # Samples ist bereits eine deutliche, konsistente Drift; grosszügig auf
    # [-1, 1] normalisiert statt hart zu clippen.
    return float(max(-1.0, min(1.0, mean_shift / 6.0)))


_face_cascade = None


def _get_cascade():
    global _face_cascade
    if (
        _face_cascade is None
        and _has_cv2_api("CascadeClassifier")
        and HAAR_CASCADE_PATH.exists()
    ):
        cascade = cv2.CascadeClassifier(str(HAAR_CASCADE_PATH))
        if not cascade.empty():
            _face_cascade = cascade
    return _face_cascade


def _sample_frames(path: str, duration: float, samples: int = 8):
    """Liest `samples` Frames über den Clip in EINEM VideoCapture-Durchlauf.

    Für Dual-Frame Highlight-Analyse (Start/End-Bild-Pools, 6s-Clips):
    - Frame 0 = ECHTER Erstframe (~0.05 s) für composition_score(start)
    - Frame -1 = ECHTER Letzframe (~duration-0.05 s) für composition_score(end)
    - Restliche Frames: uniform verteilt dazwischen für Motion/Face-Scoring
    Diese Garantie ist entscheidend für Clip-Pools, die fast ausschließlich aus
    definierten Start-/Endbildern bestehen (z.B. 6s Showcase-Clips bei 140 BPM).
    """
    if duration <= 0 or not _has_cv2_api("VideoCapture", "CAP_PROP_POS_MSEC"):
        return []
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []

    # Zeitstempel-Sequenz: echter Erstframe, Mittelsegment, echter Letzframe
    first_t = min(0.05, duration * 0.02)   # ~2% oder 50ms
    last_t  = max(duration - 0.05, duration * 0.97)  # ~97% oder 50ms vor Ende

    if samples <= 2:
        timestamps = [first_t, last_t]
    else:
        inner = samples - 2
        timestamps = [first_t] + [
            first_t + (last_t - first_t) * (i + 1) / (inner + 1)
            for i in range(inner)
        ] + [last_t]

    frames = []
    try:
        for t_sec in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t_sec) * 1000)
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
    finally:
        cap.release()
    return frames


def _face_score_from_frames(frames: list) -> float:
    cascade = _get_cascade()
    if cascade is None or not frames:
        return 0.0
    hits = 0
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)
        if len(faces) > 0:
            hits += 1
    return hits / len(frames)


def _frame_quality(frames: list, duration: float) -> tuple[list, float, list]:
    if duration <= 0 or cv2 is None:
        return [], 0.0, [0.0]
    if len(frames) < 2:
        return [], 0.0, [0.0]
    quality = []
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        quality.append((float(np.mean(gray)) / 255.0,
                       float(cv2.Laplacian(gray, cv2.CV_64F).var())))
    bad = []
    for index in range(1, len(frames)):
        previous = cv2.resize(cv2.cvtColor(frames[index - 1], cv2.COLOR_BGR2GRAY), (64, 36))
        current = cv2.resize(cv2.cvtColor(frames[index], cv2.COLOR_BGR2GRAY), (64, 36))
        difference = float(np.mean(np.abs(current.astype(np.int16) - previous.astype(np.int16)))) / 255.0
        brightness, sharpness = quality[index]
        if difference < 0.003 or brightness < 0.015 or sharpness < 4.0:
            bad.append(round(duration * (index + 0.5) / len(frames), 3))
    ranges = [{"start": max(0.0, t - duration / len(frames)),
               "end": min(duration, t + duration / len(frames))} for t in bad]
    starts = [round(duration * (index + 0.5) / len(frames), 3)
              for index, (_, sharpness) in enumerate(quality) if sharpness >= 12.0]
    return ranges, len(bad) / max(1, len(frames) - 1), starts[:4]


def _ocr_text_from_frames(frames: list) -> list:
    """Erkennt Text in den Sample-Frames via Tesseract (optional, siehe
    Import oben). Nutzt nur jeden 2. Sample-Frame (OCR ist vergleichsweise
    teuer), verwirft Kurz-Fragmente/Rauschen (<3 Zeichen) und dedupliziert.
    Ohne installiertes Tesseract liefert das Feld einfach []."""
    if pytesseract is None or not frames or cv2 is None:
        return []
    texts = set()
    for frame in frames[::2]:
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            txt = pytesseract.image_to_string(gray, config="--psm 6").strip()
        except Exception:
            continue
        if len(txt) >= 3:
            texts.add(txt)
    return sorted(texts)


def analyze_clip(path: str) -> dict:
    duration, width, height = _ffprobe_clip_info(path)
    tags = _tags_from_path(path)
    frames = _sample_frames(path, duration, samples=8) if cv2 is not None else []
    motion_score = _motion_score_from_frames(frames)
    motion_direction = _motion_direction_from_frames(frames)
    bad_frame_ranges, still_frame_score, alternative_start_points = _frame_quality(frames, duration)
    face_score = _face_score_from_frames(frames)
    spit_score = _spitting_score(tags, face_score, motion_score, path=path)
    dj_score = _dj_action_score(tags, motion_score, face_score, path=path)

    # Dual-Frame Highlight-Erkennung für Start/Endbilder & 6s-Videos
    start_frame = frames[0] if frames else None
    end_frame = frames[-1] if frames else None
    hl_res = score_clip_pair(start_frame, end_frame, tags=tags)
    hl_score = hl_res["highlight_score"]
    hl_rec = hl_res["recommendation"]
    hl_140bpm = select_clip_duration(hl_score, bpm=140.0, base_clip_duration=duration)

    camera_movement = ("fast" if motion_score > 0.65 else
                       "tracking" if motion_score > 0.2 else "static")
    object_flow = "continuous" if motion_score >= 0.2 and still_frame_score < 0.5 else "broken"
    gender_vector = _gender_vector(tags)
    female_hits = gender_vector.get("female", [])
    male_hits = gender_vector.get("male", [])
    gender_label = "dual" if (female_hits and male_hits) else ("female" if female_hits else ("male" if male_hits else "neutral"))
    aspect_ratio_str = f"{width}:{height}" if (width > 0 and height > 0) else "unknown"
    aspect_ratio_val = round(width / height, 3) if (width > 0 and height > 0) else None

    content_tags = [t for t in tags if t in TAG_VOCAB]
    content_summary = ", ".join(content_tags[:8]) if content_tags else "keine Vokabular-Treffer"
    result = {
        "duration": duration,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio_str,
        "aspect_ratio_float": aspect_ratio_val,
        "gender": gender_label,
        "tags": tags,
        "vector": build_tag_vector(tags),
        "motion_score": motion_score,
        "motion_direction": round(motion_direction, 4),  # -1=driftet links, +1=driftet rechts
        "face_score": face_score,
        "spitting_score": spit_score,
        "is_spitting_performance": bool(spit_score >= 0.40),
        "dj_action_score": dj_score,
        "is_dj_action": bool(dj_score >= 0.45),
        "highlight_score": hl_score,
        "highlight_recommendation": hl_rec,
        "composition_scores": hl_res["composition"],
        "visual_delta": hl_res["delta"],
        "emotion_scores": hl_res["emotion"],
        "emotional_trip": hl_res["emotional_trip"],
        "sync_140bpm": hl_140bpm,
        "camera": "static" if camera_movement == "static" else "handheld",
        "camera_movement": camera_movement,
        "lighting": "lowkey" if "night" in tags or "dark" in tags else "natural",
        "color": "warm" if "sun" in tags or "golden" in tags else "neutral",
        "objects": [tag for tag in tags if tag not in TAG_VOCAB],
        "object_flow": object_flow,
        "gender_vector": gender_vector,
        "alternative_start_points": alternative_start_points or [0.0],
        "bad_frame_ranges": bad_frame_ranges,
        "burned_parts": bad_frame_ranges,
        "still_frame_score": still_frame_score,
        "playback_ok": bool(duration > 0 and len(frames) >= 2 and still_frame_score < STILL_FRAME_SCORE_MAX),
        "description": (f"Content: {content_summary} | {camera_movement} camera; "
                f"object flow {object_flow}; "
                f"highlight {hl_rec} ({hl_score}); "
                f"{len(alternative_start_points)} alternative starts; "
                f"{len(bad_frame_ranges)} quality warnings"),
        "ocr": _ocr_text_from_frames(frames),
        "entropy": motion_score,
        "analysis_version": ANALYSIS_VERSION,
        "learned": {"uses": 0, "avg_reward": 0.0, "last_reward": None,
                    "last_used_at": None, "last_match_reason": None},
    }
    result["information_density"] = information_density(result)
    return result


def build_or_update_globe(globe: dict, log=print, save_every: int = 25,
                           on_progress=None, max_workers: int | None = None) -> dict:
    """Scannt den ClipPool, analysiert neue/geänderte Clips, lässt unveränderte
    Clips im Cache unangetastet.

    PERFORMANCE: analyze_clip() ist pro Clip komplett unabhängig (eigener
    ffprobe-Subprocess + eigener cv2.VideoCapture-Decode) -> läuft über einen
    ProcessPoolExecutor parallel auf allen verfügbaren Kernen statt seriell.
    Bei 32k+ Clips ist das der dominante Laufzeitfaktor; auf einer 8-Kern-
    Maschine bedeutet das grob einen ~6-8x Speedup ggü. der alten seriellen
    for-Schleife. max_workers default: os.cpu_count()-1 (ein Kern bleibt frei
    für I/O/Logging/Hauptprozess), min. 1.

    Abbruchsicher / inkrementell:
      - speichert die globe alle `save_every` neu analysierte Clips auf Platte
        (on_progress-Callback, i.d.R. db.save_flat_globe) statt nur am Ende
      - fängt Fehler pro einzelnem Clip ab, damit ein defekter/gesperrter Clip
        nicht den kompletten Lauf abbricht
      - fängt KeyboardInterrupt/SIGTERM ab, sichert den bisherigen Fortschritt,
        bricht laufende Worker-Prozesse hart ab (statt auf sie zu warten) und
        beendet danach sauber, statt den Cache im Bruchzustand zu lassen oder
        Minuten auf bereits gestartete Clip-Analysen zu warten
      - bereits gecachte Clips (unveränderter fingerprint) werden NIE neu
        analysiert -> "lese nur neue Clips ein"
    """
    clips = find_clips()
    log(f"[clip_pool] {len(clips)} Clips im Pool gefunden.")

    with ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 4) * 4)) as fp_pool:
        fingerprints = dict(zip(clips, fp_pool.map(lambda p: _file_fingerprint(Path(p)), clips)))

    to_process = []
    for path in clips:
        fp = fingerprints[path]
        cached = globe.get(path)
        if (cached and cached.get("fingerprint") == fp
            and cached.get("analysis_version") == ANALYSIS_VERSION
            and not cached.get("failed")):
            continue
        to_process.append((path, fp))

    log(f"[clip_pool] {len(to_process)} neue/geänderte/zuvor fehlgeschlagene Clips zu analysieren "
        f"({len(clips) - len(to_process)} bereits im Cache).")

    changed = False
    if to_process:
        workers = max_workers or max(1, (os.cpu_count() or 4) - 1)
        log(f"[clip_pool] Analysiere mit {workers} parallelen Worker-Prozessen ...")
        processed_since_save = 0
        executor = ProcessPoolExecutor(max_workers=workers)
        try:
            future_to_item = {
                executor.submit(analyze_clip, path): (path, fp) for path, fp in to_process
            }
            for i, future in enumerate(as_completed(future_to_item), 1):
                path, fp = future_to_item[future]
                try:
                    entry = future.result()
                    entry["fingerprint"] = fp
                    entry["failed"] = False
                    old_learned = (globe.get(path) or {}).get("learned")
                    if old_learned and old_learned.get("uses"):
                        entry["learned"] = old_learned
                        entry["description"] = _apply_learned_suffix(
                            entry["description"], old_learned)
                    globe[path] = entry
                except Exception as e:
                    log(f"[clip_pool] FEHLER bei {path}, überspringe Clip: {e}")
                    globe[path] = {"fingerprint": None, "failed": True, "error": str(e)}
                changed = True

                if i % 25 == 0 or i == len(to_process):
                    log(f"[clip_pool] analysiert ({i}/{len(to_process)}): {path}")

                processed_since_save += 1
                if on_progress and processed_since_save >= save_every:
                    on_progress(globe)
                    log(f"[clip_pool] Zwischenstand gesichert ({i}/{len(to_process)}).")
                    processed_since_save = 0

        except KeyboardInterrupt:
            log("[clip_pool] Abbruch durch Benutzer erkannt — breche laufende Worker ab "
                "und sichere Fortschritt ...")
            executor.shutdown(wait=False, cancel_futures=True)
            if on_progress:
                on_progress(globe)
            log("[clip_pool] Fortschritt gesichert. Nächster Lauf setzt hier fort.")
            raise
        except BaseException:
            log("[clip_pool] Unerwarteter Fehler — sichere Fortschritt vor Weiterwurf ...")
            executor.shutdown(wait=False, cancel_futures=True)
            if on_progress:
                on_progress(globe)
            raise
        else:
            executor.shutdown(wait=True)

        if on_progress and processed_since_save > 0:
            on_progress(globe)

    existing = set(clips)
    stale = [p for p in globe if p not in existing]
    for stale_path in stale:
        del globe[stale_path]
    changed = changed or bool(stale)

    if on_progress and changed:
        on_progress(globe)

    return globe


# ── Render-Feedback-Loop (Clip-Beschreibung <-> Render-Erfahrung) ───────────
_LEARNED_SUFFIX_RE = re.compile(r"\s*\|\s*learned:.*$")


def _apply_learned_suffix(description: str, learned: dict) -> str:
    base = _LEARNED_SUFFIX_RE.sub("", description or "")
    uses = learned.get("uses", 0)
    if not uses:
        return base
    reason = learned.get("last_match_reason")
    reason_part = f", zuletzt weil: {reason}" if reason else ""
    return (f"{base} | learned: {uses}x genutzt, "
            f"Ø reward {learned.get('avg_reward', 0.0):.2f}{reason_part}")


def update_learned_from_render(globe: dict, timeline: list, reward: float,
                                save_cb=None, match_reasons: dict | None = None) -> None:
    now = time.time()
    touched = False
    for segment in timeline:
        path = getattr(segment, "clip_path", None)
        entry = globe.get(path) if path else None
        if entry is None:
            continue
        learned = entry.setdefault(
            "learned", {"uses": 0, "avg_reward": 0.0, "last_reward": None,
                        "last_used_at": None, "last_match_reason": None})
        n = learned.get("uses", 0)
        learned["avg_reward"] = round((learned.get("avg_reward", 0.0) * n + reward) / (n + 1), 4)
        learned["uses"] = n + 1
        learned["last_reward"] = round(reward, 4)
        learned["last_used_at"] = now
        if match_reasons and path in match_reasons:
            learned["last_match_reason"] = match_reasons[path]
        entry["description"] = _apply_learned_suffix(entry.get("description", ""), learned)
        touched = True

    if touched and save_cb:
        save_cb(globe)

    # Stetiges Self-Learning & Vektor-Baum Update
    try:
        from vector_tree import get_global_vector_tree
        tree = get_global_vector_tree()
        for segment in timeline:
            path = getattr(segment, "clip_path", None)
            if path:
                tree.reinforce_path(path, reward)
        tree.save_tree()
    except Exception as e:
        print(f"[clip_pool] Vektor-Baum Feedback Warnung: {e}")


def get_or_build_vector_tree(globe: dict, force_rebuild: bool = False):
    """Liefert den Vektor-Baum und baut ihn bei Bedarf aus dem aktuellen Globe-Cache auf."""
    from vector_tree import get_global_vector_tree
    tree = get_global_vector_tree()
    if force_rebuild or len(tree.leaves) == 0:
        tree.build_from_globe(globe, force_rebuild=force_rebuild)
    return tree


# ── LibSync: Flat Globe Health, Validation & Diagnostics ─────────────────────
def libsync_summary(globe: dict) -> dict:
    """Erstellt eine detaillierte LibSync-Zusammenfassung über den aktuellen
    Zustand von libsync-flat-globe.db.json (MC-Gendern, Qualität, Auflösungen)."""
    total = len(globe)
    failed = sum(1 for m in globe.values() if m.get("failed"))
    playback_ok = sum(1 for m in globe.values() if m.get("playback_ok", True) and not m.get("failed"))
    female = sum(1 for m in globe.values() if (m.get("gender") == "female" or bool((m.get("gender_vector") or {}).get("female"))))
    male = sum(1 for m in globe.values() if (m.get("gender") == "male" or bool((m.get("gender_vector") or {}).get("male"))))
    dual = sum(1 for m in globe.values() if (m.get("gender") == "dual" or (bool((m.get("gender_vector") or {}).get("female")) and bool((m.get("gender_vector") or {}).get("male")))))
    neutral = total - (female + male - dual) - failed

    res_counts = {}
    for m in globe.values():
        w, h = m.get("width", 0), m.get("height", 0)
        if w and h:
            key = "16:9" if w > h else ("9:16" if h > w else "1:1")
            res_counts[key] = res_counts.get(key, 0) + 1

    return {
        "total_clips": total,
        "failed_clips": failed,
        "playback_ok_clips": playback_ok,
        "gender_breakdown": {
            "female": female,
            "male": male,
            "dual": dual,
            "neutral_or_unknown": max(0, neutral),
        },
        "aspect_ratios": res_counts,
    }


def libsync_validate_and_repair(globe: dict, log=print) -> tuple[dict, int]:
    """Validiert und repariert Einträge in libsync-flat-globe.db.json (ergänzt
    fehlende Gender-Vektoren, Labels, Vektoren und Information Density)."""
    repaired = 0
    for path, meta in globe.items():
        if meta.get("failed"):
            continue
        changed = False
        tags = meta.get("tags") or []
        if not tags or len(tags) <= 1:
            new_tags = _tags_from_path(path)
            if new_tags != tags:
                meta["tags"] = new_tags
                tags = new_tags
                changed = True

        gv = _gender_vector(tags, path=path)
        if meta.get("gender_vector") != gv:
            meta["gender_vector"] = gv
            changed = True

        female_hits = gv.get("female", [])
        male_hits = gv.get("male", [])
        expected_gender = "dual" if (female_hits and male_hits) else ("female" if female_hits else ("male" if male_hits else "neutral"))
        if meta.get("gender") != expected_gender:
            meta["gender"] = expected_gender
            changed = True
        if "vector" not in meta or not meta["vector"]:
            meta["vector"] = build_tag_vector(tags)
            changed = True
        if "information_density" not in meta or not meta["information_density"]:
            meta["information_density"] = information_density(meta)
            changed = True
        if changed:
            repaired += 1

    log(f"[libsync] {repaired} Einträge im Flat Globe validiert und repariert.")
    return globe, repaired


def prune_dead_clips(globe: dict, on_progress=None, log=print, sync_vector_tree: bool = True) -> tuple[dict, list[str]]:
    """Prüft blitzschnell via parallelem I/O alle Clip-Einträge im Globe-Cache auf reale
    Existenz auf der Festplatte und entfernt tote/gelöschte Einträge atomar."""
    all_paths = list(globe.keys())
    if not all_paths:
        log("[clip_pool] Flat Globe ist leer.")
        return globe, []

    workers = min(32, (os.cpu_count() or 4) * 4)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        exists_flags = list(pool.map(os.path.exists, all_paths))

    dead_paths = [p for p, exists in zip(all_paths, exists_flags) if not exists]
    if dead_paths:
        for p in dead_paths:
            del globe[p]
        log(f"[clip_pool] ⚡ {len(dead_paths)} tote Clip-Einträge identifiziert und entfernt.")
        if on_progress:
            on_progress(globe)
        if sync_vector_tree:
            try:
                from vector_tree import get_global_vector_tree
                tree = get_global_vector_tree()
                tree.build_from_globe(globe, force_rebuild=True)
                log(f"[clip_pool] Hierarchischer Vektor-Baum synchronisiert ({len(globe)} aktive Clips).")
            except Exception as e:
                log(f"[clip_pool] Vektor-Baum Sync Hinweis: {e}")
    else:
        log(f"[clip_pool] ✅ Alle {len(globe)} indizierten Clips existieren auf der Festplatte (0 tote Einträge).")

    return globe, dead_paths


def purge_failed_clips(globe: dict, failed_paths: list[str] | None = None, on_progress=None, log=print, sync_vector_tree: bool = True) -> tuple[dict, list[str]]:
    """Entfernt automatisch fehlerhafte / nicht abspielbare / bei Encode fehlgeschlagene
    Clips aus dem Flat Globe Cache und synchronisiert den Index."""
    if failed_paths is not None:
        to_remove = [p for p in failed_paths if p in globe]
    else:
        to_remove = [p for p, meta in globe.items() if meta.get("failed") or not meta.get("playback_ok", True)]

    if to_remove:
        for p in to_remove:
            if p in globe:
                del globe[p]
        log(f"[clip_pool] 🗑️ {len(to_remove)} fehlerhafte/nicht-abspielbare Clips aus dem Index entfernt.")
        if on_progress:
            on_progress(globe)
        if sync_vector_tree:
            try:
                from vector_tree import get_global_vector_tree
                tree = get_global_vector_tree()
                tree.build_from_globe(globe, force_rebuild=True)
                log(f"[clip_pool] Hierarchischer Vektor-Baum nach Fehlerbereinigung synchronisiert ({len(globe)} aktive Clips).")
            except Exception as e:
                log(f"[clip_pool] Vektor-Baum Sync Hinweis: {e}")
    else:
        log("[clip_pool] ✅ Keine fehlerhaften Clip-Einträge im Cache gefunden.")

    return globe, to_remove


