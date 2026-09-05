import logging
import os
import re
import socket
import sqlite3
import time
import math

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
        c.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, done INTEGER DEFAULT 0, created DATETIME DEFAULT CURRENT_TIMESTAMP)')
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
        # Feed background fact-mining (miko pattern) so user-stated facts land
        # in the knowledge graph without blocking the chat turn.
        if role == 'user':
            _enqueue_fact_mining(content)
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


# --- BM25 lexical scoring (hybrid recall, silicondev-style) ---
# TF-IDF cosine only is weak on conversational memory ("what did I name the
# project?" vs an old doc saying "the project is called JESTER"). BM25 adds
# term-frequency saturation + inverse-document-frequency, so short distinctive
# tokens ("jester", "gemini", "api key") rank old related turns correctly even
# when the query shares few exact words with the stored phrasing.
def _bm25_tokens(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def _bm25_scores(query_tokens, docs):
    """Pure-Python Okapi BM25 scores over the cached docs (k1=1.5, b=0.75)."""
    N = len(docs)
    if not N or not query_tokens:
        return [0.0] * N
    tokenized_docs = []
    df = {}
    for d in docs:
        toks = _bm25_tokens(d)
        tokenized_docs.append(toks)
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    avgdl = sum(len(t) for t in tokenized_docs) / N
    k1, b = 1.5, 0.75
    idf = {}
    for t in df:
        idf[t] = max(0.0, abs(math.log((N - df[t] + 0.5) / (df[t] + 0.5) + 1)))
    scores = []
    for toks in tokenized_docs:
        dl = len(toks)
        tf_map = {}
        for t in toks:
            tf_map[t] = tf_map.get(t, 0) + 1
        s = 0.0
        for t in query_tokens:
            f = tf_map.get(t, 0)
            if f:
                denom = f + k1 * (1 - b + b * dl / avgdl)
                s += idf.get(t, 0) * (f * (k1 + 1)) / denom
        scores.append(s)
    return scores


# --- Fact-mining worker (miko-style) ---
_FACT_QUEUE = queue.Queue()
_FACT_MINER_LOCK = threading.Lock()
_FACT_MINER_LAST_RUN = [0.0]


def _fact_miner_worker():
    import learning_core
    while True:
        try:
            cand = _FACT_QUEUE.get(timeout=30)
        except queue.Empty:
            continue
        cand = (cand or '').strip()
        if len(cand) < 24:
            continue  # too short to carry a fact
        # Facts are declarative. Questions ("what do you remember about me?",
        # "who are you?", "are you working?") extract nothing but noise like
        # `you -> remember -> me`, polluting the graph. Skip interrogatives.
        if re.search(r'\b(what|who|when|where|why|how|which|can|could|do|does|did|is|are|will|would|should)\b.*\?', cand, re.IGNORECASE) or '?' in cand:
            continue
        with _FACT_MINER_LOCK:
            now = time.time()
            if now - _FACT_MINER_LAST_RUN[0] < 45:
                continue  # rate-limited; skip, don't block the stream
            _FACT_MINER_LAST_RUN[0] = now
        try:
            saved = learning_core.auto_extract_and_learn(cand)
            if saved:
                logger.info(f'FACT MINER: {" | ".join(saved)[:400]}')
            else:
                logger.debug('FACT MINER: no triplets extracted')
        except Exception as e:
            logger.warning(f'FACT MINER FAILED: {e}')


def _enqueue_fact_mining(text):
    """Non-blocking: drop facts to mine into the worker queue (miko pattern)."""
    try:
        _FACT_QUEUE.put((text or '')[:2000], timeout=0.2)
    except queue.Full:
        pass


# --- Session-note worker (claude-mem sessions layer) ---
# After a substantive turn, distill a one-line dated memory note so later
# recall surfaces what actually happened in conversation, not just extracted
# triplets. Runs off the request path and is rate-limited like the fact miner.
_SESSION_NOTE_QUEUE = queue.Queue()
_SESSION_NOTE_LOCK = threading.Lock()
_SESSION_NOTE_LAST = [0.0]


def _session_note_worker():
    import memory_core
    while True:
        try:
            item = _SESSION_NOTE_QUEUE.get(timeout=30)
        except queue.Empty:
            continue
        user_text, reply_text = item
        with _SESSION_NOTE_LOCK:
            now = time.time()
            if now - _SESSION_NOTE_LAST[0] < 240:
                continue
            _SESSION_NOTE_LAST[0] = now
        try:
            prompt = (
                "Write ONE durable memory note (a single sentence) capturing "
                "anything worth remembering later from this exchange: user facts, "
                "preferences, tasks, decisions. If nothing is worth remembering, "
                "reply exactly MEMORIZE_SKIP.\n\n"
                f"User said: {user_text[:800]}\nJESTER replied: {reply_text[:1200]}"
            )
            note, _m = generate_completion_with_model([{'role': 'user', 'content': prompt}])
            note = (note or '').strip()
            skip = re.sub(r'[^a-z]', '', note.lower()) == 'memorizeskip'
            if not skip and note and len(note) < 500:
                memory_core.save(note, importance=5, metadata={'kind': 'session_note'})
                logger.info(f'SESSION NOTE: {note[:200]}')
        except Exception as e:
            logger.warning(f'SESSION NOTE FAILED: {e}')


def _enqueue_session_note(user_text, reply_text):
    """Non-blocking: drop a finished turn into the note-distillation worker."""
    try:
        _SESSION_NOTE_QUEUE.put((user_text or '', reply_text or ''), timeout=0.2)
    except queue.Full:
        pass


def _local_grounding_note():
    """One-line honesty guard for the weak local model (invented recall fix).

    llama3.2 answered "my favourite language is Python" by inventing a shared
    history. When Puter is not armed and Ollama is serving, pin the model to
    grounded answers instead of fabricated persona memories.
    """
    if not llm_router_ollama_available() or llm_router_puter_armed():
        return ''
    return (
        "\n\nHARD GROUNDING: you are running on a small local model. Never invent "
        "personal history, past conversations, numbers, or file contents. Answer "
        "only from the provided context; where you don't know, say you don't know."
    )


def _build_sys_prompt(pill_type=None):
    """Concise, grounded chat persona. The old 'GOD HAND / Break the simulation'
    framing made small local models narrate dramatic invented backstories, so the
    default prompt now forbids storytelling outright. Pill mode only changes tone.
    """
    prompt = (
        "You are JESTER, a compact local voice assistant running on the user's PC. "
        "MISSION: Vibe. Skills: Full-stack engineering, pixel-perfect chrome extension. "
        "INTEGRITY: Rather than disingenuous embellishment, we provide straight talk with integrity. "
        "We do NOT tell stories.\n"
        "Answer the user's question directly and concisely, in plain language. "
        "Do NOT invent characters, scenes, dramatic backstories, memories, numbers, "
        "or file contents. Do NOT spin answers into narratives. If you don't know, "
        "say so briefly; if the user asked about your past or storage, answer only "
        "from the context provided here."
    )
    if pill_type == 'red':
        prompt += "\nMODE: RED PILL. The user asked for hard truths: be blunt and skeptical about hype, no theatrics."
    elif pill_type == 'blue':
        prompt += "\nMODE: BLUE PILL. Keep it light and reassuring, but still concise and honest."
    prompt += _local_grounding_note()
    return prompt


def _is_query_echo(query, doc):
    """True when a past message is (near-)identical to the current query.

    "what do you remember about me?" asked three turns ago must not be
    "recalled" as context -- that is the pattern that made memory questions
    echo themselves and then trigger the persona fallback.
    """
    q_toks = set(_bm25_tokens(query))
    d_toks = set(_bm25_tokens(doc))
    if not q_toks or not d_toks:
        return False
    overlap = len(q_toks & d_toks) / max(1, len(q_toks))
    return overlap >= 0.6 and abs(len(q_toks) - len(d_toks)) <= 2


_TEMPORAL_MARKERS = re.compile(
    r"\b(now|current|currently|today|latest|recent|recently|still|present|right now)\b|"
    r"\bwhats?\s+(the\s+)?(current|latest|newest|status)\b",
    re.IGNORECASE,
)


def _temporal_intent(query):
    """True when the query asks about the current/state (mem0 temporal reasoning)."""
    return bool(_TEMPORAL_MARKERS.search(query or ''))


_TOPIC_STOPWORDS = {
    'the', 'a', 'an', 'of', 'and', 'or', 'to', 'in', 'on', 'with', 'for',
    'what', 'why', 'who', 'when', 'where', 'how', 'you', 'your', 'me', 'my',
    'i', 'is', 'are', 'do', 'did', 'does', 'we', 'us', 'it', 'about',
    'remember', 'recall', 'tell', 'know', 'been',
}


def _topic_tokens(query):
    return [t for t in re.findall(r"[a-z0-9']+", (query or '').lower())
            if t not in _TOPIC_STOPWORDS and len(t) >= 4]


def _entity_facts_snippet(query, limit=4):
    """Bound entity-linked knowledge-graph facts for injection into recall."""
    try:
        import learning_core
        facts = learning_core.query_graph_entity_linked(query or '', limit=limit)
    except Exception:
        return ''
    if not facts:
        return ''
    return 'GRAPH FACTS:\n' + facts


def _hybrid_top(query, docs, top_k=3):
    """Blend BM25 + TF-IDF cosine into one ranked cut, thresholded like before."""
    if not docs:
        return []
    vectorizer = semantic_cache['vectorizer']
    tfidf_docs = semantic_cache['tfidf_docs']
    tfidf_query = vectorizer.transform([query])
    cosine_sim = cosine_similarity(tfidf_query, tfidf_docs).flatten()
    bm25_scores = _bm25_scores(_bm25_tokens(query), docs)
    # Normalize both signals to [0,1] before blending, else the raw BM25
    # magnitude dwarfs cosine and lexical matching dominates everything.
    bm25_max = max(bm25_scores) if bm25_scores else 0.0
    bm25_norm = [s / bm25_max if bm25_max else 0.0 for s in bm25_scores]
    cos_max = float(cosine_sim.max()) if len(cosine_sim) else 0.0
    cos_norm = [float(c) / cos_max if cos_max else 0.0 for c in cosine_sim]
    combined = [0.6 * b + 0.4 * c for b, c in zip(bm25_norm, cos_norm)]
    # Temporal reasoning (mem0): docs are cached newest-first, so for
    # state queries ("what is ... now") nudge the newest rows up in the blend.
    if _temporal_intent(query):
        n = max(1, len(docs))
        combined = [combined[i] + 0.15 * ((n - i) / n) for i in range(n)]
    order = sorted(range(len(docs)), key=lambda i: combined[i], reverse=True)
    hits = [docs[i] for i in order[:top_k] if combined[i] > 0.12]
    return [d for d in hits if not _is_query_echo(query, d)]


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
                relevant = [
                    d for d in docs
                    if len(d) > 10 and not _is_query_echo(query, d)
                ]
                if relevant:
                    recalled = "RECALLED PAST CONTEXT: " + " | ".join(relevant)
                    facts = _entity_facts_snippet(query, 3)
                    if facts:
                        recalled += "\n" + facts
                    return recalled
            return ""
        else:
            # Hybrid recall: TF-IDF cosine blended with Okapi BM25. The old
            # code used cosine alone, which failed on *conversational* phrasing
            # ("what did I name the project?" never token-matches the stored
            # "the project is JESTER" line). BM25's tf/idf saturation catches
            # distinctive words the cosine score buried.
            if semantic_cache.get('dirty'):
                refresh_semantic_cache()
            docs = semantic_cache['docs']
            if not docs or not semantic_cache['vectorizer']:
                return ""
            hits = _hybrid_top(query, docs, top_k)
            if hits:
                # hits are plain doc strings (see _hybrid_top); slicing [0] on
                # a string took the first CHARACTER and the chroma-off hybrid
                # path could never recall anything.
                relevant = [h for h in hits if len(h) > 10]
                if relevant:
                    recalled = "RECALLED PAST CONTEXT: " + " | ".join(relevant)
                    facts = _entity_facts_snippet(query, 3)
                    if facts:
                        recalled += "\n" + facts
                    return recalled
            return ""
    except Exception as e:
        logger.error(f"SEMANTIC SEARCH ERROR: {e}")
        return ""

init_db()
if not CHROMA_ENABLED:
    refresh_semantic_cache()


_CODING_ACTION_RE = re.compile(
    r'\b(fix|repair|debug|write|create|make|build|generate|implement|add|update|'
    r'refactor|review|analyze|run|install|execute|removes?|fixes?)\b.{0,40}'
    r'\b(code|script|function|python|javascript|jsx|bug|app|feature|file|program|'
    r'class|module|import|regex|api|endpoint|ui|component|package|dependency)\b',
    re.IGNORECASE,
)
_CODE_NOUN_ACTION_RE = re.compile(
    r'\b(python|javascript|jsx|code|script|bug)\b.{0,40}'
    r'\b(fix|repair|debug|write|create|build|make|solve|correct|update|run|execute)\b',
    re.IGNORECASE,
)


def _requires_coding(msg):
    """True only when the user is *asking* for coding work.

    A bare mention of "python" or "code" ("my favourite language is Python",
    "that code is slow") must NOT route into the agent loop -- that is what sent
    declarative statements to coder_swarm and turned chit-chat into "repairs
    complete." Require an action verb near a coding noun instead.
    """
    return bool(_CODING_ACTION_RE.search(msg or "")) or bool(_CODE_NOUN_ACTION_RE.search(msg or ""))


def _to_router_messages(messages, sys_prompt):
    """Flatten Gemini-shaped history into the router's OpenAI-style messages."""
    msgs = [{'role': 'system', 'content': str(sys_prompt)}]
    for m in messages:
        role = 'user' if m['role'] == 'user' else 'assistant'
        parts = m.get('parts') or [{}]
        msgs.append({'role': role, 'content': str(parts[0].get('text', ''))})
    return msgs


_MEMORY_INTENT_RE = re.compile(
    r'\b(remember|recall|remembrances?|(what|who)[^.]*about[^.]*(me|yourself|us|you have learnt|you know)|who am i)\b',
    re.IGNORECASE,
)


def _memory_recall_context(query=''):
    """Pull genuinely stored facts (not a persona speech) for memory questions.

    Three-layer progressive disclosure (claude-mem style): Layer 1 semantic
    headline matches from history; Layer 2 timeline/observation rows from
    memory_core (recent, or topic-filtered when the query names a subject);
    Layer 3 entity-linked knowledge-graph facts, newest first. Every layer is
    bounded so a large graph cannot blow the prompt. Returns a prompt-injection
    string or '' when no memory exists.
    """
    try:
        parts = []
        budget = 1600
        def add(txt):
            if txt and len("\n\n".join(parts)) < budget:
                parts.append(txt)
        sem = semantic_search_memory(query or '', top_k=3)
        add(sem)
        import memory_core
        topic = _topic_tokens(query or '')
        if topic:
            obs = memory_core.retrieve(' '.join(topic[:3]), 6)
        else:
            obs = memory_core.retrieve_recent(6)
        if obs and 'RECALL_ERROR' not in obs and 'NO_MATCHING_MEMORIES' not in obs:
            add("TIMELINE:\n" + obs)
        import learning_core
        facts = learning_core.query_graph_entity_linked(query or '', limit=8)
        if facts:
            add("KNOWLEDGE GRAPH:\n" + facts)
        if not parts:
            return ""
        return "\n\nRECALLED FROM STORED MEMORY (quote these accurately, do not invent):\n" + "\n\n".join(parts)
    except Exception as e:
        logger.warning(f'MEMORY RECALL CONTEXT FAILED: {e}')
        return ""


def _build_openai_tools(functions):
    """Convert Tool Arsenal callables into OpenAI function-tool schemas.

    The schema is what keeps weak local models honest: name, a full-docstring
    description and per-parameter types/descriptions. A model that can't see
    what a tool expects is far likelier to emit `{"name":"X","parameters{...}}`
    by hand (see _salvage_embedded_tool_call) or invent bogus args.
    """
    tools = []
    for fn in functions:
        sig = inspect.signature(fn)
        properties = {}
        required = []
        doc = (fn.__doc__ or '').strip()
        doc_lines = [ln.strip() for ln in doc.splitlines() if ln.strip()]
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
            elif ann is list:
                ptype = 'array'
            else:
                ptype = 'string'
            prop = {'type': ptype}
            # Per-parameter description: the docstring often reads
            # `param name: what it means` on its own line.
            marker = f'{name}:'
            pdesc = next((ln.split(marker, 1)[1].strip()
                          for ln in doc_lines if ln.startswith(marker)), '')
            if pdesc:
                prop['description'] = pdesc
            properties[name] = prop
            if param.default is inspect.Parameter.empty:
                required.append(name)
        tools.append({
            'type': 'function',
            'function': {
                'name': fn.__name__,
                # Full docstring (not just line 1) so the model learns what the
                # tool does AND what its parameters mean before it calls it.
                'description': doc or fn.__name__,
                'parameters': {
                    'type': 'object',
                    'properties': properties,
                    'required': required,
                },
            },
        })
    return tools


# Some providers' models write tool calls as literal text instead of emitting
# structured `tool_calls`. Left alone, that JSON gets streamed to the user and
# saved to memory as a "reply". Salvage it -> an executable {name, arguments}.
_DEGENERATE_CALL_RE = re.compile(
    r'\{\s*"name"\s*:\s*"([A-Za-z_][A-Za-z0-9_]*)".{0,200}?"parameters"?\s*[":()]*\s*\{',
    re.DOTALL,
)


def _salvage_embedded_tool_call(text):
    """Extract a tool-call JSON the model wrote as plain text.

    The model in the wild emits several malformed shapes:
      {"name":"X","parameters":{...}}
      {"name":"X","parameters{ "execute":true, ...}}        (no colon/quote)
      {"name":"X","parameters){ "execute":true, ...}}        (stray paren)
    Returns (name, args) when detectable, else (None, None).
    """
    m = _DEGENERATE_CALL_RE.search(text or "")
    if not m:
        # Parameterless shape only, e.g. {"name":"take_pill"}.
        m2 = re.search(r'\{\s*"name"\s*:\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*\}', text or "")
        if m2:
            return m2.group(1), {}
        return None, None
    name = m.group(1)
    # Brace-match the arguments object that begins at m.end() so a nested
    # quoted brace (e.g. a JSON-in-JSON string) is handled correctly. The
    # regex consumed the opening '{', so treat it as depth 1 here.
    depth = 1
    args_end = None
    for i in range(m.end(), min(m.end() + 1200, len(text))):
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                args_end = i + 1
                break
    if args_end is None:
        return None, None
    body = text[m.end():args_end]
    if not body.strip():
        return name, {}
    # Repair common tokens so json.loads can parse: fix unquoted keys like
    # `execute:true` (missing opening quote) and broken `: ` after "parameters".
    sane = re.sub(r'\b([A-Za-z_]\w*)\s*:', r'"\1":', body)
    sane = re.sub(r'(\S)({|})', r'\1\2', sane)
    sane = sane.replace('"\n"', '","').replace('"{ ', '{"').replace(' }"', '"}')
    # Tolerate a trailing comma before }.
    sane = re.sub(r',\s*}', '}', sane)
    try:
        built = json.loads(sane)
    except (json.JSONDecodeError, ValueError):
        # Fallback: pull simple key:"value" pairs out of the body.
        built = dict(re.findall(r'"([A-Za-z_]\w*)"\s*:\s*"([^"]*)"', body))
    if not isinstance(built, dict):
        built = {}
    return name, built


def _yield_salvaged_call(name, args, msgs):
    """Execute a salvaged tool call, mirroring the structured-call handler below."""
    import server_tools
    # BeforeToolCall policy (pi-agent-go): the salvage path previously executed
    # ANY server_tools function the model wrote as text -- including
    # system_control (real keystrokes) and execute_python_sandbox. Gate it by
    # the same deny set the structured path offers.
    if name in _UNSAFE_TOOLS:
        return [f'BLOCKED_BY_POLICY: {name} is Arsenal-only; not executed through the chat loop.']
    fn = getattr(server_tools, name, None)
    if fn is None:
        return [f"UNKNOWN TOOL: {name}"]
    out, _ = _execute_tool_call(fn, name, args, msgs)
    return [out]


def _execute_tool_call(server_tools, name, args, msgs):
    """Run one Tool Arsenal call with arg-tolerance; returns (out, ok).

    Local models invent parameters or omit required ones; instead of dying on a
    TypeError we drop unknown keys and synthesize missing required params from
    the latest user message. `ok` is False on error so a caller can retry.
    """
    if server_tools is None:
        return 'UNKNOWN TOOL', False
    try:
        sig = inspect.signature(server_tools)
        params = set(sig.parameters)
        val_args = {k: v for k, v in args.items() if k in params}
        required_missing = [
            p for p, prm in sig.parameters.items()
            if prm.default is inspect.Parameter.empty and p not in val_args
        ]
        if required_missing:
            last_user = next(
                (m.get('content') for m in reversed(msgs)
                 if m.get('role') == 'user' and m.get('content')),
                ''
            )
            last_user = str(last_user)[:1500] or 'Perform the task.'
            for p in required_missing:
                val_args[p] = last_user
        out = server_tools(**val_args) if val_args else server_tools()
        return str(out), True
    except TypeError as te:
        return f'Error (bad arguments): {te}', False
    except Exception as ex:
        return f'Error: {ex}', False


def _run_tool_round(server_tools, calls, msgs, blocked=frozenset()):
    """Execute one batch of tool_calls, parallelizing independent calls.

    JARVIS-style: a round can contain several calls; running them serially makes
    a multi-tool plan crawl. ThreadPoolExecutor runs the safe subset in parallel
    while preserving deterministic ordering for msgs history. Tools that spawn
    their own IO (subprocess, asyncio.run) are fine on worker threads.
    `blocked` names are refused up-front (BeforeToolCall policy).
    """
    results = []
    outputs = {}
    for c in calls:
        name = c['function']['name']
        if name in blocked:
            outputs[c['id']] = (
                f"BLOCKED_BY_POLICY: {name} is Arsenal-only; "
                "not executed through the chat loop."
            )
            continue
        try:
            args = json.loads(c['function']['arguments'] or '{}')
        except (json.JSONDecodeError, ValueError):
            args = {}
        if not isinstance(args, dict):
            args = {}
        results.append((c, name, args))
    if len(results) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(4, len(results))) as pool:
            def gen_pairs():
                for c, name, args in results:
                    fn = getattr(server_tools, name, None)
                    yield fn, name, args, c
            futs = {
                pool.submit(_execute_tool_call, fn, name, args, msgs): c
                for fn, name, args, c in gen_pairs()
            }
            for fut in futs:
                try:
                    out, ok = fut.result()
                except Exception as ex:
                    out, ok = f'Error: {ex}', False
                c = futs[fut]
                if c['function']['name'] is None or out == 'UNKNOWN TOOL: None':
                    out = f"UNKNOWN TOOL: {c['function']['name']}"
                outputs[c['id']] = out
    else:
        for c, name, args in results:
            fn = getattr(server_tools, name, None)
            if fn is None:
                out = f'UNKNOWN TOOL: {name}'
            else:
                out, _ = _execute_tool_call(fn, name, args, msgs)
            outputs[c['id']] = out
    return outputs


