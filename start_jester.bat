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

:: Delegate to the robust Python launch script
"%PYTHON_EXE%" start_jester.py
