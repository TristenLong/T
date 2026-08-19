@echo off
title JESTER V1000 - OMNISCIENCE OBSERVATORY
echo ========================================================
echo   JESTER V1000 OBSERVATORY - INITIATING BOOT SEQUENCE
echo ========================================================
echo.

echo [1] Launching Watchdog Hypervisor (Science Engine)...
start cmd /k "title SCIENCE ENGINE WATCHDOG && python watchdog_engine.py"

echo [2] Launching God Hand Dashboard...
start observatory.html

echo.
echo BOOT SEQUENCE COMPLETE.
echo Watch the stars.
pause
