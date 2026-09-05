# JESTER / GOD_HAND Architecture & Rules (Gemini CLI Context)

> **Terminal AI Standard: Google Gemini CLI (`gemini`)**  
> Workspace: `c:\Users\trist\gemini-voice-assistant`  
> Synchronized with: `CLAUDE.md`, `AGENTS.md`

## Overview
This repository contains the **JESTER / GOD_HAND** hybrid voice, vision, and terminal intelligence system.
- **Frontend**: React + Vite on port 5173 (`npm run dev`)
- **Backend / Core**: Python Flask (port 5000) and GOD_HAND Core / Pipecat WebRTC engine (port 7860)
- **Gemini Capabilities**: Large-context analysis (1M-2M tokens), deep research reports, web exploration, and automated file creation.

## Core Commands & Guidelines
- **Development**:
  - Frontend: `npm run dev` (Vite port 5173)
  - Backend: `python server/server.py` (Flask port 5000)
  - Core: `python GOD_HAND_CORE/bot.py` or `python start_jester.py`
  - Tests: `npm test`
- **Output Standards**:
  - Direct local file writes when requested.
  - Structure complex research into clear markdown files.
  - Coordinate with Claude Code and Codex sub-agents.

## Operating Principles
1. **Never Break Working Endpoints**: Ports 5000 (Flask), 5173 (Vite), 7860 (Core).
2. **Tri-Context Integrity**: Keep `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` in sync.
3. **Daily Session Protocol**: Run the Session Closer agent or `python sync_context.py --close` at the end of each session to write `session_summary.md` and commit to Git.