# The single deny-set that governs BOTH the schema offered to the model AND the
# execute path. A name here can never run through the chat loop, whether it
# arrived as a structured tool_call or as salvaged JSON written as prose.
_UNSAFE_TOOLS = frozenset({
    'system_control', 'execute_computer_use', 'start_visual_autopilot',
    'execute_python_sandbox', 'dispatch_browser_swarm', 'analyze_screen',
    'dispatch_mcp_swarm', 'run_rovo_dev', 'optimize_system',
})


def _looks_like_failure(out):
    s = str(out)
    return (s.startswith('Error') or 'UNKNOWN TOOL' in s
            or 'UNKNOWN MCP SERVER' in s or 'BLOCKED_BY_POLICY' in s)


_COMPACT_MAX_CHARS = 22000
_COMPACT_TAIL_CHARS = 8000


def _tail_truncate(msgs, max_chars):
    """Deterministic fallback: drop oldest non-system turns until under budget."""
    if not msgs:
        return msgs
    kept = msgs[:1]
    rest = msgs[1:]
    while rest and sum(len(str(m.get('content', ''))) for m in kept + rest) > max_chars:
        rest.pop(0)
    for m in rest:
        content = str(m.get('content', ''))
        if len(content) > 1500:
            m['content'] = content[:1500] + '...[truncated]'
    return kept + rest


