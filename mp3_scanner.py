"""
mp3_scanner.py — findet MP3s in FAVs (rekursiv), liest mp3tag-Metadaten
(Genre/Mood/Comment/Artist) und baut daraus einen einfachen, offline
berechenbaren Tag-Vektor (Bag-of-Keywords über TAG_VOCAB).

Kein Embedding-Modell nötig -> 100% offline, deterministisch, schnell.
Nutzt optional alle_songs_extrahiert.csv als Fast-Path, wenn vorhanden
und aktueller als die mp3-Datei (spart erneutes Tag-Parsing).
"""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from config import MP3_ROOTS, SONGS_CSV, TAG_VOCAB

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None  # Skript bleibt lauffähig, warnt aber beim Scan


@dataclass
class SongInfo:
    path: str
    title: str = ""
    artist: str = ""
    genre: str = ""
    mood: str = ""
    comment: str = ""
    lyrics: str = ""               # aus CSV-Spalte "Lyrics" oder ID3 USLT-Frame -- eigentliche
                                    # TAG_VOCAB-Trefferquelle bei Suno-Songs, wo Genre/Mood leer sind
    bpm_tag: float = 0.0          # BPM falls in mp3tag hinterlegt (0 = unbekannt, wird per Audioanalyse ersetzt)
    tag_vector: list = field(default_factory=list)


IGNORED_DIR_NAMES = {
    "stems", "16zu9", "9zu16", "__pycache__",
}
STEM_NAME_PATTERNS = ("__vocals", "__drums", "__bass", "__other")


def is_valid_song_path(path: str | Path) -> bool:
    """Prüft, ob ein Audio-Pfad ein echter Song ist (kein erzeugter Stem, kein Output-Ordner)."""
    p = Path(path)
    for part in p.parts[:-1]:
        part_lower = part.lower()
        if part_lower in IGNORED_DIR_NAMES or "stems" in part_lower:
            return False
        if part_lower.startswith("_demucs_tmp") or part_lower.startswith("."):
            return False

    stem_name = p.stem.lower()
    if stem_name.startswith((".", "_")):
        return False
    for pat in STEM_NAME_PATTERNS:
        if stem_name.endswith(pat) or f"{pat}__" in stem_name:
            return False
    if "_beatsync" in stem_name:
        return False
    return True


def find_mp3_files(extra_roots: list | None = None) -> list:
    """Rekursiver Scan aller konfigurierten MP3-Quellordner (config.MP3_ROOTS)
    nach *.mp3, optional erweitert um extra_roots (z.B. per main.py
    --mp3-root, mehrfach angebbar). Mehrere/überlappende Ordner werden
    dedupliziert; ein einzelner fehlender Ordner bricht den Scan nicht ab
    (Warnung + überspringen), solange mindestens einer existiert.
    Ignoriert automatisch stems/, 16zu9/, 9zu16/ und Stem-Dateien."""
    roots = list(MP3_ROOTS) + list(extra_roots or [])
    if not roots:
        raise ValueError("Keine MP3-Quellordner konfiguriert (MP3_ROOTS/--mp3-root leer).")
    seen_dirs = set()
    found = set()
    any_existing = False
    for root_str in roots:
        root = Path(root_str)
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        if not root.exists():
            print(f"[mp3_scanner] Warnung: MP3-Quelle nicht gefunden, übersprungen: {root}")
            continue
        any_existing = True
        for ext in ("*.mp3", "*.m4a", "*.wav"):
            for p in root.rglob(ext):
                if is_valid_song_path(p):
                    found.add(str(p))
    if not any_existing:
        raise FileNotFoundError(f"Keine der konfigurierten MP3-Quellen existiert: {roots}")
    return sorted(found)


def _read_tags_mutagen(path: str) -> SongInfo:
    info = SongInfo(path=path)
    if MutagenFile is None:
        return info
    try:
        audio = MutagenFile(path, easy=True)
        if audio is None:
            return info
        info.title   = (audio.get("title")   or [""])[0]
        info.artist  = (audio.get("artist")  or [""])[0]
        info.genre   = (audio.get("genre")   or [""])[0]
        # "mood" ist kein Standard-EasyID3-Feld -> über raw Frame versuchen
        info.comment = (audio.get("comment") or [""])[0] if "comment" in audio else ""
        bpm_field = audio.get("bpm")
        if bpm_field:
            try:
                info.bpm_tag = float(bpm_field[0])
            except ValueError:
                pass
    except Exception as e:
        print(f"[mp3_scanner] Warnung: Tags konnten nicht gelesen werden ({path}): {e}")
        return info
    # Lyrics stehen NICHT im easy=True-Mapping (kein Standard-EasyID3-Feld) --
    # zweiter Pass über die rohen ID3-Frames (USLT = "Unsynchronised Lyrics").
    # Nur relevant für Songs OHNE CSV-Fast-Path-Treffer (siehe scan_all_songs);
    # bei denen war song.tag_vector bisher mangels Genre/Mood/Comment-Inhalt
    # praktisch immer ein Nullvektor (siehe semantic_matching.py-Bugfix).
    try:
        raw = MutagenFile(path, easy=False)
        if raw is not None:
            for key, frame in raw.tags.items() if raw.tags else []:
                if key.startswith("USLT"):
                    text = getattr(frame, "text", None)
                    if text:
                        info.lyrics = text
                        break
    except Exception as e:
        print(f"[mp3_scanner] Warnung: Lyrics-Frame konnte nicht gelesen werden ({path}): {e}")
    return info


