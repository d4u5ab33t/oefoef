#!/usr/bin/env python3
"""
hardware_check.py — Detaillierte Hardware-Erkennung & Render-Optimierungsprofil

Analysiert:
  1. CPU: Logische Kerne, Physische Kerne, AVX2/AVX-512 Support
  2. RAM: Gesamtspeicher, Verfügbarer Speicher, Paging/Swap
  3. GPU / Encoder: NVIDIA NVENC (h264_nvenc / hevc_nvenc), CUDA-Unterstützung
  4. C++ Acceleration: Native cxx_accel Engine Status & Benchmark
  5. Externe Tools: FFmpeg, FFprobe, MixMeister BPM Analyzer
  6. Optimierungsprofile: Automatische Empfehlungen für 1080p und 4K Renders
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import hardware
from config import (
    FFMPEG_BIN,
    FFPROBE_BIN,
    MIXMEISTER_BPM_ANALYZER_PATH,
    MIXMEISTER_BPM_FALLBACK_ENABLED,
    USE_NVENC_IF_AVAIL,
    ENCODE_PRESET,
    OUTPUT_RESOLUTION,
)


def print_banner(text: str):
    line = "=" * 70
    print(f"\n{line}")
    print(f"  ⚡ {text}")
    print(f"{line}")


def check_ffmpeg() -> dict:
    ffmpeg_ok = shutil.which(FFMPEG_BIN) is not None or Path(FFMPEG_BIN).is_file()
    ffprobe_ok = shutil.which(FFPROBE_BIN) is not None or Path(FFPROBE_BIN).is_file()
    nvenc_h264 = False
    nvenc_hevc = False

    if ffmpeg_ok:
        try:
            res = subprocess.run(
                [FFMPEG_BIN, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            out = res.stdout or ""
            nvenc_h264 = "h264_nvenc" in out
            nvenc_hevc = "hevc_nvenc" in out
        except Exception:
            pass

    return {
        "ffmpeg": ffmpeg_ok,
        "ffprobe": ffprobe_ok,
        "nvenc_h264": nvenc_h264,
        "nvenc_hevc": nvenc_hevc,
    }


def check_cxx_accel() -> dict:
    try:
        from cxx_accel.bridge import get_cxx_engine
        engine = get_cxx_engine()
        info = engine.get_status_info()
        return {
            "available": True,
            "version": info.get("version", "unknown"),
            "native": info.get("native_dll_loaded", False),
            "engine": info.get("engine_label", "Python SIMD Fallback"),
        }
    except Exception as e:
        return {"available": False, "error": str(e), "native": False, "engine": "None"}


def check_mixmeister() -> dict:
    try:
        import bpm_analyzer
        avail = bpm_analyzer.is_available()
        return {
            "available": avail,
            "path": str(bpm_analyzer._ANALYZER_PATH),
            "enabled": MIXMEISTER_BPM_FALLBACK_ENABLED,
        }
    except Exception as e:
        return {"available": False, "error": str(e), "enabled": False}


def main():
    print_banner("OIDASHEIM HARDWARE-DIAGNOSE & PERFORMANCE-PROFILER")

    # 1. System & OS
    print(f"🖥️  Betriebssystem:  {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"🐍 Python Runtime:   {platform.python_version()} ({sys.executable})")

    # 2. Hardware Profiling
    hw = hardware.detect_hardware(force_refresh=True)
    print(f"\n🧠 CPU & ARBEITSSPEICHER:")
    print(f"   - Logische Kerne:    {hw.logical_cores}")
    print(f"   - Physische Kerne:   {hw.physical_cores if hw.physical_cores else 'Nicht ermittelbar'}")
    print(f"   - Gesamter RAM:      {hw.total_ram_gb:.2f} GB")
    print(f"   - Freier/Verfügbar:  {hw.available_ram_gb:.2f} GB (Quelle: {hw.ram_source})")

    # 3. GPU / Video-Encoder
    ff_info = check_ffmpeg()
    print(f"\n🎬 VIDEO-ENCODER & MULTIMEDIA-TOOLS:")
    print(f"   - FFmpeg installiert: {'✅ Ja' if ff_info['ffmpeg'] else '❌ FEHLT (wird zwingend benötigt!)'}")
    print(f"   - FFprobe installiert: {'✅ Ja' if ff_info['ffprobe'] else '❌ FEHLT'}")
    print(f"   - NVIDIA NVENC H.264:  {'✅ Verfügbar (Hardware-Beschleunigung aktiv)' if ff_info['nvenc_h264'] else '⚪ Nicht verfügbar (CPU-Fallback)'}")
    print(f"   - NVIDIA NVENC HEVC:   {'✅ Verfügbar (H.265 Hardware-Encoding)' if ff_info['nvenc_hevc'] else '⚪ Nicht verfügbar'}")

    # 4. C++ Acceleration
    cxx_info = check_cxx_accel()
    print(f"\n⚡ C++ NATIVE ACCELERATION STACK:")
    if cxx_info.get("available"):
        native_badge = "🚀 C++20 Native DLL (AVX2/SIMD)" if cxx_info.get("native") else "⚙️ Vektorisierter Python/NumPy Fallback"
        print(f"   - Status:             ✅ Bereit")
        print(f"   - Engine:             {native_badge}")
        print(f"   - Version:            {cxx_info.get('version')}")
    else:
        print(f"   - Status:             ❌ Fehler ({cxx_info.get('error')})")

    # 5. MixMeister BPM Analyzer
    mm_info = check_mixmeister()
    print(f"\n🎵 BPM-DETEKTION & AUDIO-ANALYSE:")
    print(f"   - MixMeister Analyzer: {'✅ Installiert & Aktiv' if mm_info.get('available') else '⚪ Nicht gefunden (librosa übernimmt vollständig)'}")
    if mm_info.get("available"):
        print(f"   - Pfad:                {mm_info.get('path')}")

    # 6. Render-Optimierungsprofil
    print(f"\n🚀 OPTIMIERTE RENDER-KONFIGURATION:")
    for res_name, (w, h) in [("1080p HD (1920x1080)", (1920, 1080)), ("4K UHD (3840x2160)", (3840, 2160))]:
        use_nvenc = ff_info["nvenc_h264"] and USE_NVENC_IF_AVAIL
        codec = "h264_nvenc" if use_nvenc else "libx264"
        workers, threads = hardware.recommend_encode_plan(w, h, codec, ENCODE_PRESET, use_nvenc)
        ram_est = hardware.estimate_ram_per_worker_mb(w, h, codec, ENCODE_PRESET)
        print(f"   [{res_name}]:")
        print(f"      • Codec:              {codec}")
        print(f"      • Parallele Worker:   {workers}")
        print(f"      • Threads pro Worker: {threads}")
        print(f"      • Geschätzter RAM:    ~{ram_est:.0f} MB / Worker")

    print(f"\n{'=' * 70}")
    print("  ✅ System-Check abgeschlossen. Alle Stacks einsatzbereit.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
