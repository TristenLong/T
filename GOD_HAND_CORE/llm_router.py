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
# A custom OpenAI-compatible base lets a free/live key (e.g. OpenRouter or
# Puter) be used without code changes -- tool modules read this too.
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None

# Create a singleton client so we don't recreate it every call if we fall back
openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL) if OPENAI_API_KEY else None

# Puter (https://puter.com) exposes an OpenAI-compatible endpoint that works with
# a free auth token from https://puter.com/dashboard (API token section). No paid
# API keys needed; the token holder covers usage under puter's user-pays model.
PUTER_API_TOKEN = os.getenv("PUTER_AUTH_TOKEN") or os.getenv("PUTER_API_KEY") or None
PUTER_BASE_URL = os.getenv("JESTER_PUTER_BASE_URL", "https://api.puter.com/puterai/openai/v1")
# Default matches the renderer's PUTER_MODEL constant; the dated Gemini default
# made the router "use Puter" while asking Puter for a Gemini model every time.
PUTER_MODEL = os.getenv("JESTER_PUTER_MODEL", "z-ai/glm-5.3")

puter_client = OpenAI(api_key=PUTER_API_TOKEN, base_url=PUTER_BASE_URL) if PUTER_API_TOKEN else None

# Optional heavier local/cloud model for complex single-turn work (oh-my-codex
# style auto-routing). Empty by default; set JESTER_HEAVY_MODEL to enable it.
HEAVY_MODEL = os.getenv('JESTER_HEAVY_MODEL') or None

_COMPLEX_MARKERS = (
    'compare', 'explain why', 'debug', 'why is', 'how does', 'write a',
    'refactor', 'design', 'implement', 'analyze', 'summarize this', 'fix the',
    'evaluate', 'weigh', 'trade', 'strategy', 'architecture', 'performance',
    'security', 'review this',
)


def classify_complexity(text):
    """Coarse complexity estimate used to pick a heavier model when configured.

    'complex' for long or skill-heavy asks (debugging, design, analysis),
    'standard' for mid-length turns, 'trivial' for casual chat.
    """
    t = (text or '').lower()
    if len(t) > 700 or any(m in t for m in _COMPLEX_MARKERS):
        return 'complex'
    if len(t) > 250:
        return 'standard'
    return 'trivial'


def configure_puter(auth_token, model=None):
    """Arm Puter at runtime with a token obtained from the renderer's sign-in.

    Tool modules build OpenAI clients from OPENAI_* env vars at instantiation,
    so arming also sets those so every tool (coder, browser, etc.) routes
    through Puter's OpenAI-compatible endpoint instead of the dead API key.
    `model` (optional) is the Puter model to use, e.g. 'z-ai/glm-5.3'.
    """
    global puter_client, PUTER_API_TOKEN, PUTER_MODEL
    auth_token = (auth_token or "").strip()
    PUTER_API_TOKEN = auth_token
    puter_client = OpenAI(api_key=auth_token, base_url=PUTER_BASE_URL) if auth_token else None
    # Tools instantiate their own OpenAI clients from the OPENAI_* env vars at
    # construction time, so push the (possibly empty) Puter credentials onto the
    # environment here, not just onto this module's singleton. This is what
    # makes CoderCore/BrowserCore follow the armed-Puter route.
    os.environ['OPENAI_API_KEY'] = auth_token
    os.environ['OPENAI_BASE_URL'] = PUTER_BASE_URL if auth_token else ''
    os.environ['JESTER_OPENAI_MODEL'] = (model or PUTER_MODEL) if auth_token else os.getenv('JESTER_OPENAI_MODEL', 'gpt-4o')
    if model:
        model = (model or "").strip()
        PUTER_MODEL = model
        os.environ['JESTER_PUTER_MODEL'] = model
    return bool(puter_client)

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
    return bool(puter_client) or bool(openai_client) or is_ollama_available()


