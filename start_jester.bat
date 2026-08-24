@echo off
title JESTER V2000: SINGULARITY (SWARM HYPERVISOR)
echo ===================================================================
echo    INITIALIZING JESTER V2000: SINGULARITY (SWARM HYPERVISOR)...
echo ===================================================================

cd /d "%~dp0"

:: Check virtual environment python
set "PYTHON_EXE=%~dp0GOD_HAND_CORE\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
)
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo [SYSTEM] Using Python: %PYTHON_EXE%
echo [SYSTEM] Starting Vite Dev Server...
start /b cmd /c "npx vite"

echo [SYSTEM] Waiting for Vite...
timeout /t 3 /nobreak >nul

echo [SYSTEM] Booting JESTER Electron HUD...
call .\node_modules\.bin\electron.cmd . --dev

:: Clean up Vite when Electron closes
echo [SYSTEM] Shutting down...
taskkill /f /im node.exe >nul 2>&1
pause
