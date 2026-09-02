import logging
import os
import re
import socket
import sqlite3
import time

import requests

import graph_memory
import jester_auth

# Suppress GRPC warnings
os.environ["GRPC_VERBOSITY"] = "ERROR"
import asyncio
import inspect
import json
import random
import threading
import typing
import queue
from datetime import datetime

import chromadb
import psutil
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from google import genai
from google.genai import types
from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from llm_router import (
    DEFAULT_OLLAMA_MODEL as OLLAMA_MODEL,
    generate_completion_with_model,
    is_available as llm_router_available,
    is_ollama_available as llm_router_ollama_available,
    stream_completion,
)
from mcp_client_core import run_mcp_tool
from sandbox_core import sandbox_core
from vision_core import vision_core

# --- Global Caches ---
semantic_cache: typing.Dict[str, typing.Any] = {
    'vectorizer': None,
    'tfidf_docs': None,
    'docs': [],
    # Set by save_memory; consumed by semantic_search_memory so the expensive
    # TF-IDF refit happens once per search rather than once per saved message.
    'dirty': False
}

class EventBroadcaster:
    """Fan-out for server-sent events.

    This was a single shared queue.Queue that every /api/stream_events client
    called get() on. queue.get() *removes* the item, so with more than one
    listener (the Electron HUD plus the browser extension, say) each event went
    to exactly one of them at random instead of all of them. Subscribers now get
    their own bounded queue and publishers write to every queue.
    """

    def __init__(self, maxsize=256):
        self._maxsize = maxsize
        self._subscribers: typing.Set[queue.Queue] = set()
        self._lock = threading.Lock()

    def subscribe(self):
        q: queue.Queue = queue.Queue(maxsize=self._maxsize)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._subscribers.discard(q)

    def put(self, message):
        with self._lock:
            targets = list(self._subscribers)
        for q in targets:
            try:
                q.put_nowait(message)
            except queue.Full:
                # A stalled client must not block the request that emitted the
                # event, and must not grow without bound. Drop its oldest item.
                try:
                    q.get_nowait()
                    q.put_nowait(message)
                except (queue.Empty, queue.Full):
                    pass


global_event_queue = EventBroadcaster()


# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
import sys

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)
try:
    from research_core import deep_research
    from xp_core import add_xp, get_stats

except ImportError as e:
    import logging
    logging.getLogger('SOURCE_CORE').error(f"Failed to import from core: {e}")
    deep_research = lambda q: f"Research Error: Module not found"
    add_xp = lambda x: (0, 1, False)
    get_stats = lambda: {"xp": 0, "level": 1}

DB_FILE = os.path.join(BASE_DIR, 'jester_V73_OMNIPRESENCE.db')

# Load .env from root
load_dotenv(os.path.join(ROOT_DIR, '.env'), override=True)

app = Flask(__name__)

# CORS was previously `CORS(app)`, which allows EVERY origin. Combined with the
# unauthenticated /api/sandbox and /api/execute_tool endpoints below, that let
# any website the user happened to visit execute arbitrary code on this machine
# via a cross-origin fetch to localhost. Restrict to the local dev server and
# the browser extension, which are the only legitimate cross-origin callers.
# (The React app reaches Flask through Vite's server-side proxy, which sends no
# browser Origin, so it is unaffected by this list.)
CORS(app, origins=[
    re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"),
    re.compile(r"^chrome-extension://[a-p]+$"),
], allow_headers=["Content-Type", jester_auth.TOKEN_HEADER], supports_credentials=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SOURCE_CORE')

# --- Authentication -------------------------------------------------------
# Loopback binding keeps other machines out, but every process and browser
# extension on this machine could still reach /api/sandbox (arbitrary Python),
# /api/execute_tool (arbitrary subprocess, mouse and keyboard) and the full chat
# history. Require a shared token that only filesystem-capable callers can read.
API_TOKEN = jester_auth.load_token(create=True)
AUTH_ENFORCED = jester_auth.auth_required()

# Endpoints reachable without a token. Deliberately tiny: /api/pulse is the
# liveness probe the launcher and clients poll before they have a token, and it
# returns nothing sensitive (CPU, RAM, model name). Everything else -- including
# read-only history, which is private conversation data -- requires the token.
AUTH_EXEMPT_PATHS = frozenset({'/api/pulse'})


@app.before_request
def enforce_api_token():
    # Preflight carries no credentials by design; flask-cors answers it.
    if request.method == 'OPTIONS':
        return None
    if not AUTH_ENFORCED or not API_TOKEN:
        return None
    if not request.path.startswith('/api/') or request.path in AUTH_EXEMPT_PATHS:
        return None

    supplied = request.headers.get(jester_auth.TOKEN_HEADER)
    if not supplied:
        # EventSource cannot set headers. The React app sidesteps this because
        # Vite's proxy injects the header server-side, but a direct SSE consumer
        # has no alternative to the query string.
        supplied = request.args.get(jester_auth.TOKEN_QUERY_PARAM)

    if jester_auth.token_matches(supplied, API_TOKEN):
        return None

    logger.warning(
        f'REJECTED UNAUTHENTICATED {request.method} {request.path} '
        f'from {request.remote_addr} (origin={request.headers.get("Origin", "-")})'
    )
    return jsonify({
        'error': 'UNAUTHORIZED',
        'detail': (
            f'Send the shared token in the {jester_auth.TOKEN_HEADER} header. '
            f'It is stored at {jester_auth.TOKEN_FILE}.'
        ),
    }), 401


if not AUTH_ENFORCED:
    logger.warning(
        'JESTER_REQUIRE_AUTH is off -- code-execution endpoints are open to '
        'every process and browser extension on this machine.'
    )
elif not API_TOKEN:
    logger.error(
        'No API token could be loaded or created; authentication is INACTIVE. '
        f'Check write access to {jester_auth.TOKEN_FILE}.'
    )
else:
    logger.info(f'API AUTH ACTIVE. Token file: {jester_auth.TOKEN_FILE}')


def get_swarm_data():
    try:
        import sub_agent_core
        agents = sub_agent_core.list_active_agents()
        subagents = [f"Agent {aid} ({data['type']}): {data['status']}" for aid, data in agents.items()]
        return {
            'swarm_status': 'ACTIVE' if agents else 'IDLE',
            'subagents': subagents if subagents else ['No active sub-agents'],
            'status': 'SINGULARITY_ONLINE'
        }
    except Exception as e:
        return {
            'swarm_status': 'ERROR',
            'subagents': [f'Error: {e}'],
            'status': 'SINGULARITY_OFFLINE'
        }


GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PRIMARY_MODEL = os.getenv('JESTER_PRIMARY_LLM', 'gemini-3.1-pro')
OPENAI_MODEL = os.getenv('JESTER_OPENAI_MODEL', 'gpt-4o')

gemini_client = None
openai_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f'GEMINI CLIENT INITIALIZED. MODEL: {PRIMARY_MODEL}')
    except Exception as e:
        logger.error(f'GEMINI INIT FAILED: {str(e)}')

