#!/usr/bin/env bash
set -e

echo "===================================================="
echo "  🚀 Native Genome Engine Installer (v0.1)"
echo "===================================================="

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 not found. Please install Python 3.10+."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip setuptools wheel

echo "Installing Genome Engine package in editable mode..."
python -m pip install -e ".[dev]"

echo "Checking FFmpeg installation..."
if ! command -v ffmpeg &> /dev/null; then
    echo "[WARNING] ffmpeg not found in PATH. Please install FFmpeg."
else
    echo "[OK] FFmpeg found."
fi

echo "===================================================="
echo "  ✅ Native Genome Engine Ready!"
echo "  Run: genome-engine hardware-check"
echo "===================================================="
