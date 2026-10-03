@echo off
setlocal enabledelayedexpansion

title OIDASHEIM — All-in-One Setup, Update, Hardware Optimization ^& Test Suite

echo ======================================================================
echo   🚀 OIDASHEIM 1-CLICK ALL-IN-ONE RUNNER (WINDOWS)
echo ======================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_and_fix.ps1"

echo.
echo ======================================================================
echo   Druecke eine beliebige Taste zum Beenden...
echo ======================================================================
pause >nul