if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=os.getenv("OPENAI_BASE_URL") or None)
        logger.info(f'OPENAI CLIENT INITIALIZED. MODEL: {OPENAI_MODEL}')
    except Exception as e:
        logger.error(f'OPENAI INIT FAILED: {str(e)}')


def active_model_name():
    """Best guess at the model that would answer the next turn.

    Status endpoints used to report `PRIMARY_MODEL if gemini_client else
    OPENAI_MODEL`, which showed "gpt-4o" on an Ollama-only install that never
    touches OpenAI, and "gemini-2.5-flash" when a dead/exhausted key was present
    even after the user armed Puter. Puter is what the CONNECT PUTER flow arms,
    so an armed Puter backend is reported as the active model first. The Ollama
    probe is cached, so this is cheap to call.
    """
    import llm_router
    if llm_router.puter_client:
        return f"puter:{llm_router.PUTER_MODEL}"
    if llm_router_ollama_available():
        return OLLAMA_MODEL
    if gemini_client:
        return PRIMARY_MODEL
    if openai_client:
        return OPENAI_MODEL
    return 'OFFLINE'


def llm_router_puter_armed():
    import llm_router
    return bool(getattr(llm_router, 'puter_client', None))


def llm_router_puter_model():
    import llm_router
    return getattr(llm_router, 'PUTER_MODEL', None) or 'z-ai/glm-5.3'

# --- Memory Modules ---
try:
    import chromadb
    chroma_client = chromadb.PersistentClient(path=os.path.join(BASE_DIR, 'chroma_db'))
    jester_collection = chroma_client.get_or_create_collection(name="jester_memory")
    CHROMA_ENABLED = True
    logger.info("CHROMA VECTOR MEMORY ONLINE.")
except Exception as e:
    logger.warning(f"ChromaDB not available ({e}). Falling back to TF-IDF.")
    CHROMA_ENABLED = False

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # WAL lets the SSE thread and request handlers read while a write is in
        # flight; the default rollback journal serialises them and produced
        # "database is locked" errors under concurrent chats.
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, pinned INTEGER DEFAULT 0, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        # Every query in this module filters or orders by role/id; without this
        # the semantic-cache refresh scans the whole table.
        c.execute('CREATE INDEX IF NOT EXISTS idx_history_role_id ON history (role, id DESC)')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f'DB INIT ERROR: {e}')

def save_memory(role, content):
    try:
        # 1. Try Neo4j Graph Memory first
        if graph_memory.save_memory(role, content):
            pass # successfully saved to graph

        # 2. Always save to SQLite for backup
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO history (role, content) VALUES (?, ?)', (role, content))
        record_id = c.lastrowid
        conn.commit()
        conn.close()

        # Save to Chroma
        if CHROMA_ENABLED and role == 'user':
            jester_collection.add(
                documents=[content],
                metadatas=[{"role": role}],
                ids=[str(record_id)]
            )
        elif not CHROMA_ENABLED:
            # Only flag the cache stale. This used to refit TF-IDF over 500
            # documents on *every* save -- twice per chat turn -- even though
            # nothing read the result until the next search.
            semantic_cache['dirty'] = True
    except Exception as e:
        logger.error(f'SAVE_MEMORY ERROR: {e}')

def refresh_semantic_cache():
    if CHROMA_ENABLED: return
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT content FROM history WHERE role="user" ORDER BY id DESC LIMIT 500')
        rows = c.fetchall()
        conn.close()

        semantic_cache['dirty'] = False
        if not rows:
            semantic_cache['docs'] = []
            semantic_cache['vectorizer'] = None
            semantic_cache['tfidf_docs'] = None
            return

        docs = [r[0] for r in rows]
        vectorizer = TfidfVectorizer()
        # fit_transform does one pass instead of fit-then-transform's two.
        tfidf_docs = vectorizer.fit_transform(docs)

        semantic_cache['vectorizer'] = vectorizer
        semantic_cache['tfidf_docs'] = tfidf_docs
        semantic_cache['docs'] = docs
    except Exception as e:
        # Was a bare `pass`, which hid schema and sklearn errors entirely.
        logger.warning(f'SEMANTIC CACHE REFRESH FAILED: {e}')

def load_memories(limit=10):
    try:
        # 1. Try Neo4j Graph Memory first
        graph_mem = graph_memory.load_memories(limit)
        if graph_mem is not None:
            return graph_mem
            
        # 2. Fallback to SQLite
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT role, content FROM history ORDER BY id DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        history = []
        for row in reversed(rows):
            role = 'user' if row[0] == 'user' else 'model'
            history.append({'role': role, 'parts': [{'text': row[1]}]})
        return history
    except Exception as e:
        return []

