@echo off
REM ============================================================================
REM LA.BAT — SYNAPSE AUDIO DYNAMICS Environment & System Bootloader
REM Location: J:\Oidasheim\oefoef\la_bootloader.bat
REM Motto: "Resonanz erzeugen. Werte erschaffen. Unsterblichkeit codieren."
REM ============================================================================

echo.
echo ============================================================================
echo   ███████╗██╗   ██╗███╗   ██╗██████╗ ███████╗███████╗    ██████╗ ███████╗
echo   ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔════╝██╔════╝   ██╔═══██╗██╔════╝
echo   ███████╗ ╚████╔╝ ██╔██╗ ██║██████╔╝███████╗█████╗     ██║   ██║███████╗
echo   ╚════██║  ╚██╔╝  ██║╚██╗██║██╔═══╝ ╚════██║██╔══╝     ██║   ██║╚════██║
echo   ███████║   ██║   ██║ ╚████║██║     ███████║███████╗   ╚██████╔╝███████║
echo   ╚══════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝     ╚══════╝╚══════╝    ╚═════╝ ╚══════╝
echo                     SYNAPSE AUDIO DYNAMICS — BOOTLOADER (LA.BAT)
echo ============================================================================
echo.

SET OIDASHEIM_ROOT=J:\Oidasheim\oefoef
SET PYTHONUTF8=1

echo [LA.BAT] Checking Python Environment...
python --version
if errorlevel 1 (
    echo [LA.BAT] ERROR: Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo [LA.BAT] Initializing IDEX Kernel, NAF, VEGA, PUBX, and WEEDIT v9...
python synapse_os.py --status

if "%1"=="--album-sim" (
    echo [LA.BAT] Starting Full 10-Track Album Simulation...
    python synapse_os.py --album-sim
) else (
    if "%1"=="--synapse" (
        echo [LA.BAT] Launching SYNAPSE AUDIO DYNAMICS Pipeline...
        python main.py --synapse %2 %3 %4 %5
    ) else (
        echo [LA.BAT] SYNAPSE System Ready. Pass --synapse or --album-sim to execute.
    )
)

echo.
echo [LA.BAT] Execution finished.