def _normalize_path_tail(path: str) -> str:
    """Vergleichbare Form eines Pfads OHNE Laufwerksbuchstaben (z.B. 'F:\\' vs
    'J:\\' bei Ordner-Umzügen/Reorganisationen), lowercase, einheitliche
    Slashes. Wird für den Fast-Path-Abgleich genutzt, da die CSV teils noch
    alte Laufwerksbuchstaben/Ordnerstrukturen enthält."""
    p = path.replace("\\", "/").lower()
    if len(p) > 1 and p[1] == ":":
        p = p[2:]
    return p.lstrip("/")


def _load_csv_index() -> tuple[dict, dict]:
    """alle_songs_extrahiert.csv als Fast-Path-Index.

    Liefert zwei Indizes:
      - by_path: normalisierter Pfad (ohne Laufwerksbuchstabe) -> CSV-Zeile
      - by_unique_name: Dateiname -> CSV-Zeile, NUR für Dateinamen, die in der
        gesamten CSV eindeutig sind (viele Songs liegen mehrfach unter
        identischem Dateinamen in verschiedenen Mood-/Genre-Ordnern -> bei
        Mehrdeutigkeit lieber kein Fast-Path-Treffer als eine falsche Zeile).
    """
    if not SONGS_CSV.exists():
        return {}, {}
    by_path: dict = {}
    name_counts: dict = {}
    rows_by_name: dict = {}
    with open(SONGS_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            file_path = row.get("File Path") or row.get("file_path") or row.get("path")
            file_name = row.get("File Name") or row.get("file_name")
            if file_path:
                by_path[_normalize_path_tail(file_path)] = row
            if file_name:
                name_counts[file_name] = name_counts.get(file_name, 0) + 1
                rows_by_name[file_name] = row
    by_unique_name = {name: row for name, row in rows_by_name.items()
                      if name_counts.get(name, 0) == 1}
    return by_path, by_unique_name


def build_tag_vector(text_fields: list) -> list:
    """
    Einfache Bag-of-Keywords-Vektorisierung über TAG_VOCAB.
    Nutzt C++ Native Tokenizer & Vectorizer Engine (cxx_accel) für maximale
    Ausführungsgeschwindigkeit mit Regex-Fallback.
    """
    blob = " ".join(f for f in text_fields if f)
    if not blob:
        return [0.0] * len(TAG_VOCAB)
    try:
        from cxx_accel import get_cxx_engine
        return get_cxx_engine().build_tag_vector(blob, dim=len(TAG_VOCAB))
    except Exception:
        blob_low = blob.lower()
        vec = []
        for kw in TAG_VOCAB:
            vec.append(1.0 if re.search(rf"\b{re.escape(kw)}\b", blob_low) else 0.0)
        return vec



def extract_song_meta(path: str | Path) -> dict:
    """Extrahiert Titel, Artist, Lyrics, Genre, Mood und Tags für einen einzelnen Song."""
    p_str = str(path)
    try:
        by_path, by_unique_name = _load_csv_index()
    except Exception:
        by_path, by_unique_name = {}, {}
    row = by_path.get(_normalize_path_tail(p_str)) or by_unique_name.get(Path(p_str).name)
    if row is not None:
        title = row.get("Title", "") or Path(p_str).stem
        artist = row.get("Artist", "")
        genre = row.get("Genre", "")
        mood = row.get("Mood", "")
        comment = row.get("Comment", "")
        lyrics = row.get("Lyrics", "")
        bpm_tag = float(row.get("BPM", 0) or 0)
    else:
        info = _read_tags_mutagen(p_str)
        title = info.title or Path(p_str).stem
        artist = info.artist
        genre = info.genre
        mood = info.mood
        comment = info.comment
        lyrics = info.lyrics
        bpm_tag = info.bpm_tag

    fields = [genre, mood, comment, title, lyrics]
    tags = [f.lower() for f in re.findall(r"[a-zA-Z0-9äöüÄÖÜß]+", " ".join(fields)) if len(f) > 2]
    return {
        "path": p_str,
        "title": title,
        "artist": artist,
        "genre": genre,
        "mood": mood,
        "comment": comment,
        "lyrics": lyrics,
        "bpm_tag": bpm_tag,
        "tags": sorted(set(tags)),
    }


def scan_all_songs(extra_roots: list | None = None) -> list:
    """Gibt Liste von SongInfo für alle gefundenen mp3s zurück, Tag-Vektor inklusive."""
    by_path, by_unique_name = _load_csv_index()
    songs = []
    for path in find_mp3_files(extra_roots):
        row = by_path.get(_normalize_path_tail(path)) or by_unique_name.get(Path(path).name)
        if row is not None:
            info = SongInfo(
                path=path,
                title=row.get("Title", ""),
                artist=row.get("Artist", ""),
                genre=row.get("Genre", ""),
                mood=row.get("Mood", ""),
                comment=row.get("Comment", ""),
                lyrics=row.get("Lyrics", ""),
                bpm_tag=float(row.get("BPM", 0) or 0),
            )
        else:
            info = _read_tags_mutagen(path)
        info.tag_vector = build_tag_vector(
            [info.genre, info.mood, info.comment, info.title, info.lyrics]
        )
        songs.append(info)
    return songs

