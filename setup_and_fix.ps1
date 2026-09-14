# ExecutionPolicy setzen, falls Skripte blockiert sind
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force

$ErrorActionPreference = "Stop"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  [1/4] CHECK & REPAIR PYTHON VENV" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Prüfen, ob Python installiert ist
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[FEHLER] Python wurde nicht im System-PATH gefunden. Bitte installieren!" -ForegroundColor Red
    Exit 1
}

# VENV erstellen, falls nicht vorhanden
if (-not (Test-Path "venv")) {
    Write-Host "Erstelle neue virtuelle Python-Umgebung (venv)..." -ForegroundColor Yellow
    python -m venv venv
}

# VENV aktivieren
$VenvActivate = ".\venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
} else {
    Write-Host "[FEHLER] VENV konnte nicht aktiviert werden!" -ForegroundColor Red
    Exit 1
}

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  [2/4] UPGRADE PIP & CORE BUILD TOOLS" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

python -m pip install --upgrade pip setuptools wheel --no-cache-dir

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  [3/4] INSTALL & FIX PIPELINE DEPENDENCIES" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Core Database, Audio & Processing Tools
python -m pip install --upgrade `
    duckdb `
    librosa `
    soundfile `
    numpy `
    opencv-python `
    pillow `
    requests `
    faiss-cpu

# PyTorch & OpenCLIP (Mit CUDA 12.1 GPU Support)
Write-Host "Installiere/Repariere PyTorch (CUDA 12.1)..." -ForegroundColor Yellow
python -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

Write-Host "Installiere OpenCLIP..." -ForegroundColor Yellow
python -m pip install --upgrade open_clip_torch

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  [4/4] SYSTEM CHECK & CACHE CLEANUP" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# PyCache & temporäre Dateien bereinigen
Get-ChildItem -Path . -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force

# FFmpeg Check
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "[HINWEIS] FFmpeg wurde nicht im PATH gefunden." -ForegroundColor Yellow
    Write-Host "Bitte stelle sicher, dass FFmpeg installiert und in den Systemvariablen eingetragen ist." -ForegroundColor Yellow
} else {
    Write-Host "[OK] FFmpeg im System gefunden." -ForegroundColor Green
}

Write-Host "====================================================" -ForegroundColor Green
Write-Host "  SYSTEM & PIPELINE VOLLSTÄNDIG REPARIERT UND BEREIT!" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green