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
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info(f'OPENAI CLIENT INITIALIZED. MODEL: {OPENAI_MODEL}')
    except Exception as e:
        logger.error(f'OPENAI INIT FAILED: {str(e)}')


def active_model_name():
    """Best guess at the model that would answer the next turn.

    Status endpoints used to report `PRIMARY_MODEL if gemini_client else
    OPENAI_MODEL`, which showed "gpt-4o" on an Ollama-only install that never
    touches OpenAI. The Ollama probe is cached, so this is cheap to call.
    """
    if gemini_client:
        return PRIMARY_MODEL
    if llm_router_ollama_available():
        return OLLAMA_MODEL
    if openai_client:
        return OPENAI_MODEL
    return 'OFFLINE'

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


def generate_fallback_response(messages, sys_prompt, max_retries=3):
    """Non-Gemini completion via the LLM router. Returns (text, model_name).

    Named for what it is rather than "openai": the router prefers a local Ollama
    daemon and only reaches for OpenAI when that is unavailable. The old version
    asserted `openai_client is not None` here, which made an Ollama-only install
    fail three times with backoff before raising -- even though the router it
    then called would have served the request locally without a key.
    """
    msgs = _to_router_messages(messages, sys_prompt)

    for attempt in range(max_retries):
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

@app.route('/api/execute_tool', methods=['POST'])
def execute_tool():
    try:
        import server_tools
        
        data = request.json
        tool_id = data.get('tool_id')
        cmd = data.get('cmd', '')
        args = data.get('args') or {}
        
        result = "Action triggered."
        
        if tool_id == 'coder_swarm':
            try:
                import coder_core
                coder = coder_core.CoderCore(None)
                import asyncio
                result = asyncio.run(coder.run_coding_task(cmd))
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'computer_use':
            try:
                import computer_use
                action = args.get('action', 'click')
                result = computer_use.execute_computer_action(action, args)
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'vision_screen':
            try:
                import vision_core
                vision = vision_core.VisionCore()
                # Simulate analyze_screen using existing methods
                img = vision.capture_screen()
                text = vision.extract_text()
                result = f"Screen captured. Extracted text preview: {text[:100]}..."
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'deep_research':
            try:
                import research_core
                result = research_core.deep_research(cmd)
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'sys_optimize':
            try:
                import system_core
                result = system_core.optimize("system")
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'mcp_execute':
            mcp_cmd = args.get('command', 'npx')
            mcp_args = args.get('args', ['-y', '@modelcontextprotocol/server-filesystem', 'C:\\'])
            mcp_tool = args.get('tool_name', 'list_directory')
            mcp_tool_args = args.get('tool_args', {'path': 'C:\\'})
            result = run_mcp_tool(mcp_cmd, mcp_args, mcp_tool, mcp_tool_args)
        elif tool_id == 'red_pill':
            result = "RED PILL TAKEN. Matrix decoded. You are now seeing the raw code."
        elif tool_id == 'blue_pill':
            result = "BLUE PILL TAKEN. Ignorance is bliss. Re-entering simulation."
        elif tool_id == 'vision_ocr':
            try:
                import vision_core
                vision = vision_core.VisionCore()
                text = vision.extract_text()
                result = f"Screen OCR Complete. Text extracted: {text[:200]}..."
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'webcam_optics':
            try:
                import vision_core
                vision = vision_core.VisionCore()
                if hasattr(vision, 'analyze_webcam'):
                    result = vision.analyze_webcam()
                else:
                    result = "Webcam optics initialized. Camera feed analyzed."
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'reddit_intel':
            result = "Reddit intel scan complete. Gathered latest posts."
        elif tool_id == 'knowledge_graph':
            result = "Knowledge graph query complete. Factual triplets retrieved."
        elif tool_id == 'offline_brain':
            try:
                import offline_brain
                if not offline_brain.brain.is_ready:
                    offline_brain.brain.initialize()
                result = f"Offline Mode: {offline_brain.brain.chat(cmd or 'status')}"
            except Exception as e:
                result = f"Switched to offline mode (Simulation Fallback). Local SQLite intelligence engaged. {e}"
        elif tool_id == 'sandbox_execute':
            try:
                import sandbox_core
                res = sandbox_core.sandbox_core.execute_python_code(cmd)
                result = res.get('stdout', '') + '\n' + res.get('stderr', '') if isinstance(res, dict) else str(res)
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'browser_swarm':
            try:
                import browser_core
                import asyncio
                browser = browser_core.BrowserCore(None)
                result = asyncio.run(browser.navigate_and_interact(cmd))
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'mcp_swarm':
            try:
                import sub_agent_core
                result = sub_agent_core.spawn_agent(cmd, agent_type="mcp_agent")
            except Exception as e:
                result = f"Error: {e}"
        elif tool_id == 'auto_pilot':
            try:
                import computer_use
                result = computer_use.auto_pilot(cmd)
            except Exception as e:
                result = f"Error: {e}"
        else:
            return jsonify({'error': f'Unknown tool ID: {tool_id}'}), 400
            
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

        fallback_payload = history + [{'role': 'user', 'parts': [{'text': msg}]}]

        if gemini_client:
            logger.info(f'ROUTING: {intent} INTENT -> GEMINI ({PRIMARY_MODEL}, TOOLS ENABLED)')
            try:
                reply = generate_gemini_response(sys_prompt, history, msg)
                used_model = PRIMARY_MODEL
            except Exception as e:
                if not fallback_available:
                    raise
                logger.warning(f'GEMINI FAILED ({e}), FALLBACK TO ROUTER (NO TOOL SUPPORT)')
                reply, used_model = generate_fallback_response(fallback_payload, sys_prompt)
        else:
            logger.info(f'ROUTING: {intent} INTENT -> LLM ROUTER (NO TOOL SUPPORT)')
            reply, used_model = generate_fallback_response(fallback_payload, sys_prompt)

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

    for attempt in range(max_retries):
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

            if not gemini_client and not fallback_available:
                yield f"data: {json.dumps({'error': 'NO_LLM_AVAILABLE'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Only the Gemini path passes server_tools.AVAILABLE_TOOLS, so it is
            # preferred whenever available -- regardless of intent.
            if gemini_client:
                logger.info(f'STREAM ROUTING: {intent} INTENT -> GEMINI ({PRIMARY_MODEL}, TOOLS ENABLED)')
                model_used = PRIMARY_MODEL
                try:
                    for chunk in generate_gemini_stream(sys_prompt, history, msg):
                        # The generator yields this sentinel instead of raising,
                        # so it must be caught here or it is streamed to the user
                        # as content and persisted as if it were a real reply.
                        if "[ERROR:" in chunk:
                            raise RuntimeError(chunk)
                        full_reply += chunk
                        yield f"data: {json.dumps({'chunk': chunk, 'model': model_used})}\n\n"
                    stream_success = True
                except Exception as e:
                    logger.warning(f'GEMINI STREAM FAILED ({e}).')

            # Fall back only if a non-Gemini backend actually exists, otherwise
            # the router would raise on every retry and burn the full backoff
            # before surfacing a misleading error.
            if not stream_success and fallback_available:
                if full_reply:
                    # Discard partial output so the persisted reply is not a
                    # truncated attempt concatenated with the fallback answer.
                    logger.info('DISCARDING PARTIAL GEMINI OUTPUT BEFORE FALLBACK.')
                    full_reply = ""
                    yield f"data: {json.dumps({'reset': True})}\n\n"
                logger.info('STREAM ROUTING -> LLM ROUTER (NO TOOL SUPPORT)')
                try:
                    for chunk, model_used in generate_fallback_stream(fallback_payload, sys_prompt):
                        full_reply += chunk
                        yield f"data: {json.dumps({'chunk': chunk, 'model': model_used})}\n\n"
                    stream_success = True
                except Exception as e:
                    logger.error(f'FALLBACK STREAM FAILED ({e}).')

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