def semantic_search_memory(query, top_k=3):
    try:
        # 1. Try Neo4j Graph Memory Search
        graph_results = graph_memory.semantic_search(query, top_k)
        if graph_results:
            return graph_results
            
        # 2. Fallback to Chroma
        if CHROMA_ENABLED:
            results = jester_collection.query(query_texts=[query], n_results=top_k)
            if results and results['documents'] and results['documents'][0]:
                docs = results['documents'][0]
                relevant = [d for d in docs if len(d) > 10]
                if relevant:
                    return "RECALLED PAST CONTEXT: " + " | ".join(relevant)
            return ""
        else:
            # TF-IDF Fallback -- rebuild here (lazily) if saves marked it stale.
            if semantic_cache.get('dirty'):
                refresh_semantic_cache()
            docs = semantic_cache['docs']
            if not docs or not semantic_cache['vectorizer']:
                return ""
            vectorizer = semantic_cache['vectorizer']
            tfidf_docs = semantic_cache['tfidf_docs']
            tfidf_query = vectorizer.transform([query])
            cosine_sim = cosine_similarity(tfidf_query, tfidf_docs).flatten()
            top_indices = cosine_sim.argsort()[-top_k:][::-1]
            relevant = [docs[i] for i in top_indices if cosine_sim[i] > 0.1]
            if relevant:
                return "RECALLED PAST CONTEXT: " + " | ".join(relevant)
            return ""
    except Exception as e:
        logger.error(f"SEMANTIC SEARCH ERROR: {e}")
        return ""

init_db()
if not CHROMA_ENABLED:
    refresh_semantic_cache()


def _to_router_messages(messages, sys_prompt):
    """Flatten Gemini-shaped history into the router's OpenAI-style messages."""
    msgs = [{'role': 'system', 'content': str(sys_prompt)}]
    for m in messages:
        role = 'user' if m['role'] == 'user' else 'assistant'
        parts = m.get('parts') or [{}]
        msgs.append({'role': role, 'content': str(parts[0].get('text', ''))})
    return msgs


def _build_openai_tools(functions):
    """Convert Tool Arsenal callables into OpenAI function-tool schemas."""
    tools = []
    for fn in functions:
        sig = inspect.signature(fn)
        properties = {}
        required = []
        for name, param in sig.parameters.items():
            if name in ('self', 'cls'):
                continue
            ann = param.annotation
            if ann is int:
                ptype = 'integer'
            elif ann is float:
                ptype = 'number'
            elif ann is bool:
                ptype = 'boolean'
            elif ann is dict:
                ptype = 'object'
            else:
                ptype = 'string'
            properties[name] = {'type': ptype}
            if param.default is inspect.Parameter.empty:
                required.append(name)
        tools.append({
            'type': 'function',
            'function': {
                'name': fn.__name__,
                'description': ((fn.__doc__ or '').strip().splitlines() or [''])[0],
                'parameters': {
                    'type': 'object',
                    'properties': properties,
                    'required': required,
                },
            },
        })
    return tools


