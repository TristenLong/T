import json
import logging
import os

import requests
from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger("LLM_ROUTER")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_OLLAMA_MODEL = "llama3.1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Create a singleton client so we don't recreate it every call if we fall back
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def is_ollama_available():
    """Checks if the local Ollama daemon is running."""
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=2)
        return res.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False

def generate_completion(messages, require_json=False):
    """
    Routes the request to Ollama first. If it fails or is offline, falls back to OpenAI.
    `messages` format: [{"role": "user", "content": "..."}]
    """
    
    # 1. Attempt Local Ollama Execution
    if is_ollama_available():
        logger.info(f"Ollama detected. Routing to local model: {DEFAULT_OLLAMA_MODEL}")
        payload = {
            "model": DEFAULT_OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        }
        if require_json:
            payload["format"] = "json"
            
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")
            else:
                logger.warning(f"Ollama failed with status {response.status_code}: {response.text}. Falling back to OpenAI.")
        except Exception as e:
            logger.warning(f"Ollama execution failed: {e}. Falling back to OpenAI.")
    else:
        logger.info("Ollama is OFFLINE. Routing to cloud OpenAI.")
        
    # 2. Fallback to Cloud OpenAI
    if not openai_client:
        raise ValueError("Ollama is unavailable and OPENAI_API_KEY is not set.")
        
    logger.info("Executing via OpenAI GPT-4o.")
    kwargs = {
        "model": "gpt-4o",
        "messages": messages
    }
    if require_json:
        kwargs["response_format"] = {"type": "json_object"}
        
    res = openai_client.chat.completions.create(**kwargs)
    return res.choices[0].message.content
