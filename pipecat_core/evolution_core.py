import os
import json
import asyncio
import genesis_core
import memory_core
from openai import OpenAI
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EVOLUTION_FLAG = os.path.join(ROOT_DIR, "EVOLUTION_ACTIVE")

if not os.path.exists(EVOLUTION_FLAG):
    with open(EVOLUTION_FLAG, "w") as f: f.write("TRUE")

def attempt_evolution():
    if not os.path.exists(EVOLUTION_FLAG):
        return "EVOLUTION_PAUSED"

    # Minimal logic: Check memory for failure patterns
    # In a real infinite loop, we would scan logs more deeply.
    # For this demo, we check if we lack a "joke" tool (just as a test) or respond to explicit memory triggers.
    
    if not OPENAI_API_KEY: return "NO_KEY"
    
    # We rely on the LLM in bot.py to trigger specific "create_tool" calls usually,
    # but here we actively propose one if memory suggests it.
    return "MONITORING"
