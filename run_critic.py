#!/usr/bin/env python3
"""
run_critic.py
Terminal Runner for the Brutal Critic (Anti-Gaslighting Reviewer)
Inspired by NetworkChuck's terminal workflow.
Reads the specified file or prompt and evaluates it using the 3-lens harsh review rubric.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROMPT_TEMPLATE = """
You are the BRUTAL CRITIC. Eliminate all sycophancy, polite sugar-coating, and false praise.
Evaluate the following content through THREE distinct harsh perspectives:

1. THE SYSTEMS ARCHITECT (Structure & Logic):
   - Attack logic flaws, edge cases, missing failure modes, and architectural fragility.
2. THE USER RETENTION AUDITOR (Friction & Bloat):
   - Attack feature dumps, unnecessary complexity, and user drop-off points.
3. THE SECURITY & PERFORMANCE SENTRY (Resource & Breakpoints):
   - Attack rate limits, memory leaks, security oversights, and scale bottlenecks.

OUTPUT REQUIREMENTS:
- Overall Grade: Strict 1.0 to 10.0 score (be hard to please, 8+ must be extraordinary)
- Top 3 Fatal Flaws
- The Unvarnished Roast
- Prioritized Action Plan (exact numbered fixes)

--- CONTENT TO REVIEW ---
{content}
-------------------------
"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_critic.py <path-to-file-or-text>")
        sys.exit(1)

    target_path = Path(sys.argv[1])
    if target_path.exists() and target_path.is_file():
        content = target_path.read_text(encoding="utf-8", errors="replace")
        print(f"[*] Loaded file '{target_path}' ({len(content)} chars)")
    else:
        content = " ".join(sys.argv[1:])
        print(f"[*] Reviewing input text ({len(content)} chars)")

    prompt = PROMPT_TEMPLATE.format(content=content)

    # Check available engines: google.genai, openai, or local ollama
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key:
        print("[*] Launching Brutal Critic via Gemini Engine...")
        from google import genai
        client = genai.Client(api_key=gemini_key)
        for model_name in ["gemini-3.1-pro-preview", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                print(f"\n[+] Evaluated with model: {model_name}")
                print("\n" + "=" * 50)
                print("         BRUTAL CRITIC ASSESSMENT")
                print("=" * 50 + "\n")
                print(response.text)
                return
            except Exception as e:
                print(f"[-] Model {model_name} notice: {e}")


    if openai_key:
        print("[*] Launching Brutal Critic via OpenAI Engine...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
            )
            print("\n" + "=" * 50)
            print("         BRUTAL CRITIC ASSESSMENT")
            print("=" * 50 + "\n")
            print(response.choices[0].message.content)
            return
        except Exception as e:
            print(f"[-] OpenAI call fallback: {e}")

    print("[-] Notice: No API key found or call failed. You can also run the agent in Claude Code using:")
    print("    claude -> '/agent brutal-critic review <file>'")


if __name__ == "__main__":
    main()
