"""Manual check that the Gemini path actually emits a tool call.

The chat routing in server.py prefers Gemini precisely because it is the only
path that passes server_tools.AVAILABLE_TOOLS. This asserts that premise.

Run from anywhere:
    python GOD_HAND_CORE/test_tool.py
Exits non-zero if the model does not request the sandbox tool.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# server_tools lives next to this file, so make it importable regardless of the
# directory the script is invoked from. The previous version assumed the CWD.
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
from google import genai
from google.genai import types

import server_tools

# server.py loads ROOT/.env; check there first, then GOD_HAND_CORE/.env.
# The old code used a CWD-relative "GOD_HAND_CORE/.env" that only resolved when
# run from the repo root -- which is the one place the server_tools import fails.
for candidate in (os.path.join(ROOT_DIR, ".env"), os.path.join(BASE_DIR, ".env")):
    if os.path.exists(candidate):
        load_dotenv(candidate, override=False)

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("[SKIP] GEMINI_API_KEY not set; cannot exercise the live tool path.")
    sys.exit(0)

# Match the server's configured model instead of hardcoding a different one.
MODEL = os.getenv("JESTER_PRIMARY_LLM", "gemini-3.1-pro")

client = genai.Client(api_key=API_KEY)

chat = client.chats.create(
    model=MODEL,
    config=types.GenerateContentConfig(
        tools=server_tools.AVAILABLE_TOOLS,
        temperature=0.7,
    ),
)

print(f"[TEST] Model: {MODEL}")
print(f"[TEST] Tools registered: {len(server_tools.AVAILABLE_TOOLS)}")
print("[TEST] Sending message...")

response = chat.send_message(
    "Please use the execute_python_sandbox tool to print 'Hello World'"
)

print("[TEST] Response text:", response.text)

calls = response.function_calls or []
print("[TEST] Function calls:", [c.name for c in calls])

if not calls:
    print("[FAIL] Model returned no function call; tool support is not working.")
    sys.exit(1)

print("[PASS] Gemini emitted a tool call.")
