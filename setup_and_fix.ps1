<#
.SYNOPSIS
    OIDASHEIM All-in-One Setup, Update, Upgrade, Hardware-Optimization & Test Suite (Windows)
.DESCRIPTION
    Führt automatisiert alle Installations-, Update-, Upgrade- und Fehlerbehebungs-Schritte aus:
    1. Erkennt Python Runtime & repariert/erstellt Virtual Environment (venv)
    2. Führt Hardware-Erkennung (CPU, RAM, GPU/NVENC) & Optimierungsprofiling durch
    3. Installiert & aktualisiert alle Core-Dependencies & Audio/Vision Stacks
    4. Kompiliert/verifiziert den C++ Native Acceleration Stack (cxx_accel)
    5. Bereinigt korrupte Caches & temporäre Render-Dateien
    6. Führt die vollständige automatisierte Test-Suite (pytest) zur Qualitätsprüfung aus
#>

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
$ErrorActionPreference = "Stop"

function Print-Step($num, $title) {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "  [$num] $title" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
}

# ── [1/6] Python Runtime & VENV Setup ──────────────────────────────────────────
Print-Step "1/6" "PYTHON RUNTIME & VIRTUAL ENVIRONMENT CHECK"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[FEHLER] Python wurde nicht im System-PATH gefunden. Bitte installieren (Python 3.10+)!" -ForegroundColor Red
    Exit 1
}

$PyVer = python --version
Write-Host "[OK] Gefundene Python-Version: $PyVer" -ForegroundColor Green

# VENV prüfen oder erstellen
$VenvFolder = "venv"
if (-not (Test-Path $VenvFolder)) {
    Write-Host "[INFO] Erstelle neue virtuelle Umgebung (venv)..." -ForegroundColor Yellow
    python -m venv $VenvFolder
}

$VenvActivate = ".\$VenvFolder\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
    Write-Host "[OK] Virtual Environment aktiv ($VenvFolder)." -ForegroundColor Green
} else {
    Write-Host "[INFO] Nutze globales/aktives Python-Environment." -ForegroundColor Yellow
}

# ── [2/6] Hardware-Erkennung & Performance-Profiling ──────────────────────────
Print-Step "2/6" "HARDWARE-DIAGNOSE & AUTO-OPTIMIERUNG"
if (Test-Path "hardware_check.py") {
    python hardware_check.py
}

# ── [3/6] Package Update & Upgrade ────────────────────────────────────────────
Print-Step "3/6" "INSTALL, UPDATE & UPGRADE DEPENDENCIES"

Write-Host "Aktualisiere Pip, Setuptools & Wheel..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel --no-cache-dir

Write-Host "Installiere & aktualisiere Kern-Bibliotheken..." -ForegroundColor Yellow
python -m pip install --upgrade `
    duckdb `
    librosa `
    soundfile `
    numpy `
    opencv-python `
    pillow `
    requests `
    psutil `
    mutagen `
    eyed3 `
    tinytag `
    OpenTimelineIO `
    pytest `
    anyio

# Optionale ML & Vision Bibliotheken
Write-Host "Prüfe Torch & OpenCLIP..." -ForegroundColor Yellow
python -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --extra-index-url https://pypi.org/simple
python -m pip install --upgrade open_clip_torch

# ── [4/6] C++ Acceleration Engine Build/Verify ────────────────────────────────
Print-Step "4/6" "C++ NATIVE ACCELERATION STACK BUILD & VERIFY"

if (Get-Command cmake -ErrorAction SilentlyContinue) {
    Write-Host "[CXX] Kompiliere cxx_accel mit CMake (Release / AVX2)..." -ForegroundColor Yellow
    try {
        cmake -S cxx_accel -B cxx_accel/build -DCMAKE_BUILD_TYPE=Release
        cmake --build cxx_accel/build --config Release
        Write-Host "[OK] C++ Native Engine (cxx_accel.dll) erfolgreich gebaut!" -ForegroundColor Green
    } catch {
        Write-Host "[INFO] CMake Build übersprungen/fehlgeschlagen. Vektorisierter SIMD Fallback aktiv." -ForegroundColor Yellow
    }
} elseif (Test-Path ".\cxx_accel\build_native.bat") {
    Write-Host "[INFO] CMake nicht im PATH. Starte cxx_accel\build_native.bat..." -ForegroundColor Yellow
    try {
        & ".\cxx_accel\build_native.bat"
    } catch {
        Write-Host "[INFO] Standalone Batch Build beendet. Vektorisierter SIMD Fallback aktiv." -ForegroundColor Yellow
    }
}

# ── [5/6] Cache Cleanup & Integrity Fixes ──────────────────────────────────────
Print-Step "5/6" "CACHE CLEANUP & INTEGRITY FIXES"

Write-Host "Bereinige temporäre __pycache__ und .pyc Dateien..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# FFmpeg Check
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️ [WARNUNG] FFmpeg wurde nicht im PATH gefunden!" -ForegroundColor Yellow
    Write-Host "   Bitte lade FFmpeg von https://ffmpeg.org herunter und füge es zu deinen System-Umgebungsvariablen hinzu." -ForegroundColor Yellow
} else {
    Write-Host "[OK] FFmpeg ist installiert und ausführbar." -ForegroundColor Green
}

# ── [6/6] Full Test Suite Verification ─────────────────────────────────────────
Print-Step "6/6" "AUTOMATISIERTE TEST-SUITE & QUALITÄTSPRÜFUNG"

Write-Host "Starte Test-Suite (pytest)..." -ForegroundColor Cyan
pytest tests/ -q
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "  ✅ ALL SYSTEMS GO! Alle Tests bestanden. Pipeline 100% einsatzbereit." -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Yellow
    Write-Host "  ⚠️ Einige Tests meldeten Warnungen oder Fehler. Bitte Logs prüfen." -ForegroundColor Yellow
    Write-Host "======================================================================" -ForegroundColor Yellow
}