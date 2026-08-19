@echo off
title JESTER V086: QUANTUM OMNIPRESENCE
echo [SYSTEM] INITIALIZING JESTER V086...

:: Kill existing to ensure clean slate (Watchdog will restart them)
taskkill /F /IM python.exe /FI "WINDOWTITLE eq JESTER*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq SERVER" 2>nul
taskkill /F /IM node.exe 2>nul

echo [SYSTEM] HANDING CONTROL TO WATCHDOG...
cd /d "C:\Users\trist\gemini-voice-assistant"
python jester_watchdog.py
pause
