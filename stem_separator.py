"""
stem_separator.py — trennt das Song-Signal in Stems (Vocals/Drums/Bass/Other),
damit Beat-/Onset-/Stimmlagen-Erkennung auf saubereren Einzelsignalen laufen
kann statt auf dem vollen Mix ("Matching-Verbesserung", siehe audio_analysis.py).

Offline-first, konsistent mit dem Rest des Projekts:
  - Bevorzugt Demucs (torch ist bereits Projekt-Dependency), läuft auch rein
    auf CPU (langsamer, aber ohne GPU-Pflicht).
  - Fällt automatisch auf librosa HPSS (Harmonic/Percussive Source Separation)
    zurück, wenn Demucs nicht installiert ist oder fehlschlägt -> das Feature
    funktioniert IMMER, nur mit geringerer Trennschärfe ohne Demucs.

Stems landen NEBEN der Quelldatei unter <mp3-ordner>/stems/ (flach, mit dem
Songnamen als Präfix, da sich mehrere Songs denselben Ordner teilen) und
werden gecached — ein Song wird nie zweimal getrennt.
"""
import subprocess
from pathlib import Path

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import librosa
except ImportError:
    librosa = None

try:
    import demucs.separate as _demucs_separate
    _HAS_DEMUCS = True
except ImportError:
    _demucs_separate = None
    _HAS_DEMUCS = False

from config import FFMPEG_BIN, STEM_BACKEND, STEM_DIR_NAME, STEM_SEPARATION_ENABLED

DEMUCS_STEMS = ("vocals", "drums", "bass", "other")
HPSS_STEMS = ("vocals", "drums")  # Proxy-Namen: harmonic->vocals, percussive->drums


def is_stem_file(path: str | Path) -> bool:
    """Prüft, ob ein Pfad bereits ein erzeugter Stem ist (oder in einem Stems-Ordner liegt)."""
    p = Path(path).resolve()
    for part in p.parts[:-1]:
        part_lower = part.lower()
        if part_lower == "stems" or "stems" in part_lower or part_lower.startswith("_demucs_tmp"):
            return True
    stem_name = p.stem.lower()
    for suffix in ("__vocals", "__drums", "__bass", "__other"):
        if stem_name.endswith(suffix) or f"{suffix}__" in stem_name:
            return True
    return False


def _stems_dir(mp3_path: str) -> Path:
    p = Path(mp3_path).resolve()
    parent = p.parent
    # Verhindert verschachtelte stems/stems/... Pfade: nach oben gehen bis zum Song-Hauptordner
    while parent.name.lower() in ("stems", "16zu9", "9zu16") or parent.name.lower().startswith("_demucs_tmp"):
        parent = parent.parent
    return parent / STEM_DIR_NAME


def _stem_path(mp3_path: str, name: str) -> Path:
    return _stems_dir(mp3_path) / f"{Path(mp3_path).stem}__{name}.mp3"


