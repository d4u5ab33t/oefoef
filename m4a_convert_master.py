#!/usr/bin/env python3
"""
m4a_convert_master.py — SEPARATE Convert+Mastering-Chain für ./m4a
--------------------------------------------------------------------
Eigenständiges Skript (bewusst NICHT in main.py verdrahtet), das die
M4A-Dateien (Opus @128kbps) aus einem Input-Ordner (Default: "./m4a"
relativ zu config.ROOT_DIR) in ein besseres, für die restliche oefoef-
Pipeline (audio_analysis.py/mp3_scanner.py erwarten *.mp3) brauchbares
Format konvertiert UND dabei mastert.

Warum "mastern" trotz verlustbehafteter 128kbps-Opus-Quelle:
Transcodieren allein fügt keine verlorenen Frequenzen wieder hinzu --
das ist technisch unmöglich. Was aber sehr wohl gewonnen wird:
  1. Einheitliche Lautheit über den ganzen Katalog (EBU R128 Loudness-
     Normalisierung per ffmpeg "loudnorm", 2-Pass = präzise statt Raten).
  2. Sauberer True-Peak-Headroom (Limiter), damit nichts clippt, wenn
     später Video-Renderer/Player nochmal Gain anfassen.
  3. DC-Offset/Subsonic-Rumpel raus (Highpass @ 20Hz) -- kostet nichts,
     bringt aber sauberere Wellenform für audio_analysis.py's Beat-
     Detection.
  4. Ziel-Format mit hoher, konstanter Bitrate/PCM statt eines zweiten
     verlustbehafteten Hops mit denselben 128kbps (kein Qualitätsgewinn,
     aber auch kein Generationsverlust mehr on top).

Nutzung:
    python m4a_convert_master.py                        # ./m4a -> ./m4a_mastered, MP3 320k
    python m4a_convert_master.py --format flac           # verlustfrei
    python m4a_convert_master.py --format wav            # PCM, verlustfrei, groß
    python m4a_convert_master.py --target-lufs -14        # z.B. Streaming-Standard
    python m4a_convert_master.py --into-mp3-root          # Output zusätzlich in MP3_ROOTS[0]
    python m4a_convert_master.py --workers 4 --force      # alles neu rendern
    python m4a_convert_master.py --dry-run                # nur Plan zeigen, nichts schreiben
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import FFMPEG_BIN, FFPROBE_BIN, LOG_DIR, MP3_ROOTS, ROOT_DIR

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# === TUNING-KONSTANTEN =======================================================
DEFAULT_INPUT_DIR = ROOT_DIR / "m4a"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "m4a_mastered"

DEFAULT_TARGET_LUFS = -16.0      # Integrated Loudness Ziel (EBU R128 "loudnorm")
DEFAULT_TRUE_PEAK = -1.5         # dBTP Headroom, verhindert Intersample-Clipping
DEFAULT_LOUDNORM_LRA = 11.0      # Ziel-Loudness-Range (Dynamik), loudnorm-Default

HIGHPASS_HZ = 20                 # Subsonic-Rumpel/DC-Offset raus, hörbar irrelevant
LIMITER_LEVEL_IN = 1.0
LIMITER_LEVEL_OUT = 0.98         # minimaler Sicherheitsabstand hinter loudnorm

DEFAULT_FORMAT = "mp3"
MP3_BITRATE = "320k"
FLAC_COMPRESSION = 8             # 0 (schnell/groß) .. 8 (langsam/klein), verlustfrei
WAV_SAMPLE_FMT = "s24"           # 24-bit PCM, mehr Headroom als 16-bit für spätere Bearbeitung

DEFAULT_WORKERS = 2              # ffmpeg ist selbst schon multithreaded -> wenige parallele Jobs
LOUDNORM_MEASURE_TIMEOUT_SEC = 300
LOUDNORM_ENCODE_TIMEOUT_SEC = 1800
# === /TUNING-KONSTANTEN ======================================================


def log(msg: str):
    print(msg, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "m4a_convert_master.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass


def find_m4a_files(input_dir: Path) -> list:
    """Rekursiver Scan von input_dir nach *.m4a (case-insensitive, deckt auch
    Windows-typisches .M4A ab)."""
    if not input_dir.exists():
        raise FileNotFoundError(f"Input-Ordner nicht gefunden: {input_dir}")
    found = {p for p in input_dir.rglob("*") if p.suffix.lower() == ".m4a"}
    return sorted(found)


def _output_path_for(src: Path, input_dir: Path, output_dir: Path, fmt: str) -> Path:
    """Spiegelt die Unterordner-Struktur von input_dir nach output_dir, nur
    die Dateiendung ändert sich (z.B. m4a/lofi/track.m4a ->
    m4a_mastered/lofi/track.mp3). Verhindert Namenskollisionen zwischen
    gleichnamigen Dateien aus verschiedenen Unterordnern."""
    rel = src.relative_to(input_dir)
    return (output_dir / rel).with_suffix(f".{fmt}")


def probe_codec_bitrate(path: Path) -> tuple:
    """Liest per ffprobe den tatsächlichen Audio-Codec + Bitrate der Quelle
    (rein informativ fürs Log -- die "Opus @128kbps"-Annahme aus dem
    Dateinamen/Ordner stimmt nicht zwingend für JEDE Datei im Ordner)."""
    try:
        result = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name,bit_rate",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        stream = (json.loads(result.stdout).get("streams") or [{}])[0]
        codec = stream.get("codec_name", "?")
        bit_rate = stream.get("bit_rate")
        kbps = f"{int(bit_rate) // 1000}kbps" if bit_rate else "?kbps"
        return codec, kbps
    except Exception:
        return "?", "?kbps"


def _measure_loudness(src: Path, target_lufs: float, true_peak: float, lra: float) -> dict:
    """PASS 1 der 2-Pass-loudnorm-Mastering-Kette: misst Input-Loudness/-Peak/
    -Range OHNE etwas zu schreiben (ffmpeg -f null). Die zurückgegebenen
    Messwerte gehen als measured_I/measured_TP/measured_LRA/measured_thresh
    in Pass 2 (siehe _build_master_filter) -- das ist der Unterschied
    zwischen "raten" (1-Pass loudnorm, ffmpeg-interner Default) und einer
    tatsächlich exakt aufs Ziel normalisierten Datei (2-Pass, von ffmpeg
    selbst für Broadcast-Zwecke empfohlen)."""
    filt = f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:print_format=json"
    cmd = [FFMPEG_BIN, "-hide_banner", "-nostats", "-i", str(src),
           "-af", filt, "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=LOUDNORM_MEASURE_TIMEOUT_SEC)
    # loudnorm schreibt sein JSON-Messergebnis nach stderr, umgeben von Text --
    # letzte "{...}"-Klammer im Output rausschneiden statt stur alles zu parsen.
    stderr = result.stderr or ""
    start, end = stderr.rfind("{"), stderr.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"loudnorm-Messung (Pass 1) lieferte kein JSON zurück:\n{stderr[-2000:]}")
    return json.loads(stderr[start:end + 1])


def _build_master_filter(measured: dict, target_lufs: float, true_peak: float, lra: float) -> str:
    """Baut die eigentliche Mastering-Filterkette für PASS 2:
    Highpass (Rumpel raus) -> loudnorm im 2-Pass-Modus mit den in Pass 1
    gemessenen Werten (linear statt dynamisch, dadurch reproduzierbar exakt
    auf target_lufs) -> Limiter als letzte Sicherheitsstufe gegen jedes noch
    verbliebene Überschwingen, BEVOR encodiert wird."""
    loudnorm = (
        f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured.get('target_offset', 0)}:linear=true:print_format=summary"
    )
    limiter = f"alimiter=level_in={LIMITER_LEVEL_IN}:level_out={LIMITER_LEVEL_OUT}:limit={LIMITER_LEVEL_OUT}"
    return f"highpass=f={HIGHPASS_HZ},{loudnorm},{limiter}"


def _encode_cmd_for_format(fmt: str, filter_chain: str, src: Path, dst: Path) -> list:
    base = [FFMPEG_BIN, "-y", "-hide_banner", "-nostats", "-i", str(src), "-af", filter_chain]
    if fmt == "mp3":
        return base + ["-c:a", "libmp3lame", "-b:a", MP3_BITRATE, "-ar", "48000", str(dst)]
    if fmt == "flac":
        return base + ["-c:a", "flac", "-compression_level", str(FLAC_COMPRESSION), str(dst)]
    if fmt == "wav":
        return base + ["-c:a", f"pcm_{WAV_SAMPLE_FMT}le", str(dst)]
    raise ValueError(f"Unbekanntes Zielformat: {fmt}")


def convert_and_master(src: Path, dst: Path, fmt: str, target_lufs: float,
                       true_peak: float, lra: float, dry_run: bool = False) -> bool:
    """Eine Datei durch die komplette Convert+Mastering-Chain schicken:
    ffprobe-Info -> Pass 1 (Loudness messen) -> Pass 2 (Highpass+loudnorm
    linear+Limiter, encodiert ins Zielformat). dst.parent wird bei Bedarf
    angelegt; bei Fehlern bleibt eine evtl. bereits angelegte, unvollständige
    dst-Datei NICHT liegen (wird gelöscht), damit kaputte Fragmente nicht
    versehentlich als "fertig konvertiert" durchgehen."""
    codec, kbps = probe_codec_bitrate(src)
    log(f"[m4a-master] {src.name}: Quelle={codec}@{kbps} -> Ziel {fmt.upper()} "
        f"(I={target_lufs} LUFS, TP={true_peak} dBTP, LRA={lra}).")
    if dry_run:
        log(f"[m4a-master] Dry-run: würde schreiben -> {dst}")
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        measured = _measure_loudness(src, target_lufs, true_peak, lra)
        filter_chain = _build_master_filter(measured, target_lufs, true_peak, lra)
        cmd = _encode_cmd_for_format(fmt, filter_chain, src, dst)
        subprocess.run(cmd, capture_output=True, text=True,
                        timeout=LOUDNORM_ENCODE_TIMEOUT_SEC, check=True)
        if not dst.is_file() or dst.stat().st_size <= 0:
            raise RuntimeError("ffmpeg meldete Erfolg, aber Zieldatei fehlt/ist leer.")
        log(f"[m4a-master] OK -> {dst} ({dst.stat().st_size / 1024:.0f} KB, "
            f"gemessen vorher I={measured.get('input_i')} LUFS).")
        return True
    except subprocess.CalledProcessError as e:
        log(f"[m4a-master] FEHLER (ffmpeg) bei {src.name}: {e.stderr[-1500:] if e.stderr else e}")
    except Exception as e:
        log(f"[m4a-master] FEHLER bei {src.name}: {e}\n{traceback.format_exc()}")
    dst.unlink(missing_ok=True)
    return False


def _copy_into_mp3_root(dst: Path, fmt: str, log_fn) -> None:
    """Kopiert eine fertig gemasterte Datei zusätzlich in MP3_ROOTS[0]
    (config.py), damit main.py/mp3_scanner.py sie im nächsten Batch-Lauf
    automatisch mitverarbeitet -- mp3_scanner.find_mp3_files() sucht bewusst
    NUR *.mp3, ein WAV/FLAC-Ziel landet daher NICHT automatisch im
    Beat-Sync-Scope (nur informativ geloggt, kein Fehler)."""
    if not MP3_ROOTS:
        log_fn("[m4a-master] --into-mp3-root: kein MP3_ROOTS in config.py konfiguriert, übersprungen.")
        return
    if fmt != "mp3":
        log_fn(f"[m4a-master] --into-mp3-root: Format '{fmt}' ist kein .mp3 -- "
               "mp3_scanner.py würde die Datei nicht finden. Kopiere trotzdem, aber ohne Scan-Effekt.")
    target_root = Path(MP3_ROOTS[0])
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / dst.name
    shutil.copy2(dst, target)
    log_fn(f"[m4a-master] Kopiert nach MP3_ROOTS[0] -> {target}")


def main():
    parser = argparse.ArgumentParser(
        description="Separate Convert+Mastering-Chain: ./m4a (Opus 128kbps) -> hochwertigeres Zielformat.")
    parser.add_argument("--input-dir", type=str, default=str(DEFAULT_INPUT_DIR),
                        help=f"Ordner mit *.m4a-Quellen (Default: {DEFAULT_INPUT_DIR}).")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
                        help=f"Zielordner, Struktur wird gespiegelt (Default: {DEFAULT_OUTPUT_DIR}).")
    parser.add_argument("--format", choices=("mp3", "flac", "wav"), default=DEFAULT_FORMAT,
                        help="Zielformat (Default: mp3, 320kbps CBR).")
    parser.add_argument("--target-lufs", type=float, default=DEFAULT_TARGET_LUFS,
                        help=f"Ziel-Integrated-Loudness in LUFS (Default: {DEFAULT_TARGET_LUFS}).")
    parser.add_argument("--true-peak", type=float, default=DEFAULT_TRUE_PEAK,
                        help=f"Maximaler True-Peak in dBTP (Default: {DEFAULT_TRUE_PEAK}).")
    parser.add_argument("--lra", type=float, default=DEFAULT_LOUDNORM_LRA,
                        help=f"Ziel-Loudness-Range (Default: {DEFAULT_LOUDNORM_LRA}).")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Parallele ffmpeg-Jobs (Default: {DEFAULT_WORKERS}).")
    parser.add_argument("--force", action="store_true",
                        help="Bereits vorhandene Zieldateien trotzdem neu rendern.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur Plan/Log zeigen, keine ffmpeg-Aufrufe, nichts schreiben.")
    parser.add_argument("--into-mp3-root", action="store_true",
                        help="Fertige Dateien zusätzlich nach MP3_ROOTS[0] kopieren (siehe config.py).")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    try:
        sources = find_m4a_files(input_dir)
    except FileNotFoundError as e:
        log(f"[m4a-master] {e}")
        sys.exit(1)

    if not sources:
        log(f"[m4a-master] Keine .m4a-Dateien in {input_dir} gefunden.")
        return

    log(f"[m4a-master] {len(sources)} .m4a-Datei(en) in {input_dir} gefunden "
        f"-> Ziel: {output_dir} ({args.format.upper()}).")

    jobs = []
    skipped = 0
    for src in sources:
        dst = _output_path_for(src, input_dir, output_dir, args.format)
        if dst.exists() and not args.force and not args.dry_run:
            skipped += 1
            continue
        jobs.append((src, dst))

    if skipped:
        log(f"[m4a-master] {skipped} Datei(en) bereits konvertiert -> übersprungen (--force erzwingt Neu-Rendern).")
    if not jobs:
        log("[m4a-master] Nichts zu tun.")
        return

    ok, failed = 0, 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(convert_and_master, src, dst, args.format,
                        args.target_lufs, args.true_peak, args.lra, args.dry_run): src
            for src, dst in jobs
        }
        try:
            for future in as_completed(futures):
                src = futures[future]
                try:
                    success = future.result()
                except Exception as e:
                    log(f"[m4a-master] Unerwarteter Fehler bei {src}: {e}")
                    success = False
                if success:
                    ok += 1
                    if args.into_mp3_root and not args.dry_run:
                        dst = _output_path_for(src, input_dir, output_dir, args.format)
                        try:
                            _copy_into_mp3_root(dst, args.format, log)
                        except Exception as e:
                            log(f"[m4a-master] Kopie nach MP3_ROOTS fehlgeschlagen ({dst.name}): {e}")
                else:
                    failed += 1
        except KeyboardInterrupt:
            log("[m4a-master] Abgebrochen (Ctrl+C).")
            pool.shutdown(wait=False, cancel_futures=True)
            sys.exit(130)

    log(f"[m4a-master] FERTIG: {ok} ok, {failed} fehlgeschlagen, {skipped} übersprungen.")


if __name__ == "__main__":
    main()
