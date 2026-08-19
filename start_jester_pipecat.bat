@echo off
title JESTER V66 (Pipecat Core)
cd /d "C:\Users\trist\gemini-voice-assistant\pipecat_core"
echo Initializing JESTER V66 Neural Core...
echo ----------------------------------------
echo API Keys Loaded.
echo Transport: WebRTC
echo ----------------------------------------
start "" "http://localhost:7860/client"
"C:\Users\trist\.local\bin\uv.exe" run bot.py
pause
