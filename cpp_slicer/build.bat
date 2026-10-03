@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo Compiling Oidasheim C++ Semantic Slicer
echo ========================================================

cd /d "%~dp0"

if not exist build mkdir build
cd build

cmake .. -DCMAKE_BUILD_TYPE=Release
if %ERRORLEVEL% NEQ 0 (
    echo [CMake] Generation failed or CMake generator not found. Trying direct MSVC/Clang...
    goto direct_build
)

cmake --build . --config Release
if %ERRORLEVEL% EQU 0 (
    if exist "Release\oidasheim_slicer.exe" (
        copy /y "Release\oidasheim_slicer.exe" "oidasheim_slicer.exe" >nul
    )
    echo [SUCCESS] Binary created in build\oidasheim_slicer.exe
    goto done
)

:direct_build
echo Trying direct build...
where cl.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    cl.exe /EHsc /O2 /std:c++17 /utf-8 /I..\include ..\src\*.cpp /Fe:oidasheim_slicer.exe
    goto done
)

where g++ >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    g++ -std=c++17 -O3 -I../include ../src/*.cpp -o oidasheim_slicer.exe
    goto done
)

where clang++ >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    clang++ -std=c++17 -O3 -I../include ../src/*.cpp -o oidasheim_slicer.exe
    goto done
)

echo [WARNING] No native C++ compiler found on PATH. Please run from Visual Studio Developer Command Prompt or install g++/clang.

:done
cd /d "%~dp0"
