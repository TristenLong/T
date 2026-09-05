# JESTER / GOD_HAND Architecture & Rules (Claude Code Context)

> **Terminal AI Standard: Claude Code (`claude`)**  
> Workspace: `c:\Users\trist\gemini-voice-assistant`  
> Synchronized with: `GEMINI.md`, `AGENTS.md`

## Overview
This repository contains the **JESTER / GOD_HAND** hybrid voice, vision, and terminal intelligence system.
- **Frontend**: React + Vite on port 5173 (`npm run dev`)
- **Backend / Core**: Python Flask (port 5000) and GOD_HAND Core / Pipecat WebRTC engine (port 7860)
- **Terminal Workflows**: Claude Code, Gemini CLI, OpenCode, and sub-agents.

## Core Commands & Guidelines
- **Development**:
  - Frontend: `npm run dev` (Vite port 5173)
  - Backend: `python server/server.py` (Flask port 5000)
  - Core: `python GOD_HAND_CORE/bot.py` or `python start_jester.py`
  - Tests: `npm test`
- **Sub-Agents Location**: `.claude/agents/`
  - `brutal_critic.md`: Multi-perspective anti-gaslighting critique agent.
  - `session_closer.md`: End-of-day summary, context sync, and git commit agent.
- **Context Synchronization**:
  - Run `python sync_context.py` whenever updating project architecture or core rules.

## Operating Principles
1. **Never Break Working Endpoints**: Ports 5000 (Flask), 5173 (Vite), 7860 (Core).
2. **Tri-Context Integrity**: Keep `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` in sync.
3. **Daily Session Protocol**: Run the Session Closer agent or `python sync_context.py --close` at the end of each session to write `session_summary.md` and commit to Git.
