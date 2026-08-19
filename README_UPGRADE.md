# JESTER V081 MASTERMIND - Upgrade Documentation

## New Environment Variables (.env)
- `JESTER_PRIMARY_LLM`: The primary model for both Flask and Pipecat (e.g., `gemini-2.0-flash-lite`, `gemini-1.5-pro`).
- `JESTER_ALLOW_DANGEROUS_TOOLS`: Set to `true` to enable `system_control`, `execute_code`, and `run_terminal_command`. Default: `false`.
- `JESTER_CONFIRMATION_TOKEN`: An optional token required in tool arguments for dangerous tools to execute.

## Tool Enhancements
- `solve_problem`: Now accepts `problem_description` and follows a multi-step analysis workflow.
- `search_web`: Returns structured JSON objects (title, snippet, url) instead of raw strings.
- `safeguards`: All dangerous tools now validate against blocked paths and commands.

## Memory Features
- **Pinning**: In the UI, click the lock icon to pin a memory. Pinned memories are NOT cleared during a PURGE.
- **History Sync**: The frontend now periodically syncs with the Logic Core history database.

## System Vitals
- Real-time model tracking.
- Logic Core vs Logic Engine status indicators.
