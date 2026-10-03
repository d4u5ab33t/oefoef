#!/usr/bin/env bash
# ==============================================================================
# OIDASHEIM All-in-One Setup, Update, Upgrade, Hardware-Optimization & Test Suite
# Für Linux, WSL2 und macOS
# ==============================================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_step() {
    echo -e "\n${CYAN}======================================================================${NC}"
    echo -e "  ${CYAN}[$1] $2${NC}"
    echo -e "${CYAN}======================================================================${NC}\n"
}

# ── [1/6] Python Runtime & VENV Setup ──────────────────────────────────────────
print_step "1/6" "PYTHON RUNTIME & VIRTUAL ENVIRONMENT CHECK"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[FEHLER] python3 wurde nicht gefunden. Bitte Python 3.10+ installieren.${NC}"
    exit 1
fi

PY_VER=$(python3 --version)
echo -e "${GREEN}[OK] Gefundene Python-Version: ${PY_VER}${NC}"

if [ ! -f ".venv/bin/activate" ]; then
    echo -e "${YELLOW}Erstelle neue virtuelle Umgebung (.venv)...${NC}"
    rm -rf .venv
    python3 -m venv .venv || {
        echo -e "${RED}[FEHLER] python3-venv fehlt möglicherweise. Führe 'sudo apt install python3-venv' aus.${NC}"
        exit 1
    }
fi

source .venv/bin/activate
echo -e "${GREEN}[OK] Virtual Environment (.venv) aktiv.${NC}"

# ── [2/6] Hardware-Erkennung & Performance-Profiling ──────────────────────────
print_step "2/6" "HARDWARE-DIAGNOSE & AUTO-OPTIMIERUNG"
if [ -f "hardware_check.py" ]; then
    python hardware_check.py
fi

# ── [3/6] Package Update & Upgrade ────────────────────────────────────────────
print_step "3/6" "INSTALL, UPDATE & UPGRADE DEPENDENCIES"

echo -e "${YELLOW}Aktualisiere Pip, Setuptools & Wheel...${NC}"
python -m pip install --upgrade pip setuptools wheel --no-cache-dir

echo -e "${YELLOW}Installiere & aktualisiere Kern-Bibliotheken...${NC}"
python -m pip install --upgrade \
    duckdb \
    librosa \
    soundfile \
    numpy \
    opencv-python \
    pillow \
    requests \
    psutil \
    mutagen \
    eyed3 \
    tinytag \
    OpenTimelineIO \
    pytest \
    anyio

echo -e "${YELLOW}Prüfe PyTorch & OpenCLIP...${NC}"
python -m pip install --upgrade torch torchvision torchaudio --extra-index-url https://pypi.org/simple
python -m pip install --upgrade open_clip_torch

# ── [4/6] C++ Acceleration Engine Build/Verify ────────────────────────────────
print_step "4/6" "C++ NATIVE ACCELERATION STACK BUILD & VERIFY"

if command -v cmake &> /dev/null && [ -d "cxx_accel" ]; then
    echo -e "${YELLOW}[CXX] Kompiliere cxx_accel mit CMake (Release / Linux)...${NC}"
    mkdir -p cxx_accel/build
    cmake -S cxx_accel -B cxx_accel/build -DCMAKE_BUILD_TYPE=Release || true
    cmake --build cxx_accel/build --config Release || true
    echo -e "${GREEN}[OK] C++ Native Build-Pass beendet.${NC}"
else
    echo -e "${YELLOW}[INFO] CMake nicht installiert. Vektorisierter SIMD/NumPy Fallback aktiv.${NC}"
fi

# ── [5/6] Cache Cleanup & Integrity Fixes ──────────────────────────────────────
print_step "5/6" "CACHE CLEANUP & INTEGRITY FIXES"

echo -e "${YELLOW}Bereinige temporäre __pycache__ und .pyc Dateien...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}⚠️ [WARNUNG] FFmpeg nicht gefunden! Bitte installieren: sudo apt-get install ffmpeg${NC}"
else
    echo -e "${GREEN}[OK] FFmpeg ist installiert und ausführbar.${NC}"
fi

# ── [6/6] Full Test Suite Verification ─────────────────────────────────────────
print_step "6/6" "AUTOMATISIERTE TEST-SUITE & QUALITÄTSPRÜFUNG"

echo -e "${CYAN}Starte Test-Suite (pytest)...${NC}"
pytest tests/ -q

echo -e "\n${GREEN}======================================================================${NC}"
echo -e "  ${GREEN}✅ ALL SYSTEMS GO! Linux/WSL Setup & Tests erfolgreich abgeschlossen.${NC}"
echo -e "${GREEN}======================================================================${NC}\n"
