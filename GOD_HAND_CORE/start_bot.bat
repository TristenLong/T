@echo off
set PYTHONIOENCODING=utf-8
title Pipecat Bot
cd /d "C:\Users\trist\gemini-voice-assistant\GOD_HAND_CORE"
echo Starting Pipecat Bot...
echo Open http://localhost:7860/client in your browser.
"C:\Users\trist\.local\bin\uv.exe" run bot.py --transport webrtc
pause
