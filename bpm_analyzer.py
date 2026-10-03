"""
bpm_analyzer.py — MixMeister BPM Analyzer Integration

Nutzt "C:\\Program Files (x86)\\MixMeister BPM Analyzer\\BpmAnalyzer.exe" als
Fallback-BPM-Detektor wenn librosa kein valides BPM zurückliefert (bpm <= 0)
oder explizit als Primärquelle für Song-Dateien.

CLI-Aufruf:   BpmAnalyzer.exe "<audio_file>"
Stdout-Format: "BPM: 140.00" oder "140.00" oder Zahl am Zeilenende
Rückgabe:     float (BPM), 0.0 bei Fehler/Timeout

Unterstützte Formate: MP3, WAV, WMA, M4A, AAC, OGG (via FMp3Dec.dll)
Timeout: 30 Sekunden per Default (konfigurierbar via config.MIXMEISTER_TIMEOUT_SEC)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

# Config-Import (soft — fällt auf Defaults zurück wenn config nicht geladen)
try:
    from config import MIXMEISTER_BPM_ANALYZER_PATH, MIXMEISTER_TIMEOUT_SEC
except ImportError:
    MIXMEISTER_BPM_ANALYZER_PATH: str = r"C:\Program Files (x86)\MixMeister BPM Analyzer\BpmAnalyzer.exe"
    MIXMEISTER_TIMEOUT_SEC: float = 30.0

# Regex-Pattern für BPM-Output-Parsing (alle bekannten MixMeister-Formate)
_BPM_PATTERNS = [
    re.compile(r"BPM[:\s]+([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE),  # "BPM: 140.00"
    re.compile(r"Tempo[:\s]+([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE),  # "Tempo: 140"
    re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.MULTILINE),      # "140.00" (Rohe Zahl)
    re.compile(r"([0-9]{2,3}(?:\.[0-9]+)?)\s*BPM", re.IGNORECASE),   # "140.00 BPM"
]

_ANALYZER_PATH = Path(MIXMEISTER_BPM_ANALYZER_PATH)
_TIMEOUT = float(MIXMEISTER_TIMEOUT_SEC)


def _parse_bpm_output(stdout: str) -> float:
    """Parst stdout des BpmAnalyzer und gibt BPM als float zurück.
    Gibt 0.0 zurück wenn kein valides BPM gefunden wurde.
    """
    if not stdout:
        return 0.0
    for pattern in _BPM_PATTERNS:
        m = pattern.search(stdout)
        if m:
            try:
                val = float(m.group(1))
                if 20.0 <= val <= 400.0:  # Plausibler BPM-Bereich
                    return round(val, 2)
            except (ValueError, IndexError):
                continue
    return 0.0


def detect_bpm(audio_path: str | Path, timeout: float | None = None) -> float:
    """Ermittelt den BPM-Wert einer Audio-Datei via MixMeister BPM Analyzer.

    Args:
        audio_path: Absoluter Pfad zur Audio-Datei (MP3, WAV, M4A, etc.)
        timeout: Timeout in Sekunden (Default: config.MIXMEISTER_TIMEOUT_SEC = 30s)

    Returns:
        BPM als float. 0.0 wenn:
        - BpmAnalyzer.exe nicht gefunden
        - Datei nicht vorhanden
        - Timeout überschritten
        - Kein valides BPM erkannt (z.B. bei Stille)

    Beispiel:
        >>> bpm = detect_bpm("j:/clips/track.mp3")
        >>> if bpm > 0:
        ...     print(f"BPM: {bpm}")  # BPM: 140.0
    """
    audio_path = Path(audio_path)
    if not _ANALYZER_PATH.is_file():
        return 0.0
    if not audio_path.is_file():
        return 0.0

    t = timeout if timeout is not None else _TIMEOUT

    try:
        result = subprocess.run(
            [str(_ANALYZER_PATH), str(audio_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=t,
            # Kein neues Konsolenfenster — wichtig für ProcessPoolExecutor
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        # MixMeister gibt BPM auf stdout ODER stderr aus — beide prüfen
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        return _parse_bpm_output(combined)
    except subprocess.TimeoutExpired:
        return 0.0
    except FileNotFoundError:
        return 0.0
    except Exception:
        return 0.0


def detect_bpm_batch(
    audio_paths: list[str | Path],
    timeout_per_file: float | None = None,
    max_workers: int = 2,
) -> dict[str, float]:
    """Ermittelt BPM für eine Liste von Audio-Dateien parallel.

    Args:
        audio_paths: Liste von Pfaden zu Audio-Dateien
        timeout_per_file: Timeout pro Datei in Sekunden
        max_workers: Gleichzeitig laufende BpmAnalyzer-Prozesse (Default: 2)
                     WICHTIG: MixMeister ist ressourcenintensiv — nicht zu hoch setzen!

    Returns:
        Dict {str(path): bpm_float}. Fehlgeschlagene Dateien → 0.0
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, float] = {}
    if not audio_paths:
        return results

    t = timeout_per_file if timeout_per_file is not None else _TIMEOUT

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(detect_bpm, p, t): str(p)
            for p in audio_paths
        }
        for future in as_completed(future_to_path):
            path_str = future_to_path[future]
            try:
                results[path_str] = future.result()
            except Exception:
                results[path_str] = 0.0

    return results


def is_available() -> bool:
    """Prüft ob BpmAnalyzer.exe vorhanden und ausführbar ist."""
    return _ANALYZER_PATH.is_file()
