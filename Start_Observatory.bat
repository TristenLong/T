@echo off
title JESTER V1000 - OMNISCIENCE OBSERVATORY
echo ========================================================
echo   JESTER V1000 OBSERVATORY - INITIATING BOOT SEQUENCE
echo ========================================================
echo.

echo [1] Launching Watchdog Hypervisor (Science Engine)...
start cmd /k "title JESTER V1000 ENGINE && python jester_watchdog.py"

echo [2] Launching Terminal HUD Scanner...
start cmd /k "title JESTER V1000 HUD && python live_hud_scanner.py"

echo [3] Launching God Hand Dashboard...
start observatory.html

echo.
echo BOOT SEQUENCE COMPLETE.
echo Watch the stars.
pause
