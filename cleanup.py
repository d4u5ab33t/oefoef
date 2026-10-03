"""
cleanup.py — Housekeeping für tmp/-Arbeitsverzeichnisse.

renderer.py legt pro Render ein Arbeitsverzeichnis unter TMP_DIR an
(TMP_DIR / <output_stem>, siehe render_music_video) und räumt es am Ende
eines ERFOLGREICHEN Renders selbst wieder weg. Bricht ein Render vorzeitig
ab — Exception, Timeout, Ctrl+C, harter Absturz, Kill — blieb dieses
Arbeitsverzeichnis bisher für immer liegen (siehe UPGRADE.md v1.0.1: 218 +
429 verwaiste seg_*.mp4-Dateien wurden genau so gefunden).

Dieses Modul räumt gezielt NUR erkennbare Render-Arbeitsverzeichnisse auf —
erkannt an ihrer eindeutigen Signatur (concat_list.txt, video_only.mp4 oder
seg_NNNNN.mp4-Dateien, exakt wie renderer.py sie erzeugt). Alles andere unter
tmp/ (z.B. manuell abgelegte Test-/Scratch-Dateien wie tmp/pidada/,
tmp/database.csv) bleibt unberührt.
"""
import shutil
import time
from pathlib import Path
from typing import Callable, Optional

from config import TMP_DIR

# Dateien/Muster, die ein renderer.py-Arbeitsverzeichnis eindeutig
# kennzeichnen. Nur Ordner mit mindestens einem Treffer werden angefasst.
_RENDER_WORKDIR_SIGNATURE_FILES = ("concat_list.txt", "video_only.mp4")
_RENDER_WORKDIR_SIGNATURE_GLOB = "seg_*.mp4"


def _is_render_workdir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if any((path / name).exists() for name in _RENDER_WORKDIR_SIGNATURE_FILES):
        return True
    try:
        next(path.glob(_RENDER_WORKDIR_SIGNATURE_GLOB))
        return True
    except StopIteration:
        return False


def cleanup_stale_render_dirs(tmp_dir: Path = TMP_DIR, min_age_sec: float = 0,
                               log: Optional[Callable[[str], None]] = None) -> int:
    """Entfernt verwaiste renderer.py-Arbeitsverzeichnisse unterhalb von
    tmp_dir. Wird von main.py einmal vor dem Verarbeitungslauf aufgerufen —
    zu diesem Zeitpunkt kann kein eigenes work_dir mehr aktiv sein, daher ist
    min_age_sec=0 (sofort) der sichere Standard für diesen Aufrufkontext.
    Ein größerer Wert eignet sich, falls das Cleanup mal parallel zu einem
    laufenden Render aus einem anderen Prozess aufgerufen werden soll.

    Gibt die Anzahl entfernter Verzeichnisse zurück.
    """
    def _log(msg: str):
        if log:
            log(msg)
        else:
            print(msg, flush=True)

    if not tmp_dir.is_dir():
        return 0

    removed = 0
    now = time.time()
    for entry in sorted(tmp_dir.iterdir()):
        if not _is_render_workdir(entry):
            continue
        try:
            age = now - entry.stat().st_mtime
        except OSError:
            continue
        if age < min_age_sec:
            continue
        try:
            size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
            shutil.rmtree(entry)
            removed += 1
            _log(f"[cleanup] Verwaistes Render-Arbeitsverzeichnis entfernt: "
                 f"{entry.name} ({size / (1024 * 1024):.1f} MB)")
        except Exception as e:
            _log(f"[cleanup] Konnte {entry} nicht entfernen: {e}")
    return removed


if __name__ == "__main__":
    # Manuell ausführbar: `python cleanup.py` räumt tmp/ auf, ohne main.py
    # zu starten.
    n = cleanup_stale_render_dirs()
    print(f"[cleanup] Fertig: {n} verwaiste(s) Arbeitsverzeichnis(se) entfernt.", flush=True)