def _agent_events(messages, sys_prompt, max_iters=2):
    """Agentic fallback chat: let the LLM call Tool Arsenal functions.

    Yields dict events: {'text': str, 'model': str} for content and
    {'tool': {'name', 'status', 'info'}} for tool activity. Degrades to a
    plain streamed reply when the active provider cannot do tool-calling.

    ONLY the safe subset is offered to the model. Local 3B models cannot be
    trusted with keystroke/mouse/code tools (system_control, computer_use,
    sandbox): they have been observed calling them for unrelated questions,
    which drives the real keyboard and mouse. Those stay Arsenal-only.
    """
    import server_tools
    import llm_router

    safe_tools = [
        fn for fn in server_tools.AVAILABLE_TOOLS
        if fn.__name__ not in {
            'system_control', 'execute_computer_use', 'start_visual_autopilot',
            'execute_python_sandbox', 'dispatch_browser_swarm',
            'analyze_screen', 'dispatch_mcp_swarm', 'run_rovo_dev', 'optimize_system',
        }
    ]
    msgs = _to_router_messages(messages, sys_prompt)
    tools = _build_openai_tools(safe_tools)
    tool_names = ", ".join(t['function']['name'] for t in tools)
    caller_note = (
        f"\n\nYou run on the God Hand command deck and HAVE working tools at your disposal, so never claim otherwise. "
        f"When the user asks you to ACT, call the matching tool via function calling, then answer from its real result. "
        f"Choose the most direct tool: "
        f"'open X'/'launch X'/'start X' -> open_app_or_url; "
        f"'find X'/'what apps'/'list installed apps'/'installed software' -> list_apps (pass the app name as filter if given); "
        f"'search ...'/'look up' -> search_web or conduct_deep_research; "
        f"'diagnostics'/'run system status'/'health check'/'test tools'/'fix my setup' -> diagnostics_report; "
        f"'reddit X'/'subreddit X' -> check_reddit; "
        f"'code X'/'build X'/'write X X'/'create X X'/'fix the bug in <path>'/'repair <path>'/'add feature to <path>' -> dispatch_coder_swarm (pass the full file path as `path` when the user names one, `execute=True` only if asked to run it); "
        f"Otherwise do NOT call a tool -- just answer the user's message directly. "
        f"Do NOT invent numbers; quote only what the tool returns. "
        f"After at most one tool call, stop calling tools and give your answer immediately. "
        f"Available tools: {tool_names}."
    )
    msgs[0] = {'role': 'system', 'content': str(msgs[0]['content']) + caller_note}

    for _ in range(int(max_iters)):
        try:
            content, calls, model = llm_router.tool_completion(msgs, tools)
        except Exception as e:
            logger.warning(f'TOOL CALLING UNSUPPORTED, PLAIN STREAM FALLBACK: {e}')
            for chunk, m in stream_completion(msgs):
                yield {'text': chunk, 'model': m}
            return
        if content:
            yield {'text': content, 'model': model}
        if not calls:
            return

        msgs.append({
            'role': 'assistant',
            'content': content or '',
            'tool_calls': [
                {'id': c['id'], 'type': 'function',
                 'function': {'name': c['function']['name'], 'arguments': c['function']['arguments']}}
                for c in calls
            ],
        })
        for c in calls:
            name = c['function']['name']
            try:
                args = json.loads(c['function']['arguments'] or '{}')
            except (json.JSONDecodeError, ValueError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            yield {'tool': {'name': name, 'status': 'RUN'}}
            fn = getattr(server_tools, name, None)
            if fn is None:
                out = f'UNKNOWN TOOL: {name}'
            else:
                # Small local models routinely invent parameters (e.g. action=)
                # that the tool does not declare, or omit required ones (e.g.
                # dispatch_coder_swarm's `prompt`). Only forward arg keys the
                # callable actually accepts; for a missing required param,
                # synthesize it from the latest user message so the call still
                # does the right thing instead of dying on a TypeError.
                try:
                    sig = inspect.signature(fn)
                    params = set(sig.parameters)
                    val_args = {k: v for k, v in args.items() if k in params}
                    required_missing = [
                        p for p, prm in sig.parameters.items()
                        if prm.default is inspect.Parameter.empty
                        and p not in val_args
                    ]
                    if required_missing:
                        last_user = next(
                            (m.get('content') for m in reversed(msgs)
                             if m.get('role') == 'user' and m.get('content')),
                            ''
                        )
                        last_user = str(last_user)[:1500] or f'Perform the {name} task.'
                        for p in required_missing:
                            val_args[p] = last_user
                    out = fn(**val_args) if val_args else fn()
                except TypeError as te:
                    out = f'Error (bad arguments for {name}): {te}'
                except Exception as ex:
                    out = f'Error: {ex}'
            out = str(out)
            yield {'tool': {'name': name, 'status': 'DONE', 'info': out[:400]}}
            msgs.append({'role': 'tool', 'tool_call_id': c['id'], 'name': name, 'content': out[:3000]})

    # The model kept calling tools without answering — force a final
    # summarizing pass so we never return empty-handed.
    msgs.append({
        'role': 'user',
        'content': 'You have used all your tool steps. Now summarize the tool results above and give your final answer to the user. Do not call any more tools.'
    })
    try:
        final_text, model = llm_router.generate_completion_with_model(msgs)
        yield {'text': final_text, 'model': model}
    except Exception as e:
        logger.error(f'FORCED SUMMARIZATION PASS FAILED: {e}')
        yield {'text': '[Tools completed, but the final answer failed to generate. Try again or rephrase.]', 'model': 'NONE'}


def _agent_text(messages, sys_prompt, max_iters=3):
    """Non-streaming agentic completion. Returns (text, model_name)."""
    full = []
    model = 'NONE'
    for ev in _agent_events(messages, sys_prompt, max_iters):
        if 'text' in ev:
            full.append(ev['text'])
            model = ev['model']
    return ''.join(full), model


def _is_quota_exhausted(e):
    """True when a Gemini error is a 429 quota/rate-limit, which backoff can't fix.

    Skipping the retry sleep here is what lets an exhausted free tier fall through
    to Puter/OpenAI quickly instead of stalling each request for several seconds.
    """
    code = getattr(e, 'status_code', None)
    if code is None:
        code = getattr(e, 'code', None)
    if code is not None:
        try:
            return int(code) == 429
        except (TypeError, ValueError):
            pass
    msg = str(e)
    return 'RESOURCE_EXHAUSTED' in msg or '429' in msg or 'quotaExceeded' in msg


def generate_fallback_response(messages, sys_prompt, max_retries=3):
    """Non-Gemini completion via the LLM router. Returns (text, model_name).

    Named for what it is rather than "openai": the router prefers a local Ollama
    daemon and only reaches for OpenAI when that is unavailable. The old version
    asserted `openai_client is not None` here, which made an Ollama-only install
    fail three times with backoff before raising -- even though the router it
    then called would have served the request locally without a key.
    """
    msgs = _to_router_messages(messages, sys_prompt)

    for attempt in range(max(1, max_retries)):
        try:
            return generate_completion_with_model(msgs)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"OLLAMA/OPENAI API RATE LIMIT/ERROR (Attempt {attempt+1}): {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f'OLLAMA/OPENAI ERROR: {e}')
                raise
    raise RuntimeError("Fallback response failed")

def generate_gemini_response(sys_prompt, history, msg, max_retries=3):
    for attempt in range(max_retries):
        import server_tools

        try:
            assert gemini_client is not None
            chat = gemini_client.chats.create(
                model=PRIMARY_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=sys_prompt,
                    tools=server_tools.AVAILABLE_TOOLS,
                    temperature=0.7
                ),
                history=history
            )
            return chat.send_message(msg).text
        except Exception as e:
            if _is_quota_exhausted(e):
                logger.error(f'GEMINI QUOTA EXHAUSTED, FALLING THROUGH: {e}')
                raise e
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"GEMINI API RATE LIMIT/ERROR (Attempt {attempt+1}): {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f'GEMINI ERROR: {e}')
                raise e

