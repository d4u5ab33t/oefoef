"""
hardware.py — Hardware-Erkennung + adaptive Ressourcen-Planung für ffmpeg-Renders.

WARUM DIESE DATEI EXISTIERT:
renderer.py wählte die Anzahl paralleler ffmpeg-Segment-Encodes bisher rein
nach CPU-Kernzahl (`min(8, cpu_count)`), OHNE zu berücksichtigen, dass:
  1. jede einzelne ffmpeg-Instanz OHNE `-threads`-Deckel selbst versucht,
     ALLE verfügbaren Kerne zu nutzen -> bei 8 parallelen Instanzen auf z.B.
     einer 8-Kern-CPU fordert das System effektiv 8x8=64 Threads auf 8 Kernen
     an (massives Oversubscription/Thrashing, CPU pendelt bei ~99% ohne
     echten Fortschritt).
  2. jede Instanz -- v.a. bei 4K + libx265 + Preset "medium" -- mehrere
     hundert MB bis wenige GB RAM für Referenz-/Lookahead-Buffer braucht.
     8 parallele Instanzen davon können den verfügbaren RAM sprengen (Swap/
     OOM), unabhängig davon, wie viele CPU-Kerne vorhanden sind.

Dieses Modul ermittelt die TATSÄCHLICHE Hardware (Kerne, verfügbarer RAM,
GPU/NVENC) und leitet daraus sowohl die Worker-Zahl (wie viele ffmpeg-
Instanzen parallel laufen) als auch die Thread-Zahl PRO Instanz ab, sodass
weder CPU noch RAM überzeichnet werden. Siehe recommend_encode_plan().

Best-effort: nutzt psutil falls installiert (genauere "verfügbarer RAM"-Zahl
inkl. Cache/Buffers-Berücksichtigung), fällt sonst auf plattformspezifische
Bordmittel zurück (Windows: GlobalMemoryStatusEx, Linux: /proc/meminfo).
Schlägt auch das fehl, wird konservativ mit RAM_FALLBACK_GB weitergerechnet
-- Hardware-Erkennung darf NIE einen Render verhindern oder zum Absturz
bringen, sie soll ihn nur intelligenter dimensionieren.
"""
import ctypes
import os
import platform
from dataclasses import dataclass

from config import (CODEC_RAM_MULTIPLIER, ESTIMATED_RAM_MB_1080P_LIBX264_MEDIUM,
                    NVENC_MAX_WORKERS, PRESET_RAM_MULTIPLIER, RAM_FALLBACK_GB,
                    RENDER_MAX_THREADS_PER_WORKER, RENDER_MAX_WORKERS_HARD_CAP,
                    RENDER_MIN_WORKERS, RENDER_RAM_SAFETY_FRACTION,
                    RENDER_RESERVE_CORES)


@dataclass
class HardwareInfo:
    logical_cores: int
    physical_cores: int | None
    total_ram_gb: float
    available_ram_gb: float
    ram_source: str  # "psutil" | "windows" | "linux" | "fallback"


# Prozessweiter Cache: Hardware ändert sich nicht innerhalb eines main.py-
# Laufs (auch nicht im Batch-Modus über viele Songs hinweg) -> keine neue
# Messung pro Song nötig, siehe force_refresh für den seltenen Sonderfall.
_CACHED: HardwareInfo | None = None


def _detect_ram_psutil():
    import psutil  # optionale Abhängigkeit, siehe requirements.txt
    vm = psutil.virtual_memory()
    return vm.total / (1024 ** 3), vm.available / (1024 ** 3)


def _detect_ram_windows():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
        raise OSError("GlobalMemoryStatusEx fehlgeschlagen")
    return stat.ullTotalPhys / (1024 ** 3), stat.ullAvailPhys / (1024 ** 3)


def _detect_ram_linux():
    info = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            key, _, rest = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                info[key] = int(rest.strip().split()[0]) * 1024  # kB -> Bytes
    if "MemTotal" not in info:
        raise OSError("MemTotal nicht in /proc/meminfo gefunden")
    total = info["MemTotal"]
    # Ältere Kernel liefern kein MemAvailable -> konservativ die Hälfte des
    # Totals annehmen statt komplett zu scheitern.
    available = info.get("MemAvailable", total * 0.5)
    return total / (1024 ** 3), available / (1024 ** 3)


