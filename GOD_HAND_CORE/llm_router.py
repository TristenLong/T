import json
import logging
import os
import time

import requests
from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger("LLM_ROUTER")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

OLLAMA_HOST = os.getenv("JESTER_OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"
DEFAULT_OLLAMA_MODEL = os.getenv("JESTER_OLLAMA_MODEL", "llama3.1")
# Was hardcoded to "gpt-4o" at the call site, which made the model name the rest
# of the app reports to the client a guess rather than a fact.
OPENAI_MODEL = os.getenv("JESTER_OPENAI_MODEL", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Create a singleton client so we don't recreate it every call if we fall back
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# The availability probe used to run on every single completion, adding up to a
# 2s stall per request whenever Ollama was not installed. Cache the verdict for
# a short window so a daemon that starts or stops is still picked up promptly.
_OLLAMA_PROBE_TTL = float(os.getenv("JESTER_OLLAMA_PROBE_TTL", "30"))
_ollama_probe_cache = {"checked_at": 0.0, "available": False}


def is_ollama_available(force=False):
    """Checks if the local Ollama daemon is running (result cached briefly)."""
    now = time.monotonic()
    if not force and (now - _ollama_probe_cache["checked_at"]) < _OLLAMA_PROBE_TTL:
        return _ollama_probe_cache["available"]

    try:
        res = requests.get(OLLAMA_TAGS_URL, timeout=2)
        available = res.status_code == 200
    except requests.RequestException:
        available = False

    _ollama_probe_cache["checked_at"] = now
    _ollama_probe_cache["available"] = available
    return available

def is_available():
    """True when at least one backend can serve a completion."""
    return bool(openai_client) or is_ollama_available()


def generate_completion_with_model(messages, require_json=False):
    """Same as generate_completion but returns (text, model_name).

    Callers that report a model name to the UI need to know which backend
    actually answered; the previous single-return signature forced them to guess.
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
                return data.get("message", {}).get("content", ""), DEFAULT_OLLAMA_MODEL
            logger.warning(f"Ollama failed with status {response.status_code}: {response.text}. Falling back to OpenAI.")
        except requests.RequestException as e:
            logger.warning(f"Ollama execution failed: {e}. Falling back to OpenAI.")
        # A live daemon that just errored should not keep winning the route for
        # the rest of the cache window.
        _ollama_probe_cache["available"] = False
    else:
        logger.info("Ollama is OFFLINE. Routing to cloud OpenAI.")

    # 2. Fallback to Cloud OpenAI
    if not openai_client:
        raise ValueError("Ollama is unavailable and OPENAI_API_KEY is not set.")

    logger.info(f"Executing via OpenAI ({OPENAI_MODEL}).")
    kwargs = {
        "model": OPENAI_MODEL,
        "messages": messages
    }
    if require_json:
        kwargs["response_format"] = {"type": "json_object"}

    res = openai_client.chat.completions.create(**kwargs)
    return res.choices[0].message.content, OPENAI_MODEL


def generate_completion(messages, require_json=False):
    """Routes to Ollama first, falling back to OpenAI. Returns text only."""
    text, _model = generate_completion_with_model(messages, require_json=require_json)
    return text


def stream_completion(messages, require_json=False):
    """Yields (chunk, model_name) pairs, Ollama first then OpenAI.

    Streaming previously bypassed this router entirely and talked straight to
    OpenAI, so an Ollama-only install could chat but never stream.
    """
    if is_ollama_available():
        logger.info(f"Ollama detected. Streaming from local model: {DEFAULT_OLLAMA_MODEL}")
        payload = {
            "model": DEFAULT_OLLAMA_MODEL,
            "messages": messages,
            "stream": True
        }
        if require_json:
            payload["format"] = "json"

        try:
            emitted = False
            with requests.post(OLLAMA_URL, json=payload, timeout=120, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except ValueError:
                        continue
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        emitted = True
                        yield chunk, DEFAULT_OLLAMA_MODEL
                    if data.get("done"):
                        break
            if emitted:
                return
            logger.warning("Ollama stream produced no content. Falling back to OpenAI.")
        except requests.RequestException as e:
            # Only safe to fall back because nothing was emitted yet; if content
            # had already been yielded, restarting would duplicate it.
            logger.warning(f"Ollama streaming failed: {e}. Falling back to OpenAI.")
        _ollama_probe_cache["available"] = False
    else:
        logger.info("Ollama is OFFLINE. Streaming from cloud OpenAI.")

    if not openai_client:
        raise ValueError("Ollama is unavailable and OPENAI_API_KEY is not set.")

    logger.info(f"Streaming via OpenAI ({OPENAI_MODEL}).")
    stream = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        stream=True,
    )
    for event in stream:
        if not event.choices:
            continue
        chunk = event.choices[0].delta.content
        if chunk:
            yield chunk, OPENAI_MODEL