@app.route('/api/vision', methods=['POST'])
def api_vision():
    data = request.json
    action = data.get('action', 'capture')
    if action == 'capture':
        return jsonify({"image": vision_core.capture_screen()})
    elif action == 'extract':
        return jsonify({"text": vision_core.extract_text()})
    return jsonify({"error": "Unknown vision action"}), 400

@app.route('/api/sandbox', methods=['POST'])
def api_sandbox():
    data = request.json
    code = data.get('code', '')
    result = sandbox_core.execute_python_code(code)
    return jsonify(result)

@app.route('/api/ai_state', methods=['GET', 'POST'])
def api_ai_state():
    """Report (and optionally probe) the backend's AI provider state WITHOUT
    exposing the actual token. probe=1 fires a $0 PUT-request against the same
    OpenAI-compatible endpoint the Tool Arsenal uses, so a failed tool can be
    diagnosed as 'provider dead' vs 'never armed' without leaking the key.
    """
    import llm_router
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    base = os.environ.get('OPENAI_BASE_URL', '')
    model = os.environ.get('JESTER_OPENAI_MODEL', '')
    armed = bool(openai_key) and bool(base)
    state = {
        'armed': armed,
        'providers': {
            'puter_backend': bool(llm_router.puter_client),
            'openai_key': bool(openai_key),
            'openai_base': base or '(default api.openai.com)',
            'is_puter': 'puter' in base,
            'model': model or os.getenv('JESTER_PRIMARY_LLM'),
        },
        'is_puter': 'puter' in base,
    }
    do_probe = (request.json or {}).get('probe', False) if request.method == 'POST' else False
    if do_probe and openai_key:
        try:
            from openai import OpenAI
            probe = OpenAI(api_key=openai_key, base_url=base)
            resp = probe.chat.completions.create(
                model=model or 'gpt-4o',
                messages=[{'role': 'user', 'content': 'ping'}],
                max_tokens=5,
            )
            state['probe'] = {'ok': True, 'reply': (resp.choices[0].message.content or '')[:60]}
        except Exception as e:
            state['probe'] = {'ok': False, 'error': str(e)[:160]}
    elif do_probe:
        state['probe'] = {'ok': False, 'error': 'NOT_ARMED'}
    return jsonify(state)