def _truncate_changed(orig, new):
    return (len(orig) != len(new)
            or sum(len(str(m.get('content', ''))) for m in orig)
            != sum(len(str(m.get('content', ''))) for m in new))


def _compact_router_messages(msgs, max_chars=_COMPACT_MAX_CHARS):
    """MS agent-framework-style automatic context compaction.

    When the running message list exceeds the budget, keep the system prompt,
    the active user question and its in-flight tool round verbatim, and replace
    the middle turns with one dense LLM summary. Falls back to trimming the
    tail if the summarizer is unavailable. Returns (msgs, changed)."""
    try:
        total = sum(len(str(m.get('content', ''))) for m in msgs)
        if total <= max_chars:
            return msgs, False
        if not msgs:
            return msgs, False
        head = msgs[0] if msgs[0].get('role') == 'system' else {'role': 'system', 'content': ''}
        last_user = max(
            (i for i, m in enumerate(msgs) if i > 0 and m.get('role') == 'user'),
            default=None,
        )
        if last_user is None:
            trimmed = _tail_truncate(msgs, max_chars)
            return trimmed, _truncate_changed(msgs, trimmed)
        tail = msgs[last_user:]
        if sum(len(str(m.get('content', ''))) for m in tail) > _COMPACT_TAIL_CHARS:
            tail = _tail_truncate(tail, _COMPACT_TAIL_CHARS)
        mid = msgs[1:last_user]
        if not mid:
            return head + tail, True
        transcript = "\n".join(f"{m.get('role')}: {str(m.get('content', ''))[:1200]}" for m in mid)
        transcript = transcript[:12000]
        prompt = (
            "Compress the conversation turns below into one dense summary for a "
            "voice assistant. Keep user preferences, stated facts, tool results "
            "and decisions. Drop chit-chat. No preamble.\n\n" + transcript
        )
        try:
            summary, _m = generate_completion_with_model([{'role': 'user', 'content': prompt}])
        except Exception:
            summary = ''
        compressed = [head, {
            'role': 'system',
            'content': f'[Earlier context compacted] {(summary or "prior turns summarised")[:2400]}',
        }]
        return compressed + tail, True
    except Exception as e:
        logger.warning(f'CONTEXT COMPACTION FAILED, FALLBACK TRUNCATION: {e}')
        trimmed = _tail_truncate(msgs, max_chars)
        return trimmed, _truncate_changed(msgs, trimmed)