def tool_completion(messages, tools):
    """Completion that may return OpenAI-style tool_calls from the local model.

    `messages` is OpenAI-style ({"role", "content", ...}); `tools` is a list of
    OpenAI function-tool specs. Returns (content, tool_calls, model_name) where
    tool_calls is a list of {"id", "function": {"name", "arguments"}} or None.

    Routes Puter -> Ollama -> OpenAI, same order as normal completions, so
    the explicitly-armed cloud brain takes priority over the local model.

    Raises ValueError only when no backend can serve tool calls at all.
    """
    def extract(res):
        msg = res.choices[0].message
        content = msg.content or ""
        calls = None
        for tc in (msg.tool_calls or []):
            if calls is None:
                calls = []
            calls.append({
                "id": tc.id or "",
                "function": {"name": tc.function.name or "", "arguments": tc.function.arguments or "{}"},
            })
        return content, calls

    if puter_client:
        try:
            res = puter_client.chat.completions.create(model=PUTER_MODEL, messages=messages, tools=tools)
            content, calls = extract(res)
            return content, calls, f"puter:{PUTER_MODEL}"
        except Exception as e:
            logger.warning(f"Puter tool-call attempt failed: {e}. Falling back.")

    if is_ollama_available():
        try:
            client = OpenAI(api_key="ollama", base_url=f"{OLLAMA_HOST}/v1")
            res = client.chat.completions.create(model=DEFAULT_OLLAMA_MODEL, messages=messages, tools=tools)
            content, calls = extract(res)
            return content, calls, DEFAULT_OLLAMA_MODEL
        except Exception as e:
            logger.warning(f"Ollama tool-call attempt failed: {e}. Falling back.")
        _ollama_probe_cache["available"] = False

    if not openai_client:
        raise ValueError("Ollama is unavailable, Puter is unconfigured/unreachable, and OPENAI_API_KEY is not set.")

    res = openai_client.chat.completions.create(model=OPENAI_MODEL, messages=messages, tools=tools)
    content, calls = extract(res)
    return content, calls, OPENAI_MODEL


def generate_completion_with_model(messages, require_json=False):
    """Same as generate_completion but returns (text, model_name).

    Callers that report a model name to the UI need to know which backend
    actually answered; the previous single-return signature forced them to guess.
    `messages` format: [{"role": "user", "content": "..."}]
    """

    # 1. Armed Puter is the user's explicit choice (CONNECT PUTER); try it first.
    if puter_client:
        logger.info(f"Executing via Puter ({PUTER_MODEL}).")
        kwargs = {
            "model": PUTER_MODEL,
            "messages": messages
        }
        if require_json:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            res = puter_client.chat.completions.create(**kwargs)
            return res.choices[0].message.content, f"puter:{PUTER_MODEL}"
        except Exception as e:
            logger.warning(f"Puter execution failed: {e}. Falling back to Ollama.")

    # 2. Attempt Local Ollama Execution
    if is_ollama_available():
        complexity = classify_complexity(
            ' '.join(str(m.get('content', '')) for m in messages if m.get('role') in ('user', 'system'))[:2000]
        )
        ollama_model = HEAVY_MODEL if (HEAVY_MODEL and complexity in ('standard', 'complex')) else DEFAULT_OLLAMA_MODEL
        logger.info(f"Ollama detected. Routing to local model: {ollama_model} (complexity={complexity})")
        payload = {
            "model": ollama_model,
            "messages": messages,
            "stream": False
        }
        if require_json:
            payload["format"] = "json"

        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", ""), ollama_model
            logger.warning(f"Ollama failed with status {response.status_code}: {response.text}. Falling back to OpenAI.")
        except requests.RequestException as e:
            logger.warning(f"Ollama execution failed: {e}. Falling back to OpenAI.")
        # A live daemon that just errored should not keep winning the route for
        # the rest of the cache window.
        _ollama_probe_cache["available"] = False
    else:
        logger.info("Ollama is OFFLINE. Routing to cloud OpenAI.")

    # 3. Fallback to Cloud OpenAI
    if not openai_client:
        raise ValueError("Puter is unconfigured/unreachable, Ollama is unavailable, and OPENAI_API_KEY is not set.")

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
    """Yields (chunk, model_name) pairs, Puter first when armed, then Ollama, then OpenAI.

    Streaming previously bypassed this router entirely and talked straight to
    OpenAI, so an Ollama-only install could chat but never stream.
    """
    if puter_client:
        logger.info(f"Streaming via Puter ({PUTER_MODEL}).")
        try:
            stream = puter_client.chat.completions.create(
                model=PUTER_MODEL,
                messages=messages,
                stream=True,
            )
            for event in stream:
                if not event.choices:
                    continue
                chunk = event.choices[0].delta.content
                if chunk:
                    yield chunk, f"puter:{PUTER_MODEL}"
            return
        except Exception as e:
            logger.warning(f"Puter streaming failed: {e}. Falling back to Ollama/OpenAI.")

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
            logger.warning("Ollama stream produced no content. Falling back to Puter/OpenAI.")
        except requests.RequestException as e:
            # Only safe to fall back because nothing was emitted yet; if content
            # had already been yielded, restarting would duplicate it.
            logger.warning(f"Ollama streaming failed: {e}. Falling back to Puter/OpenAI.")
        _ollama_probe_cache["available"] = False
    else:
        logger.info("Ollama is OFFLINE. Streaming from cloud Puter/OpenAI.")

    if not openai_client and not puter_client:
        raise ValueError("Ollama is unavailable, Puter is unconfigured, and OPENAI_API_KEY is not set.")

    if not openai_client:
        raise ValueError("Ollama is unavailable, Puter is unconfigured/unreachable, and OPENAI_API_KEY is not set.")

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