def _wav_to_mp3(wav_path: Path, mp3_path: Path) -> bool:
    try:
        result = subprocess.run(
            [FFMPEG_BIN, "-y", "-i", str(wav_path), "-b:a", "192k", str(mp3_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )
        return result.returncode == 0 and mp3_path.is_file()
    except Exception:
        return False


def _existing_stems(mp3_path: str, names: tuple) -> dict:
    found = {}
    for name in names:
        candidate = _stem_path(mp3_path, name)
        if candidate.is_file():
            found[name] = str(candidate)
    return found


def _cleanup_dir(path: Path) -> None:
    try:
        import shutil
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _separate_demucs(mp3_path: str) -> dict:
    """Nutzt Demucs (htdemucs, 4 Stems) als In-Process-Call (kein separater
    Interpreter-Start pro Song). demucs.separate.main() legt intern
    <tmp_out>/htdemucs/<songname>/<stem>.wav an, das hier in die flache
    ./stems/-Konvention des Projekts umkopiert/umkodiert wird."""
    out_dir = _stems_dir(mp3_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    # BUGFIX (Thread-Safety): vorher war der Demucs-Tmp-Ordner für ALLE Songs
    # im selben Verzeichnis identisch ("_demucs_tmp") -- main.py verarbeitet
    # per AUDIO_PREFETCH_WORKERS=2 zwei Songs gleichzeitig in Threads, und
    # Songs aus demselben Ordner (z.B. FAVs/**-Batch-Lauf) teilten sich damit
    # denselben Tmp-Pfad. Zwei parallele Demucs-Subprozesse hätten sich so
    # gegenseitig die Zwischendateien überschrieben/gelöscht (_cleanup_dir()
    # eines Threads räumt währenddessen den Ordner des anderen Threads weg).
    # Pfad jetzt eindeutig pro Song (Stem-Name des mp3s einbezogen).
    demucs_tmp = out_dir / f"_demucs_tmp_{Path(mp3_path).stem}"
    args = ["--out", str(demucs_tmp), "-n", "htdemucs", mp3_path]
    try:
        _demucs_separate.main(args)
    except SystemExit:
        pass  # demucs.separate.main() beendet sich intern per sys.exit() bei Erfolg
    except Exception:
        return {}

    produced_dir = demucs_tmp / "htdemucs" / Path(mp3_path).stem
    if not produced_dir.is_dir():
        return {}
    stems = {}
    for name in DEMUCS_STEMS:
        wav_path = produced_dir / f"{name}.wav"
        if not wav_path.is_file():
            continue
        mp3_out = _stem_path(mp3_path, name)
        if _wav_to_mp3(wav_path, mp3_out):
            stems[name] = str(mp3_out)
    _cleanup_dir(demucs_tmp)
    return stems


def _separate_hpss(mp3_path: str, y, sr) -> dict:
    """Fallback ohne ML-Modell: librosa HPSS trennt in Harmonic- (Proxy für
    Vocals/Melodie) und Percussive-Anteil (Proxy für Drums). Geringere
    Trennschärfe als Demucs, aber 100% offline ohne zusätzliche Dependency."""
    if librosa is None or sf is None:
        return {}
    if y is None or sr is None:
        try:
            from audio_analysis import load_audio_file
            y, sr = load_audio_file(mp3_path, sr=22050, mono=True)
        except Exception:
            return {}

    try:
        harmonic, percussive = librosa.effects.hpss(y)
    except Exception:
        return {}

    out_dir = _stems_dir(mp3_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = {}
    for name, signal in (("vocals", harmonic), ("drums", percussive)):
        wav_tmp = out_dir / f"_{Path(mp3_path).stem}__{name}_tmp.wav"
        mp3_out = _stem_path(mp3_path, name)
        try:
            sf.write(str(wav_tmp), signal, sr)
            if _wav_to_mp3(wav_tmp, mp3_out):
                stems[name] = str(mp3_out)
        except Exception:
            continue
        finally:
            try:
                wav_tmp.unlink(missing_ok=True)
            except Exception:
                pass
    return stems


def separate_stems(mp3_path: str, y=None, sr=None, log=None) -> dict:
    """Gibt {stem_name: mp3_pfad} zurück, unter <mp3-ordner>/stems/ gecached.
    y/sr optional bereits geladen übergeben (spart Doppel-Load, da
    audio_analysis.analyze_song() den Mix ohnehin schon lädt). Wirft nie —
    Stems sind eine Qualitätsverbesserung, kein Hard-Requirement; schlägt die
    Trennung fehl, arbeitet audio_analysis einfach mit dem vollen Mix weiter."""
    def _log(msg: str):
        if log:
            log(msg)

    if not STEM_SEPARATION_ENABLED or is_stem_file(mp3_path):
        return {}

    has_cuda = False
    try:
        import torch
        has_cuda = torch.cuda.is_available()
    except Exception:
        has_cuda = False

    if STEM_BACKEND == "demucs":
        use_demucs = _HAS_DEMUCS
    elif STEM_BACKEND == "hpss":
        use_demucs = False
    else:  # "auto": Demucs on GPU, instant HPSS on CPU
        use_demucs = _HAS_DEMUCS and has_cuda

    wanted = DEMUCS_STEMS if use_demucs else HPSS_STEMS
    cached = _existing_stems(mp3_path, wanted)
    if cached:
        return cached

    try:
        if use_demucs:
            _log(f"[stems] Trenne via Demucs (GPU/CUDA) -> {_stems_dir(mp3_path)}")
            stems = _separate_demucs(mp3_path)
            if stems:
                return stems
            _log("[stems] Demucs lieferte keine Stems, Fallback auf HPSS.")

        _log(f"[stems] Trenne via schnellem HPSS -> {_stems_dir(mp3_path)}")
        return _separate_hpss(mp3_path, y, sr)
    except Exception as e:
        _log(f"[stems] Stem-Trennung fehlgeschlagen, arbeite mit vollem Mix weiter: {e}")
        return {}


def verify_stem_phase(track_a: str, track_b: str) -> float:
    """Berechnet die Phasen-Korrelation zwischen zwei Audiospuren (-1.0 bis +1.0).
    Werte < 0 weisen auf destruktive Phasenauslöschung hin."""
    try:
        if librosa is None:
            return 1.0
        y1, sr1 = librosa.load(track_a, sr=22050, mono=True, duration=30.0)
        y2, sr2 = librosa.load(track_b, sr=22050, mono=True, duration=30.0)
        min_len = min(len(y1), len(y2))
        if min_len < 100:
            return 1.0
        y1, y2 = y1[:min_len], y2[:min_len]
        denom = (np.linalg.norm(y1) * np.linalg.norm(y2))
        if denom <= 0:
            return 1.0
        return float(np.dot(y1, y2) / denom)
    except Exception:
        return 1.0


def create_stem_doubles(stems: dict, work_dir: Path, log=None) -> dict:
    """Erzeugt phasenkohärente Stem-Doubles (Remaster-Doublet-Technik) mit gezieltem
    Haas-Micro-Shift, L/R-Panning-Offset und harmonischer Sättigung für Vocals, 808 und Drums."""
    def _log(msg):
        if log:
            log(msg)

    if not stems:
        return {}

    doubled_stems = dict(stems)
    out_dir = work_dir / "stem_doubles"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Vocal-Double: 20ms Micro-Delay + L/R 20% Panning + HPF 100Hz @ -6dB
    if "vocals" in stems and Path(stems["vocals"]).is_file():
        voc_double = out_dir / "vocals_double.m4a"
        cmd = [
            FFMPEG_BIN, "-y", "-nostdin", "-i", stems["vocals"],
            "-af", "highpass=f=100,adelay=20|20,volume=-6dB,pan=stereo|c0=0.8*c0+0.2*c1|c1=0.2*c0+0.8*c1",
            "-c:a", "aac", "-b:a", "192k", str(voc_double)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            if res.returncode == 0 and voc_double.is_file():
                doubled_stems["vocals_double"] = str(voc_double)
                _log("[stems] Vocal-Doublet mit 20ms Micro-Shift und L/R-Offset generiert.")
        except Exception:
            pass

    # 2. 808/Bass-Double: Harmonischer Mid-Layer (100-400Hz + Tanh Tube-Sättigung) @ -6dB
    if "bass" in stems and Path(stems["bass"]).is_file():
        bass_double = out_dir / "bass_harmonic_double.m4a"
        cmd = [
            FFMPEG_BIN, "-y", "-nostdin", "-i", stems["bass"],
            "-af", "highpass=f=90,equalizer=f=250:width_type=o:width=1.2:g=3.0,volume=3dB,asoftclip=type=tanh,volume=-9dB",
            "-c:a", "aac", "-b:a", "192k", str(bass_double)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            if res.returncode == 0 and bass_double.is_file():
                doubled_stems["bass_double"] = str(bass_double)
                _log("[stems] 808-Harmonic-Doublet für Handy-Hörbarkeit generiert.")
        except Exception:
            pass

    return doubled_stems