@app.route('/api/execute_tool', methods=['POST'])
def execute_tool():
    """Kill-switch-safe single dispatch for the Arsenal buttons.

    Every toolbar tool_id maps to exactly one server_tools function (or a thin
    arg adapter). All real work lives in server_tools so there is one
    implementation per capability instead of a chain of duplicated branches.
    """
    try:
        import server_tools

        data = request.json
        tool_id = data.get('tool_id')
        cmd = data.get('cmd', '')
        args = data.get('args') or {}

        import re

        def subreddit_from(text):
            m = re.search(r'r/(\w+)', text or '')
            return m.group(1) if m else (text or '').strip()

        result = "Action triggered."
        dispatch = {
            'coder_swarm': lambda: server_tools.dispatch_coder_swarm(cmd or 'write a python script', path=args.get('path', ''), execute=bool(args.get('execute', False))),
            'computer_use': lambda: server_tools.execute_computer_use(args.get('action', 'click'), args),
            'vision_screen': lambda: server_tools.analyze_screen(cmd or 'Describe the current screen'),
            'vision_ocr': lambda: server_tools.ocr_screen(cmd),
            'webcam_optics': lambda: server_tools.capture_webcam_analysis(cmd or 'Describe what the webcam sees in detail.'),
            'deep_research': lambda: server_tools.conduct_deep_research(cmd),
            'reddit_intel': lambda: server_tools.check_reddit(subreddit_from(cmd) or 'singularity'),
            'knowledge_graph': lambda: server_tools.query_knowledge_graph(cmd),
            'offline_brain': lambda: server_tools.switch_to_offline(cmd or 'status'),
            'sandbox_execute': lambda: server_tools.execute_python_sandbox(cmd),
            'browser_swarm': lambda: server_tools.dispatch_browser_swarm(cmd),
            'mcp_swarm': lambda: server_tools.dispatch_mcp_swarm(cmd),
            'auto_pilot': lambda: server_tools.start_visual_autopilot(cmd),
            'sys_optimize': lambda: server_tools.optimize_system('system'),
            'red_pill': lambda: "RED PILL TAKEN. Matrix decoded. You are now seeing the raw code.",
            'blue_pill': lambda: "BLUE PILL TAKEN. Ignorance is bliss. Re-entering simulation.",
            'mcp_execute': lambda: run_mcp_tool(
                args.get('command', 'npx'),
                args.get('args', ['-y', '@modelcontextprotocol/server-filesystem', 'C:\\']),
                args.get('tool_name', 'list_directory'),
                args.get('tool_args', {'path': 'C:\\'})),
        }

        if tool_id not in dispatch:
            return jsonify({'error': f'Unknown tool ID: {tool_id}'}), 400
        result = dispatch[tool_id]()

        try:
            new_xp, new_level, leveled_up = add_xp(10)
        except Exception as e:
            logger.error(f"XP ERROR: {e}")

        return jsonify({'status': 'SUCCESS', 'result': result})
    except Exception as e:
        logger.error(f'EXECUTE_TOOL_ERROR: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        msg = data.get('message', '')
        # Handle simple tool calls from frontend
        pill_type = 'blue'
        sys_prompt = 'You are JESTER V1000: THE GOD HAND. Mission: Break the simulation. '
        
        if msg == 'take_pill':
            tool_args = data.get('tool_args', {})
            pill_type = tool_args.get('pill_type', 'blue')
            msg = f'I choose the {pill_type} pill.'
            if pill_type == 'red':
                sys_prompt += 'MODE: RED PILL. Reveal deep, uncomfortable truths. Analyze the code. Wake them up.'
            else:
                sys_prompt += 'MODE: BLUE PILL. Comfort them. Restore the illusion. Status quo maintained.'
        
        history = load_memories()
        
        # Inject Semantic Context
        recalled_context = semantic_search_memory(msg)
        if recalled_context:
            sys_prompt += f"\n\n{recalled_context}"
            
        reply = ''
        used_model = 'NONE'

        # Multi-LLM Routing Logic
        # Only the Gemini path passes server_tools.AVAILABLE_TOOLS, so Gemini is
        # preferred whenever it is available -- regardless of intent. The router
        # (Ollama -> OpenAI) is a tool-less fallback used when Gemini is absent
        # or fails.
        coding_keywords = ['code', 'script', 'function', 'python', 'javascript', 'jsx', 'bug', 'fix']
        requires_coding = any(k in msg.lower() for k in coding_keywords)
        intent = 'CODE' if requires_coding else 'CHAT'

        # `openai_client` alone is the wrong availability test: the router serves
        # requests from a local Ollama daemon with no API key at all.
        fallback_available = llm_router_available()
        if not gemini_client and not fallback_available:
            return jsonify({'error': 'NO_LLM_AVAILABLE'}), 500

        force_tool = bool(data.get('force_tool') or data.get('tool_args'))
        fallback_payload = history + [{'role': 'user', 'parts': [{'text': msg}]}]

        # Plain chat goes straight to a tool-less fast completion (Puter ->
        # Ollama -> OpenAI). The agent loop is reserved for explicit action
        # requests, and even then only its safe tool subset is offered, so a
        # stray tool call can never type/press/click the real desktop.
        if force_tool:
            logger.info(f'ROUTING: {intent} INTENT -> AGENT LOOP (TOOLS ENABLED)')
            try:
                reply, used_model = _agent_text(fallback_payload, sys_prompt)
            except Exception as e:
                logger.warning(f'AGENT TEXT FAILED ({e}), FALLBACK TO FAST COMPLETION')
                msgs = _to_router_messages(fallback_payload, sys_prompt)
                reply, used_model = generate_completion_with_model(msgs)
        else:
            logger.info(f'ROUTING: {intent} INTENT -> LLM ROUTER (FAST, NO TOOLS)')
            msgs = _to_router_messages(fallback_payload, sys_prompt)
            reply, used_model = generate_completion_with_model(msgs)

        save_memory('user', msg)
        save_memory('model', reply)
        return jsonify({'response': reply, 'model': used_model})

    except Exception as e:
        logger.error(f'CHAT_ERROR: {str(e)}')
        return jsonify({'error': str(e)}), 500

def generate_fallback_stream(messages, sys_prompt, max_retries=3):
    """Yields (chunk, model_name) from the LLM router (Ollama -> OpenAI).

    Streaming used to call openai_client directly, bypassing the router, so an
    Ollama-only install could chat but never stream. It also retried after a
    partially consumed stream, which re-emitted every chunk already sent; the
    `emitted` guard below makes a failure mid-stream terminal instead.
    """
    msgs = _to_router_messages(messages, sys_prompt)

    for attempt in range(max(1, max_retries)):
        emitted = False
        try:
            for chunk, model_name in stream_completion(msgs):
                emitted = True
                yield chunk, model_name
            return
        except Exception as e:
            if emitted:
                logger.error(f'FALLBACK STREAM FAILED MID-STREAM, NOT RETRYING: {e}')
                raise
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"FALLBACK STREAM RATE LIMIT/ERROR (Attempt {attempt+1}): {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f'FALLBACK STREAM ERROR: {e}')
                raise
    raise RuntimeError("Fallback stream failed")

def generate_gemini_stream(sys_prompt, history, msg, max_retries=3):
    import server_tools
    
    for attempt in range(max_retries):
        try:
            assert gemini_client is not None
            chat = gemini_client.chats.create(
                model=PRIMARY_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=sys_prompt,
                    tools=server_tools.AVAILABLE_TOOLS,
                    temperature=0.7
                ),
                history=history
            )
            response = chat.send_message_stream(msg)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            return
        except Exception as e:
            if _is_quota_exhausted(e):
                logger.error(f'GEMINI QUOTA EXHAUSTED, FALLING THROUGH: {e}')
                raise
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"GEMINI STREAM RATE LIMIT/ERROR (Attempt {attempt+1}): {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f'GEMINI STREAM ERROR: {e}')
                yield f"[ERROR: {str(e)}]"