def detect_hardware(force_refresh: bool = False) -> HardwareInfo:
    """Ermittelt CPU-Kerne + RAM (gecached, siehe force_refresh)."""
    global _CACHED
    if _CACHED is not None and not force_refresh:
        return _CACHED

    logical_cores = os.cpu_count() or 4
    physical_cores = None
    try:
        import psutil
        physical_cores = psutil.cpu_count(logical=False)
    except Exception:
        pass

    total_gb = available_gb = None
    ram_source = "fallback"
    candidates = [("psutil", _detect_ram_psutil)]
    if platform.system() == "Windows":
        candidates.append(("windows", _detect_ram_windows))
    elif platform.system() == "Linux":
        candidates.append(("linux", _detect_ram_linux))
    for name, fn in candidates:
        try:
            total_gb, available_gb = fn()
            ram_source = name
            break
        except Exception:
            continue

    if total_gb is None:
        total_gb = available_gb = float(RAM_FALLBACK_GB)
        ram_source = "fallback"

    _CACHED = HardwareInfo(
        logical_cores=logical_cores, physical_cores=physical_cores,
        total_ram_gb=round(total_gb, 2), available_ram_gb=round(available_gb, 2),
        ram_source=ram_source,
    )
    return _CACHED


def estimate_ram_per_worker_mb(width: int, height: int, video_codec: str, preset: str) -> float:
    """Grobe (bewusst konservative) RAM-Schätzung pro parallelem ffmpeg-
    Encode-Worker, skaliert von einer 1080p/libx264/medium-Baseline über
    Pixelanzahl + Codec- + Preset-Multiplikator hoch. Kein exaktes Profiling
    -- Ziel ist, grobe Größenordnungsfehler zu vermeiden (z.B. 4K+libx265 mit
    derselben Worker-Zahl wie 1080p+libx264 behandeln), nicht Byte-genau zu
    sein. Eine Überschätzung kostet nur etwas Parallelität, eine
    Unterschätzung riskiert Swapping/OOM -- daher im Zweifel eher hoch."""
    baseline_px = 1920 * 1080
    px = max(1, width * height)
    scale = px / baseline_px
    codec_mult = CODEC_RAM_MULTIPLIER.get(video_codec, 1.3)
    preset_mult = PRESET_RAM_MULTIPLIER.get(preset, 1.0)
    return ESTIMATED_RAM_MB_1080P_LIBX264_MEDIUM * scale * codec_mult * preset_mult


def recommend_encode_plan(width: int, height: int, video_codec: str, preset: str,
                          use_nvenc: bool, log=None) -> "tuple[int, int]":
    """Liefert (max_workers, threads_per_worker) für render_silent_video()'s
    parallelen Segment-Encode-Pass, basierend auf tatsächlich erkannter
    Hardware statt eines pauschalen `min(8, cpu_count)`. Beide Werte sind so
    gewählt, dass weder CPU (workers * threads_per_worker <= nutzbare
    logische Kerne) noch RAM (workers * geschätzter RAM/Worker <= Safety-
    Anteil des VERFÜGBAREN RAMs) nennenswert überzeichnet werden."""
    hw = detect_hardware()

    usable_cores = max(1, hw.logical_cores - RENDER_RESERVE_CORES)
    ram_per_worker_mb = estimate_ram_per_worker_mb(width, height, video_codec, preset)
    ram_budget_mb = hw.available_ram_gb * 1024 * RENDER_RAM_SAFETY_FRACTION
    workers_by_ram = max(1, int(ram_budget_mb // max(1.0, ram_per_worker_mb)))

    hard_cap = NVENC_MAX_WORKERS if use_nvenc else RENDER_MAX_WORKERS_HARD_CAP
    workers = max(RENDER_MIN_WORKERS, min(usable_cores, workers_by_ram, hard_cap))

    threads_per_worker = max(1, min(RENDER_MAX_THREADS_PER_WORKER, usable_cores // workers))

    if log:
        phys = f" ({hw.physical_cores} physisch)" if hw.physical_cores else ""
        log(f"[hardware] {hw.logical_cores} logische Kerne{phys}, "
            f"RAM {hw.available_ram_gb:.1f}/{hw.total_ram_gb:.1f} GB verfügbar "
            f"(Quelle: {hw.ram_source}) | ~{ram_per_worker_mb:.0f} MB/Worker geschätzt "
            f"({video_codec}, preset={preset}, {width}x{height}) "
            f"-> {workers} Worker x {threads_per_worker} Threads "
            f"(RAM-Limit waere {workers_by_ram}, CPU-Limit waere {usable_cores}).")

    return workers, threads_per_worker


def thread_ffmpeg_args(video_codec: str, threads: int) -> list:
    """ffmpeg-CLI-Argumente, die einen einzelnen ffmpeg-Subprocess auf
    `threads` Threads deckeln. `-threads N` regelt Decode-/Filter-Threads
    für alle Codecs, aber libx265 verwaltet seinen Encoder-eigenen Thread-
    Pool separat und ignoriert `-threads` dafür weitgehend -> zusätzlich
    `-x265-params pools=...:frame-threads=...` nötig, sonst zieht sich
    libx265 trotz `-threads`-Deckel weiterhin alle Kerne."""
    args = ["-threads", str(max(1, threads))]
    if video_codec == "libx265":
        frame_threads = max(1, min(4, threads))
        args += ["-x265-params", f"pools={max(1, threads)}:frame-threads={frame_threads}"]
    return args
