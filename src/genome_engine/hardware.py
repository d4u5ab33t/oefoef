"""
hardware.py — Hardware detection & resource planning for Genome Engine.
"""
import ctypes
import os
import platform
from dataclasses import dataclass

RAM_FALLBACK_GB = 8.0
RENDER_RESERVE_CORES = 1
RENDER_RAM_SAFETY_FRACTION = 0.75
RENDER_MIN_WORKERS = 1
RENDER_MAX_WORKERS_HARD_CAP = 8
NVENC_MAX_WORKERS = 4
RENDER_MAX_THREADS_PER_WORKER = 8
ESTIMATED_RAM_MB_1080P_LIBX264_MEDIUM = 400.0

CODEC_RAM_MULTIPLIER = {
    "libx264": 1.0,
    "libx265": 1.5,
    "h264_nvenc": 0.8,
    "hevc_nvenc": 0.9,
}

PRESET_RAM_MULTIPLIER = {
    "ultrafast": 0.7,
    "superfast": 0.8,
    "fast": 0.9,
    "medium": 1.0,
    "slow": 1.3,
    "slower": 1.6,
    "veryslow": 2.0,
}


@dataclass
class HardwareInfo:
    logical_cores: int
    physical_cores: int | None
    total_ram_gb: float
    available_ram_gb: float
    ram_source: str  # "psutil" | "windows" | "linux" | "fallback"


_CACHED: HardwareInfo | None = None


def _detect_ram_psutil():
    import psutil
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
        raise OSError("GlobalMemoryStatusEx failed")
    return stat.ullTotalPhys / (1024 ** 3), stat.ullAvailPhys / (1024 ** 3)


def _detect_ram_linux():
    info = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            key, _, rest = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                info[key] = int(rest.strip().split()[0]) * 1024
    if "MemTotal" not in info:
        raise OSError("MemTotal not in /proc/meminfo")
    total = info["MemTotal"]
    available = info.get("MemAvailable", total * 0.5)
    return total / (1024 ** 3), available / (1024 ** 3)


def detect_hardware(force_refresh: bool = False) -> HardwareInfo:
    """Detect CPU cores + RAM capabilities."""
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
    baseline_px = 1920 * 1080
    px = max(1, width * height)
    scale = px / baseline_px
    codec_mult = CODEC_RAM_MULTIPLIER.get(video_codec, 1.3)
    preset_mult = PRESET_RAM_MULTIPLIER.get(preset, 1.0)
    return ESTIMATED_RAM_MB_1080P_LIBX264_MEDIUM * scale * codec_mult * preset_mult


def recommend_encode_plan(width: int, height: int, video_codec: str, preset: str, use_nvenc: bool = False, log=None) -> tuple[int, int]:
    hw = detect_hardware()
    usable_cores = max(1, hw.logical_cores - RENDER_RESERVE_CORES)
    ram_per_worker_mb = estimate_ram_per_worker_mb(width, height, video_codec, preset)
    ram_budget_mb = hw.available_ram_gb * 1024 * RENDER_RAM_SAFETY_FRACTION
    workers_by_ram = max(1, int(ram_budget_mb // max(1.0, ram_per_worker_mb)))

    hard_cap = NVENC_MAX_WORKERS if use_nvenc else RENDER_MAX_WORKERS_HARD_CAP
    workers = max(RENDER_MIN_WORKERS, min(usable_cores, workers_by_ram, hard_cap))
    threads_per_worker = max(1, min(RENDER_MAX_THREADS_PER_WORKER, usable_cores // workers))

    if log:
        log(f"[hardware] {hw.logical_cores} logical cores, RAM {hw.available_ram_gb:.1f}/{hw.total_ram_gb:.1f} GB available (Source: {hw.ram_source}) -> {workers} workers x {threads_per_worker} threads.")

    return workers, threads_per_worker