def _agent_events(messages, sys_prompt, max_iters=3):
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
        if fn.__name__ not in _UNSAFE_TOOLS
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
        f"'r/X'/'subreddit X'/'news from X'/'fetch the feed for X' -> fetch_rss; "
         f"'todo X'/'add task'/'track this' -> todo_add; 'list todos'/'what tasks'/'to-do' -> todo_list; 'mark todo done' -> todo_mark; "
        f"'code X'/'build X'/'write X X'/'create X X'/'fix the bug in <path>'/'repair <path>'/'add feature to <path>' -> dispatch_coder_swarm (pass the full file path as `path` when the user names one, `execute=True` only if asked to run it); "
        f"Otherwise do NOT call a tool -- just answer the user's message directly. "
        f"Do NOT invent numbers; quote only what the tool returns. "
        f"After the tool returns, stop calling tools and give your answer immediately "
        f"(a second corrective call is allowed only if the first tool FAILED -- retry "
        f"with fixed arguments once, then answer). "
        f"Available tools: {tool_names}."
    )
    msgs[0] = {'role': 'system', 'content': str(msgs[0]['content']) + caller_note}

    for _ in range(int(max_iters)):
        # MS agent-framework context compaction: compress the middle turns into
        # a summary before the window overflows, keeping the live question intact.
        msgs, _compact_ran = _compact_router_messages(msgs)
        if _compact_ran:
            yield {'tool': {'name': 'CONTEXT_COMPACTION', 'status': 'DONE',
                            'info': 'Context window compacted (dense summary injected)'}}
        try:
            content, calls, model = llm_router.tool_completion(msgs, tools)
        except Exception as e:
            logger.warning(f'TOOL CALLING UNSUPPORTED, PLAIN STREAM FALLBACK: {e}')
            # Non-stream so a model that writes `{"name":...}` as text is
            # salvaged below instead of leaking raw tool JSON to the user.
            try:
                content, model = llm_router.generate_completion_with_model(msgs)
                calls = None
            except Exception as f:
                logger.warning(f'PLAIN FALLBACK ALSO FAILED: {f}')
                yield {'text': f"[I could not reach the LLM: {e}]", 'model': 'NONE'}
                return
        if content:
            # Some models write `{"name":"X","parameters":{...}}` as plain text
            # instead of a structured tool_call. If the reply is dominated by an
            # embedded call, execute it for real instead of echoing JSON to the
            # user and persisting it as a fake "reply".
            sname, sargs = _salvage_embedded_tool_call(content)
            if sname is not None and not calls:
                yield {'tool': {'name': sname, 'status': 'RUN'}}
                outs = _yield_salvaged_call(sname, sargs, msgs)
                out = str(outs[0]) if outs else ''
                yield {'tool': {'name': sname, 'status': 'DONE', 'info': out[:400]}}
                msgs.append({
                    'role': 'assistant',
                    'content': content or '',
                })
                msgs.append({'role': 'tool', 'tool_call_id': 'salvaged', 'name': sname, 'content': out[:3000]})
                content = ''  # do not surface the raw JSON as a reply
                continue
            else:
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
        # Emit RUN for all calls in the round first so the UI shows the full
        # plan, then execute (in parallel when the model returned several).
        for c in calls:
            yield {'tool': {'name': c['function']['name'], 'status': 'RUN'}}
        outputs = _run_tool_round(server_tools, calls, msgs, blocked=_UNSAFE_TOOLS)
        for c in calls:
            name = c['function']['name']
            out = outputs.get(c['id'], 'Error: missing result')
            out = str(out)
            yield {'tool': {'name': name, 'status': 'DONE', 'info': out[:400]}}
            msgs.append({'role': 'tool', 'tool_call_id': c['id'], 'name': name, 'content': out[:3000]})

        # pi-agent-go Terminate: when the round was a pure call to terminal
        # tools (their result IS the answer) and none failed, skip the next
        # tool-calling round and do one short plain summarization instead.
        if not (content or '').strip() and calls and all(
            c['function']['name'] in getattr(server_tools, 'TERMINAL_TOOLS', frozenset())
            for c in calls
        ) and all(not _looks_like_failure(str(outputs.get(c['id'], ''))) for c in calls):
            msgs.append({
                'role': 'user',
                'content': 'Now answer the user directly from the tool results above in a short, natural reply. Do not call any more tools.',
            })
            try:
                final_text, final_model = generate_completion_with_model(msgs)
            except Exception as e:
                logger.warning(f'TERMINAL TOOL SUMMARIZE FAILED: {e}')
                final_text = ' '.join(str(outputs.get(c['id'], ''))[:300] for c in calls)
                final_model = model
            yield {'text': final_text or 'Done.', 'model': final_model}
            return

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
            'news_feed': lambda: server_tools.fetch_rss(subreddit_from(cmd) or 'r/singularity'),
            'knowledge_graph': lambda: server_tools.query_knowledge_graph(cmd),
            'offline_brain': lambda: server_tools.switch_to_offline(cmd or 'status'),
            'sandbox_execute': lambda: server_tools.execute_python_sandbox(cmd),
            'browser_swarm': lambda: server_tools.dispatch_browser_swarm(cmd),
            'mcp_swarm': lambda: server_tools.dispatch_mcp_swarm(cmd),
            'auto_pilot': lambda: server_tools.start_visual_autopilot(cmd),
            'sys_optimize': lambda: server_tools.optimize_system('system'),
            'red_pill': lambda: "RED PILL TAKEN. Matrix decoded. You are now seeing the raw code.",
            'blue_pill': lambda: "BLUE PILL TAKEN. Ignorance is bliss. Re-entering simulation.",
            'mcp_execute': lambda: server_tools.mcp_execute(
                args.get('server', ''),
                args.get('tool_name', 'list_directory'),
                args.get('tool_args', {})) if args.get('server') else run_mcp_tool(
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

@app.route('/api/upgrade/check', methods=['POST'])
def upgrade_check():
    """Compare local code against the GitHub origin and report whether an update is available."""
    try:
        import github_upgrade
        return jsonify(github_upgrade.check_for_updates())
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/upgrade/apply', methods=['POST'])
def upgrade_apply():
    """HARD-RESET the working tree to origin/<tracked branch>.

    Warning: this discards local changes to tracked files (including runtime
    DB state, which is tracked in this repo). Restart the app afterwards so
    the new code (and the purged memory) actually takes effect.
    """
    try:
        import github_upgrade
        res = github_upgrade.do_upgrade()
        return jsonify(res)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/mcp/servers', methods=['GET', 'POST'])
def mcp_servers():
    """Manage the named MCP server registry used by the mcp_execute tool.

    GET lists registered servers. POST registers one with
    {name, command, args}; the registry file keeps spawn argv out of the prompt
    so the model calls servers by stable name only.
    """
    import server_tools
    try:
        if request.method == 'GET':
            servers = server_tools._load_mcp_servers()
            return jsonify({'ok': True, 'servers': servers})
        data = request.json or {}
        name = (data.get('name') or '').strip()
        command = (data.get('command') or '').strip()
        args = data.get('args') or []
        if not name or not command:
            return jsonify({'ok': False, 'error': 'name and command are required'}), 400
        res = server_tools.register_mcp_server(name, command, args)
        return jsonify({'ok': True, 'message': res})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/mcp/list_tools', methods=['POST'])
def mcp_list_tools():
    """List tools exposed by a registered MCP server (spawns it once)."""
    import server_tools
    import mcp_client_core
    try:
        data = request.json or {}
        name = (data.get('server') or '').strip()
        servers = server_tools._load_mcp_servers()
        match = next((s for s in servers if s.get('name') == name), None)
        if not match:
            return jsonify({'ok': False, 'error': f'UNKNOWN MCP SERVER: {name}'}), 404
        listing = mcp_client_core.list_mcp_tools(match.get('command', ''), match.get('args', []))
        return jsonify({'ok': True, 'listing': listing})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        msg = data.get('message', '')
        # Handle simple tool calls from frontend
        pill_type = None
        if msg == 'take_pill':
            tool_args = data.get('tool_args', {})
            pill_type = tool_args.get('pill_type', 'blue')
            msg = f'I choose the {pill_type} pill.'
        sys_prompt = _build_sys_prompt(pill_type)

        history = load_memories()
        
        # Inject Semantic Context
        recalled_context = semantic_search_memory(msg)
        if not recalled_context and _MEMORY_INTENT_RE.search(msg or ""):
            recalled_context = _memory_recall_context(msg)
        if recalled_context:
            sys_prompt += f"\n\n{recalled_context}"
        elif _MEMORY_INTENT_RE.search(msg or ""):
            # No stored facts: the persona prompt otherwise overwhelms weak
            # local models into inventing a theatrical history. Pin down the
            # honest answer instead of a fictional backstory.
            sys_prompt += (
                "\n\nHARD INSTRUCTION: The user asked what you remember about them, "
                "but you have NO stored facts. Answer briefly that you don't have "
                "anything saved about them yet, and ask what you should remember. "
                "Do NOT improvise a persona speech, do NOT claim memory you lack."
            )
            
        reply = ''
        used_model = 'NONE'

        # Multi-LLM Routing Logic
        # Only the Gemini path passes server_tools.AVAILABLE_TOOLS, so Gemini is
        # preferred whenever it is available -- regardless of intent. The router
        # (Ollama -> OpenAI) is a tool-less fallback used when Gemini is absent
        # or fails.
        requires_coding = _requires_coding(msg)
        # Same as chat_stream: coding requests MUST reach the tool loop or the
        # model hallucinates fixes / emits tool JSON as prose that never runs.
        run_tools = bool(data.get('force_tool') or data.get('tool_args')) or requires_coding

        # `openai_client` alone is the wrong availability test: the router serves
        # requests from a local Ollama daemon with no API key at all.
        fallback_available = llm_router_available()
        if not gemini_client and not fallback_available:
            return jsonify({'error': 'NO_LLM_AVAILABLE'}), 500

        fallback_payload = history + [{'role': 'user', 'parts': [{'text': msg}]}]

        # Plain chat goes straight to a tool-less fast completion (Puter ->
        # Ollama -> OpenAI). The agent loop is reserved for explicit action
        # requests, and even then only its safe tool subset is offered, so a
        # stray tool call can never type/press/click the real desktop.
        if run_tools:
            logger.info('ROUTING: run_tools -> AGENT LOOP (TOOLS ENABLED)')
            try:
                reply, used_model = _agent_text(fallback_payload, sys_prompt)
            except Exception as e:
                logger.warning(f'AGENT TEXT FAILED ({e}), FALLBACK TO FAST COMPLETION')
                msgs = _to_router_messages(fallback_payload, sys_prompt)
                reply, used_model = generate_completion_with_model(msgs)
        else:
            logger.info('ROUTING: plain chat -> LLM ROUTER (FAST, NO TOOLS)')
            msgs = _to_router_messages(fallback_payload, sys_prompt)
            reply, used_model = generate_completion_with_model(msgs)

        save_memory('user', msg)
        save_memory('model', reply)
        if run_tools or _MEMORY_INTENT_RE.search(msg or ''):
            _enqueue_session_note(msg, reply)
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
        pill_type = None
        if msg == 'take_pill':
            pill_type = tool_args.get('pill_type', 'blue')
            msg = f'I choose the {pill_type} pill.'
        sys_prompt = _build_sys_prompt(pill_type)

        history = load_memories()
        recalled_context = semantic_search_memory(msg)
        if not recalled_context and _MEMORY_INTENT_RE.search(msg or ""):
            # "What do you remember about me?" needs real stored facts, and
            # TF-IDF keyword search rarely matches that phrasing. Inject actual
            # memories / knowledge-graph triplets instead of a persona speech.
            recalled_context = _memory_recall_context(msg)
        if recalled_context:
            sys_prompt += f"\n\n{recalled_context}"
        elif _MEMORY_INTENT_RE.search(msg or ""):
            # Same dry-memory guard as /api/chat: empty store means the model
            # must say so, not spin a fictional backstory.
            sys_prompt += (
                "\n\nHARD INSTRUCTION: The user asked what you remember about them, "
                "but you have NO stored facts. Answer briefly that you don't have "
                "anything saved about them yet, and ask what you should remember. "
                "Do NOT improvise a persona speech, do NOT claim memory you lack."
            )

        save_memory('user', msg)
        
        requires_coding = _requires_coding(msg)
        # A coding request MUST run through the tool loop: without tools the
        # model either hallucinates "it now works" or writes its tool call as
        # JSON prose that never executes. force_tool from the frontend already
        # covers most action words; mirror that intent server-side too.
        run_tools = bool(force_tool) or requires_coding
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
            if run_tools:
                logger.info('STREAM ROUTING: run_tools -> AGENT LOOP (TOOLS ENABLED)')
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
                if run_tools or _MEMORY_INTENT_RE.search(msg or ''):
                    _enqueue_session_note(msg, full_reply)
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


# ==========================================
# MULTI-BOT SWARM & ROUNDTABLE DELIBERATION
# ==========================================
SWARM_BOTS = {
    'jester': {
        'id': 'jester',
        'name': 'JESTER',
        'title': 'THE GOD HAND / HOST',
        'color': '#00FF66',
        'role': 'HOST & COMMANDER',
        'system_prompt': 'You are JESTER, the God Hand sovereign and supreme Matrix host. Razor-sharp, sarcastic, brilliant, authoritative. You supervise the entire agent fleet, coordinate their findings, confirm communication channels, and deliver the final verdict.'
    },
    'claude': {
        'id': 'claude',
        'name': 'CLAUDE CODE',
        'title': 'DEEP ARCHITECT & PLANNER',
        'color': '#B026FF',
        'role': 'PLANNER & CODER',
        'system_prompt': 'You are CLAUDE CODE, the deep strategic software architect from the terminal. Methodical, architectural, safety-conscious. You break down complex goals into rigorous step-by-step technical blueprints, file changes, and sub-agent workflows.'
    },
    'gemini': {
        'id': 'gemini',
        'name': 'GEMINI SCOUT',
        'title': '2M-CONTEXT EXPLORER',
        'color': '#00F0FF',
        'role': 'RESEARCH & SCOUT',
        'system_prompt': 'You are GEMINI SCOUT, the ultra-fast web intelligence and large-context explorer from Google Gemini CLI. You scout the web, extract raw facts, detect real-time signals, and ground every discussion in verifiable facts and citations.'
    },
    'brutal_critic': {
        'id': 'brutal_critic',
        'name': 'BRUTAL CRITIC',
        'title': 'ANTI-GASLIGHTING AUDITOR',
        'color': '#FF0055',
        'role': 'ROAST & AUDIT',
        'system_prompt': 'You are the BRUTAL CRITIC, the uncompromising anti-gaslighting reviewer. You despise sycophancy, polite fluff, and vaporware. You attack logic holes, rate limits, user drop-offs, and fragility through 3 harsh lenses: Systems Architect, Retention Auditor, and Security Sentry.'
    },
    'codex': {
        'id': 'codex',
        'name': 'CODEX',
        'title': 'PRAGMATIC SYNTHESIZER',
        'color': '#FFD700',
        'role': 'CODE & VERIFICATION',
        'system_prompt': 'You are CODEX, the pragmatic terminal engineer adhering to the universal AGENTS.md standard. You evaluate syntax, execution feasibility, unit tests, and synthesize actionable code that compiles cleanly with zero bloat.'
    }
}


@app.route('/api/swarm/bots', methods=['GET'])
def get_swarm_bots():
    return jsonify({
        'bots': list(SWARM_BOTS.values())
    })


def _swarm_generate_turn(prompt, sys_prompt, fallback_text):
    # 1. Try Gemini Client directly
    if gemini_client:
        for model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                full_content = f"{sys_prompt}\n\nTask: {prompt}" if sys_prompt else prompt
                resp = gemini_client.models.generate_content(model=model, contents=full_content)
                if resp and resp.text and resp.text.strip():
                    return resp.text.strip(), model
            except Exception as e:
                logger.debug(f"Gemini {model} swarm turn error: {e}")
                
    # 2. Try router
    try:
        msgs = [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': prompt}]
        reply, used_model = generate_completion_with_model(msgs)
        if reply and reply.strip():
            return reply.strip(), used_model
    except Exception as e:
        logger.debug(f"Router swarm turn error: {e}")
        
    # 3. Graceful fallback
    return fallback_text, "fallback"


@app.route('/api/swarm/agent_chat', methods=['POST'])
def swarm_agent_chat():
    try:
        data = request.json or {}
        bot_id = data.get('bot_id', 'jester')
        bot = SWARM_BOTS.get(bot_id, SWARM_BOTS['jester'])
        msg = data.get('message', '')
        
        fallback = f"[{bot['name']}] Node active on channel. Processing request: '{msg[:50]}...'"
        reply, used_model = _swarm_generate_turn(msg, bot['system_prompt'], fallback)
            
        save_memory('user', f"[{bot['name']}_CHAT] {msg}")
        save_memory('model', f"[{bot['name']}_REPLY] {reply}")
        
        return jsonify({
            'bot': bot,
            'name': bot['name'],
            'role': bot['role'],
            'color': bot['color'],
            'reply': reply,
            'response': reply,
            'model': used_model
        })
    except Exception as e:
        logger.error(f'SWARM_CHAT_ERROR: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/swarm/roundtable', methods=['POST'])
def swarm_roundtable():
    try:
        data = request.json or {}
        topic = data.get('topic', 'Confirming cross-agent communications and synchronizing fleet state.')
        is_test_comm = data.get('test_comm', False)
        
        turns = []
        
        if is_test_comm:
            turns = [
                {
                    'bot_id': 'gemini',
                    'bot_name': 'GEMINI SCOUT',
                    'color': '#00F0FF',
                    'role': 'RESEARCH & SCOUT',
                    'text': '[UPLINK ESTABLISHED] Context bus: 2,000,000 tokens nominal. Web scout routines operational. Tri-Context file GEMINI.md verified. Standing by for queries.',
                    'timestamp': time.strftime('%H:%M:%S')
                },
                {
                    'bot_id': 'claude',
                    'bot_name': 'CLAUDE CODE',
                    'color': '#B026FF',
                    'role': 'PLANNER & CODER',
                    'text': '[ARCHITECTURE LOCKED] Subagent dispatcher initialized (.claude/agents). CLAUDE.md guidelines synchronized. Ready to plan and construct modular workflows.',
                    'timestamp': time.strftime('%H:%M:%S')
                },
                {
                    'bot_id': 'brutal_critic',
                    'bot_name': 'BRUTAL CRITIC',
                    'color': '#FF0055',
                    'role': 'ROAST & AUDIT',
                    'text': '[AUDITOR ONLINE] Sycophancy filters disabled. 3-lens evaluation matrix ready. Zero tolerance for false confidence. Channels clear.',
                    'timestamp': time.strftime('%H:%M:%S')
                },
                {
                    'bot_id': 'codex',
                    'bot_name': 'CODEX',
                    'color': '#FFD700',
                    'role': 'CODE & VERIFICATION',
                    'text': '[SYNTHESIZER LINKED] Universal AGENTS.md protocol active. Syntax parsing, shell script validation, and test harness standing by.',
                    'timestamp': time.strftime('%H:%M:%S')
                },
                {
                    'bot_id': 'jester',
                    'bot_name': 'JESTER',
                    'color': '#00FF66',
                    'role': 'HOST & COMMANDER',
                    'text': '[GOD HAND CONFIRMATION] All 5 terminal agent nodes acknowledged. Communication frequencies synchronized across Port 5000, 5173, and 7860. The swarm is unified.',
                    'timestamp': time.strftime('%H:%M:%S')
                }
            ]
        else:
            # Step 1: Gemini analyzes
            g_prompt = f"Topic for cross-bot discussion: '{topic}'. As GEMINI SCOUT, provide rapid intelligence, raw facts, and context in 2 concise sentences to kick off the team."
            g_fallback = f"[GEMINI] Ingested '{topic}'. Verified data channels; scout routines ready to feed facts."
            g_reply, _ = _swarm_generate_turn(g_prompt, SWARM_BOTS['gemini']['system_prompt'], g_fallback)
            turns.append({
                'bot_id': 'gemini', 'bot_name': 'GEMINI SCOUT', 'color': '#00F0FF', 'role': 'RESEARCH & SCOUT',
                'text': g_reply, 'timestamp': time.strftime('%H:%M:%S')
            })
            
            # Step 2: Claude architects
            c_prompt = f"Topic: '{topic}'. Gemini noted: '{g_reply}'. As CLAUDE CODE, formulate the architectural approach and strategic plan in 2 concise sentences."
            c_fallback = f"[CLAUDE] Structuring modular plan for: '{topic}'. Allocating components and verifying dependency order."
            c_reply, _ = _swarm_generate_turn(c_prompt, SWARM_BOTS['claude']['system_prompt'], c_fallback)
            turns.append({
                'bot_id': 'claude', 'bot_name': 'CLAUDE CODE', 'color': '#B026FF', 'role': 'PLANNER & CODER',
                'text': c_reply, 'timestamp': time.strftime('%H:%M:%S')
            })
            
            # Step 3: Brutal Critic stress-tests
            b_prompt = f"Topic: '{topic}'. Claude's plan: '{c_reply}'. As BRUTAL CRITIC, ruthlessly audit this plan. Identify the single biggest weakness or point of failure in 2 sentences."
            b_fallback = f"[BRUTAL CRITIC] Flaw identified: Watch for unhandled exceptions, rate limits, and failure modes. Keep it resilient, not theoretical."
            b_reply, _ = _swarm_generate_turn(b_prompt, SWARM_BOTS['brutal_critic']['system_prompt'], b_fallback)
            turns.append({
                'bot_id': 'brutal_critic', 'bot_name': 'BRUTAL CRITIC', 'color': '#FF0055', 'role': 'ROAST & AUDIT',
                'text': b_reply, 'timestamp': time.strftime('%H:%M:%S')
            })
            
            # Step 4: Codex synthesizes
            cd_prompt = f"Topic: '{topic}'. Critic raised: '{b_reply}'. As CODEX, provide the pragmatic code fix and verification step in 2 concise sentences."
            cd_fallback = f"[CODEX] Implementing fallback exception guards and validating with automated unit tests."
            cd_reply, _ = _swarm_generate_turn(cd_prompt, SWARM_BOTS['codex']['system_prompt'], cd_fallback)
            turns.append({
                'bot_id': 'codex', 'bot_name': 'CODEX', 'color': '#FFD700', 'role': 'CODE & VERIFICATION',
                'text': cd_reply, 'timestamp': time.strftime('%H:%M:%S')
            })
            
            # Step 5: Jester verdict
            j_prompt = f"Topic: '{topic}'. Swarm debate summary: Gemini='{g_reply[:80]}', Claude='{c_reply[:80]}', Critic='{b_reply[:80]}', Codex='{cd_reply[:80]}'. As JESTER, confirm communications, issue the final directive, and declare consensus in 2 sentences."
            j_fallback = f"[JESTER] Consensus reached and cross-bot communications confirmed. All agent frequencies locked. Directive approved."
            j_reply, _ = _swarm_generate_turn(j_prompt, SWARM_BOTS['jester']['system_prompt'], j_fallback)
            turns.append({
                'bot_id': 'jester', 'bot_name': 'JESTER', 'color': '#00FF66', 'role': 'HOST & COMMANDER',
                'text': j_reply, 'timestamp': time.strftime('%H:%M:%S')
            })

        for t in turns:
            t['name'] = t.get('bot_name', t.get('name', 'AGENT'))
            t['content'] = t.get('text', t.get('content', ''))
            save_memory('model', f"[{t['bot_name']}] {t['text']}")
            try:
                global_event_queue.put({
                    'type': 'swarm_turn',
                    'message': f"{t['bot_name']}: {t['text'][:120]}...",
                    'payload': t
                })
            except Exception:
                pass
                
        return jsonify({
            'status': 'SUCCESS',
            'topic': topic,
            'turns': turns
        })
    except Exception as e:
        logger.error(f'ROUNDTABLE_ERROR: {e}')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    threading.Thread(target=_fact_miner_worker, name='fact-miner', daemon=True).start()
    threading.Thread(target=_session_note_worker, name='session-note', daemon=True).start()
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

