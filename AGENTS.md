# JESTER / GOD_HAND Universal Agent Protocol (AGENTS.md)

> **Universal Agent Standard: Codex, OpenCode, Antigravity, & Sub-Agents**  
> Workspace: `c:\Users\trist\gemini-voice-assistant`  
> Synchronized with: `CLAUDE.md`, `GEMINI.md`

## Mission & Architecture
The JESTER / GOD_HAND project is an autonomous multi-modal agent stack comprising:
- **Voice / Audio**: WebRTC + Pipecat + Deepgram/Cartesia audio stream (port 7860)
- **Vision / UI**: React + Vite matrix observatory hub (port 5173)
- **API Server**: Flask backend endpoints (port 5000)
- **Multi-Agent Terminal Fleet**: Claude Code, Gemini CLI, OpenCode, and specialized sub-agents.

## Agent Fleet & Roles
1. **`brutal_critic`** (`.claude/agents/brutal_critic.md`):
   - Harsh, objective evaluation of code, plans, and scripts.
   - 3-lens evaluation: Structural correctness, performance/retention, security/limits.
2. **`session_closer`** (`.claude/agents/session_closer.md`):
   - End-of-session auditor.
   - Synchronizes `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and updates `session_summary.md`.
   - Stages and commits all work to Git.
3. **`deep_research`**:
   - Web extraction and comprehensive markdown report builder.

## Directives
- Always preserve working system ports: 5000, 5173, 7860.
- When closing a session, invoke `python sync_context.py --close`.