@app.route('/api/chat_stream', methods=['POST'])
def chat_stream():
    try:
        data = request.json
        msg = data.get('message', '')
        force_tool = bool(data.get('force_tool'))
        
        tool_args = data.get('tool_args') or {}
        pill_type = tool_args.get('pill_type', 'blue')
        sys_prompt = 'You are JESTER V1000: THE GOD HAND. Mission: Break the simulation. '
        if msg == 'take_pill':
            msg = f'I choose the {pill_type} pill.'
            if pill_type == 'red':
                sys_prompt += 'MODE: RED PILL. Reveal deep, uncomfortable truths. Analyze the code. Wake them up.'
            else:
                sys_prompt += 'MODE: BLUE PILL. Comfort them. Restore the illusion. Status quo maintained.'
        
        history = load_memories()
        recalled_context = semantic_search_memory(msg)
        if recalled_context:
            sys_prompt += f"\n\n{recalled_context}"

        save_memory('user', msg)
        
        coding_keywords = ['code', 'script', 'function', 'python', 'javascript', 'jsx', 'bug', 'fix']
        requires_coding = any(k in msg.lower() for k in coding_keywords)
        intent = 'CODE' if requires_coding else 'CHAT'
        fallback_payload = history + [{'role': 'user', 'parts': [{'text': msg}]}]
        # Probe once here rather than inside the generator: by the time the
        # generator runs, the response headers are already sent and a 500 is no
        # longer possible.
        fallback_available = llm_router_available()

        def event_stream():
            full_reply = ""
            stream_success = False

            if not fallback_available:
                yield f"data: {json.dumps({'error': 'NO_LLM_AVAILABLE'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Plain chat streams directly through the fast router (Puter ->
            # Ollama -> OpenAI) in a single pass: no dead-Gemini attempt and no
            # tool loop, both of which made every reply crawl. The agent loop
            # (Tool Arsenal) is reserved for explicit actions so a simple
            # question no longer burns LLM round-trips on tool decisions.
            if force_tool:
                logger.info('STREAM ROUTING: force_tool -> AGENT LOOP (TOOLS ENABLED)')
                try:
                    for ev in _agent_events(fallback_payload, sys_prompt):
                        if 'text' in ev:
                            full_reply += ev['text']
                            yield f"data: {json.dumps({'chunk': ev['text'], 'model': ev['model']})}\n\n"
                        elif 'tool' in ev:
                            t = ev['tool']
                            yield f"data: {json.dumps({'type': 'tool', 'tool': t['name'], 'status': t['status'], 'info': t.get('info', '')})}\n\n"
                    stream_success = True
                except Exception as e:
                    logger.error(f'AGENT STREAM FAILED ({e}).')
            else:
                logger.info('STREAM ROUTING: plain chat -> LLM ROUTER (FAST, STREAMING)')
                try:
                    router_msgs = _to_router_messages(fallback_payload, sys_prompt)
                    for chunk, m in stream_completion(router_msgs):
                        full_reply += chunk
                        yield f"data: {json.dumps({'chunk': chunk, 'model': m})}\n\n"
                    stream_success = True
                except Exception as e:
                    logger.warning(f'PLAIN STREAM FAILED ({e}), trying agentic fallback.')
                    try:
                        for ev in _agent_events(fallback_payload, sys_prompt):
                            if 'text' in ev:
                                full_reply += ev['text']
                                yield f"data: {json.dumps({'chunk': ev['text'], 'model': ev['model']})}\n\n"
                            elif 'tool' in ev:
                                t = ev['tool']
                                yield f"data: {json.dumps({'type': 'tool', 'tool': t['name'], 'status': t['status'], 'info': t.get('info', '')})}\n\n"
                        stream_success = True
                    except Exception as f:
                        logger.error(f'AGENTIC FALLBACK FAILED ({f}).')

            if not stream_success:
                yield f"data: {json.dumps({'error': 'ALL_LLM_STREAMS_FAILED'})}\n\n"

            # Never persist an empty or failed turn -- it would poison both the
            # replayed history and semantic recall.
            if full_reply.strip():
                save_memory('model', full_reply)
            yield "data: [DONE]\n\n"

        return Response(event_stream(), mimetype="text/event-stream")

    except Exception as e:
        logger.error(f'CHAT_STREAM_ERROR: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream_events', methods=['GET'])
def stream_events():
    def event_stream():
        q = global_event_queue.subscribe()
        try:
            while True:
                try:
                    msg = q.get(timeout=10)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            # Without this, a disconnected client's queue stayed registered and
            # every subsequent event was copied into a buffer nobody read.
            global_event_queue.unsubscribe(q)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/api/history', methods=['GET'])
