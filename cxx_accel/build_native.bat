@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   OIDASHEIM C++ Native Accelerator Build Utility
echo ========================================================

cd /d "%~dp0"

where cl.exe >nul 2>nul
if %errorlevel% equ 0 (
    echo [BUILD] MSVC cl.exe detected. Compiling cxx_accel.dll with AVX2...
    cl.exe /O2 /Oi /Ot /Gy /arch:AVX2 /fp:fast /std:c++20 /LD cxx_engine.cpp /Fe:cxx_accel.dll
    if %errorlevel% equ 0 (
        echo [SUCCESS] cxx_accel.dll built successfully via MSVC!
        exit /b 0
    )
)

where g++.exe >nul 2>nul
if %errorlevel% equ 0 (
    echo [BUILD] GCC g++.exe detected. Compiling cxx_accel.dll with -O3 -march=native...
    g++.exe -O3 -march=native -ffast-math -std=c++20 -shared -fPIC cxx_engine.cpp -o cxx_accel.dll
    if %errorlevel% equ 0 (
        echo [SUCCESS] cxx_accel.dll built successfully via GCC!
        exit /b 0
    )
)

where clang++.exe >nul 2>nul
if %errorlevel% equ 0 (
    echo [BUILD] Clang clang++.exe detected. Compiling cxx_accel.dll...
    clang++.exe -O3 -march=native -ffast-math -std=c++20 -shared -fPIC cxx_engine.cpp -o cxx_accel.dll
    if %errorlevel% equ 0 (
        echo [SUCCESS] cxx_accel.dll built successfully via Clang!
        exit /b 0
    )
)

echo [INFO] No standalone C++ compiler in PATH. Python SIMD Native Bridge will run via optimized NumPy/Ctypes layer.
exit /b 0
