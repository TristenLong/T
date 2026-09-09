@echo off
title Gemini CLI
cd /d "%~dp0"
echo ========================================================
echo   Launching Gemini CLI...
echo ========================================================
call gemini.cmd
if errorlevel 1 (
    echo.
    echo Gemini CLI exited.
)
pause