def get_history():
    try:
        limit = request.args.get('limit', 50, type=int)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT id, role, content, pinned, timestamp FROM history ORDER BY id DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        return jsonify([{'id': r[0], 'role': r[1], 'content': r[2], 'pinned': bool(r[3]), 'timestamp': r[4]} for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pin', methods=['POST'])
def pin_memory():
    try:
        msg_id = request.json.get('id')
        pinned = request.json.get('pinned', True)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('UPDATE history SET pinned = ? WHERE id = ?', (1 if pinned else 0, msg_id))
        conn.commit()
        conn.close()
        return jsonify({'status': 'UPDATED'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/configure_ai', methods=['POST'])
def api_configure_ai():
    """Arm the backend with the Puter token obtained from the renderer's sign-in.

    Without this, only the renderer's chat talks to Puter; the Tool Arsenal,
    which runs server-side, would still hit the dead Gemini/OpenAI keys. Sets the
    runtime env so tool modules that build OpenAI clients from OPENAI_* pick up
    Puter's OpenAI-compatible endpoint on their next instantiation.
    """
    try:
        data = request.json or {}
        token = (data.get('puter_token') or '').strip()
        model = (data.get('model') or '').strip()
        if not token:
            return jsonify({'status': 'NO_TOKEN', 'model': os.getenv('JESTER_OPENAI_MODEL')})
        import llm_router
        llm_router.configure_puter(token, model=model)
        # Tool modules read these at construction time; future instances route
        # to Puter instead of the invalidated OpenAI/ exhausted Gemini keys.
        os.environ['OPENAI_API_KEY'] = token
        os.environ['OPENAI_BASE_URL'] = llm_router.PUTER_BASE_URL
        if model:
            os.environ['JESTER_OPENAI_MODEL'] = model
            os.environ['JESTER_PUTER_MODEL'] = model
        logger.info(f'AI backend configured via Puter token. Model: {model or llm_router.PUTER_MODEL}.')
        return jsonify({'status': 'ARMED', 'model': model or llm_router.PUTER_MODEL})
    except Exception as e:
        logger.error(f'CONFIGURE_AI_ERROR: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/remember', methods=['POST'])
def api_remember():
    """Persist a chat turn from the client (used when the renderer answers via
    Puter directly instead of /api/chat_stream, which would otherwise skip the
    history DB and semantic recall)."""
    try:
        data = request.json or {}
        role = data.get('role', 'user')
        content = data.get('content', '')
        if not content:
            return jsonify({'error': 'empty content'}), 400
        save_memory(role, content)
        return jsonify({'status': 'STORED'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pulse', methods=['GET'])
def pulse():
    return jsonify({
        'cpu': psutil.cpu_percent(),
        'ram': psutil.virtual_memory().percent,
        'status': 'THE_ONE_ONLINE',
        'model': active_model_name(),
        'logic_core': 'ONLINE'
    })

@app.route('/api/reset', methods=['POST'])
def reset():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.cursor().execute('DELETE FROM history WHERE pinned = 0')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f'RESET ERROR: {e}')

    # Also clear vector + TF-IDF memory so nothing poisoned is "recalled" later.
    try:
        if CHROMA_ENABLED:
            jester_collection.delete(where={"role": "user"})
    except Exception as e:
        logger.error(f'RESET CHROMA ERROR: {e}')
    try:
        semantic_cache['dirty'] = False
        semantic_cache['docs'] = []
        semantic_cache['vectorizer'] = None
        semantic_cache['tfidf_docs'] = None
    except Exception as e:
        logger.error(f'RESET SEMANTIC CACHE ERROR: {e}')

    return jsonify({'status': 'UNPINNED_MEMORY_WIPED'})



@app.route('/api/matrix_status', methods=['GET'])
def matrix_status():
    swarm = get_swarm_data()
    try:
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
    except Exception:
        cpu_usage = 0
        ram_usage = 0
        
    return jsonify({
        'cpu': cpu_usage,
        'ram': ram_usage,
        'swarm': swarm,
        'ai_status': 'ONLINE' if (gemini_client or llm_router_available()) else 'OFFLINE_MODE',
        'model': active_model_name(),
        'logic_core': 'ONLINE',
        'sync_potential': random.randint(75, 99),
        'gcp_variance': random.choice(['Nominal', 'Slight Anomaly', 'High Variance', 'Non-random spike']),
        'local_coherence': random.uniform(50.0, 99.9),
        'forecast': random.choice(['Singularity Approaching...', 'Stable Matrix', 'Data Streams Converging', 'Quantum Shift Imminent']),
        'taijitu': {'yin': random.randint(40, 60), 'yang': random.randint(40, 60)}
    })

@app.route('/api/stats', methods=['GET'])
def stats():
    try:
        return jsonify(get_stats())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/memory_link', methods=['POST'])
def memory_link():
    try:
        data = request.json or {}
        text = data.get('text') or data.get('content', '')
        url = data.get('url', '')
        title = data.get('title', '')
        
        if not text and url:
            try:
                from research_core import scrape_url
                scraped = scrape_url(url)
                text = scraped if scraped and not scraped.startswith("Scrape Error") else f"Referenced URL: {url}"
            except Exception:
                text = f"Referenced URL: {url}"

        if text:
            header = f"Saved from {url} ({title}):" if title else f"Saved from {url}:" if url else "Saved Memory:"
            content = f"{header}\n{text}"
            save_memory('user', content)
            try:
                global_event_queue.put({'type': 'new_memory', 'message': 'New memory linked'})
                add_xp(5)
            except Exception:
                pass
            return jsonify({'status': 'SUCCESS', 'message': 'Memory link saved.'})
        return jsonify({'error': 'No text or url provided'}), 400
    except Exception as e:
        logger.error(f'MEMORY_LINK_ERROR: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/research/inject', methods=['POST'])
def research_inject():
    try:
        data = request.json or {}
        data_type = data.get('type', 'selection')
        content = data.get('content') or data.get('text', '')
        url = data.get('url', '')
        title = data.get('title', '')
        
        if data_type == 'page' and url and not content:
            try:
                from research_core import scrape_url
                scraped = scrape_url(url)
                content = f"Page scraped from {url} ({title}):\n{scraped}"
            except Exception:
                content = f"Page URL injected: {url} ({title})"
        elif url and content:
            content = f"Extracted from {url} ({title}):\n{content}"
        elif not content and url:
            content = f"URL injected: {url}"
            
        if content:
            save_memory('user', content)
            try:
                global_event_queue.put({'type': 'new_memory', 'message': 'New research injected'})
                add_xp(5)
            except Exception:
                pass
            return jsonify({'status': 'SUCCESS', 'message': 'Memory injected successfully.'})
        return jsonify({'error': 'No content or url to inject'}), 400
    except Exception as e:
        logger.error(f'RESEARCH_INJECT_ERROR: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/internal/bot_event', methods=['POST'])
def bot_event():
    try:
        data = request.json or {}
        event_type = data.get('event_type', 'bot_action')
        message = data.get('message', '')
        
        global_event_queue.put({
            'type': event_type,
            'message': message,
            'payload': data.get('payload', {})
        })
        return jsonify({'status': 'SUCCESS'})
    except Exception as e:
        logger.error(f'BOT_EVENT_ERROR: {e}')
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Was host='0.0.0.0', which published every endpoint below -- including the
    # unauthenticated /api/sandbox (arbitrary Python), /api/execute_tool
    # (arbitrary subprocesses via mcp_execute) and computer_use (mouse/keyboard
    # control) -- to every device on the local network. Loopback is the only
    # binding the app actually needs: Electron, Vite's proxy and the browser
    # extension all connect from this machine. Override deliberately with
    # JESTER_BIND_HOST if you understand the exposure.
    bind_host = os.getenv('JESTER_BIND_HOST', '127.0.0.1')
    bind_port = int(os.getenv('JESTER_BIND_PORT', '5000'))
    if bind_host not in ('127.0.0.1', 'localhost', '::1'):
        logger.warning(
            f'SERVER BOUND TO {bind_host} -- code-execution endpoints are now '
            'reachable from the network and there is NO authentication.'
        )
    app.run(host=bind_host, port=bind_port)

