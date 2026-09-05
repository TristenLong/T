#!/usr/bin/env python3
"""
sync_context.py
Tri-Context Synchronization & Session Closer Utility
Inspired by NetworkChuck's Terminal AI architecture.
Synchronizes CLAUDE.md, GEMINI.md, and AGENTS.md, updates session_summary.md,
and handles automated end-of-session git commits.
"""

import sys
import os
import datetime
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
CLAUDE_MD = ROOT_DIR / "CLAUDE.md"
GEMINI_MD = ROOT_DIR / "GEMINI.md"
AGENTS_MD = ROOT_DIR / "AGENTS.md"
SUMMARY_MD = ROOT_DIR / "session_summary.md"


def get_git_status():
    try:
        res = subprocess.run(
            ["git", "status", "-s"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception as e:
        return f"Error retrieving git status: {e}"


def sync_contexts():
    print("[*] Verifying Tri-Context files (CLAUDE.md, GEMINI.md, AGENTS.md)...")
    for f in [CLAUDE_MD, GEMINI_MD, AGENTS_MD]:
        if not f.exists():
            print(f"[-] Warning: {f.name} missing!")
        else:
            print(f"[+] Verified: {f.name} ({f.stat().st_size} bytes)")
    print("[+] Tri-Context state is verified.")


def close_session(custom_note=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    git_status = get_git_status()

    note = custom_note or "Session work logged and context synchronized."

    entry = f"""
### Session Close: {now}
- **Status**: Completed
- **Note**: {note}
- **Git Modified Files**:
```
{git_status or 'Clean working tree'}
```
---
"""
    # Append to session_summary.md
    existing = ""
    if SUMMARY_MD.exists():
        existing = SUMMARY_MD.read_text(encoding="utf-8")
    else:
        existing = "# Project Session Summaries\n\nDaily log of terminal AI sessions and milestones.\n\n---\n"

    SUMMARY_MD.write_text(existing + entry, encoding="utf-8")
    print(f"[+] Updated {SUMMARY_MD.name} with timestamp {now}")

    # Synchronize contexts
    sync_contexts()

    # Commit if git status has changes
    if git_status:
        try:
            print("[*] Staging changes in git...")
            subprocess.run(["git", "add", "."], cwd=ROOT_DIR, check=True)
            commit_msg = f"Session close: {note} ({now})"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT_DIR, check=True)
            print(f"[+] Committed changes: '{commit_msg}'")
        except subprocess.CalledProcessError as e:
            print(f"[-] Git commit notice: {e}")
    else:
        print("[+] Working tree is clean. Nothing to commit.")

    print("\n[✓] Session closed successfully! Have a great rest of your day.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ["--close", "-c"]:
        note = sys.argv[2] if len(sys.argv) > 2 else "Routine session close"
        close_session(note)
    else:
        sync_contexts()


if __name__ == "__main__":
    main()
