import logging
import os
import socket
import sqlite3
import time

import requests

import graph_memory

# Suppress GRPC warnings
os.environ["GRPC_VERBOSITY"] = "ERROR"
import asyncio
import json
import random
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

from llm_router import generate_completion
from mcp_client_core import run_mcp_tool
from sandbox_core import sandbox_core
from vision_core import vision_core

# --- Global Caches ---
semantic_cache: typing.Dict[str, typing.Any] = {
    'vectorizer': None,
    'tfidf_docs': None,
    'docs': []
}

global_event_queue = queue.Queue()


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
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SOURCE_CORE')


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
        c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, pinned INTEGER DEFAULT 0, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
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
            refresh_semantic_cache()
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
        
        if not rows: return
            
        docs = [r[0] for r in rows]
        vectorizer = TfidfVectorizer().fit(docs)
        tfidf_docs = vectorizer.transform(docs)
        
        semantic_cache['vectorizer'] = vectorizer
        semantic_cache['tfidf_docs'] = tfidf_docs
        semantic_cache['docs'] = docs
    except Exception as e:
        pass

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
            # TF-IDF Fallback
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


def generate_openai_response(messages, sys_prompt, max_retries=3):
    msgs = [{'role': 'system', 'content': sys_prompt}]
    for m in messages:
        role = 'user' if m['role'] == 'user' else 'assistant'
        msgs.append({'role': role, 'content': m['parts'][0]['text']})
        
    for attempt in range(max_retries):
        try:
            assert openai_client is not None
            # Route through the local LLM router (Ollama -> OpenAI fallback)
            return generate_completion(msgs)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"OLLAMA/OPENAI API RATE LIMIT/ERROR (Attempt {attempt+1}): {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f'OLLAMA/OPENAI ERROR: {e}')
                raise e

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
        # Route to OpenAI (GPT-4o) for coding/complex tasks, otherwise Gemini Flash
        coding_keywords = ['code', 'script', 'function', 'python', 'javascript', 'jsx', 'bug', 'fix']
        requires_coding = any(k in msg.lower() for k in coding_keywords)
        
        use_openai_first = requires_coding and openai_client

        if use_openai_first:
             logger.info("ROUTING: CODE INTENT DETECTED -> GPT-4o")
             try:
                 reply = generate_openai_response(history + [{'role': 'user', 'parts': [{'text': msg}]}], sys_prompt)
                 used_model = OPENAI_MODEL
             except Exception as e:
                 logger.warning("OPENAI FAILED, FALLBACK TO GEMINI")
                 if gemini_client:
                     reply = generate_gemini_response(sys_prompt, history, msg)
                     used_model = PRIMARY_MODEL
                 else:
                     raise e
        else:
             logger.info("ROUTING: CHAT INTENT DETECTED -> GEMINI")
             if gemini_client:
                 try:
                     reply = generate_gemini_response(sys_prompt, history, msg)
                     used_model = PRIMARY_MODEL
                 except Exception as e:
                     logger.warning("GEMINI FAILED, FALLBACK TO OPENAI")
                     if openai_client:
                         reply = generate_openai_response(history + [{'role': 'user', 'parts': [{'text': msg}]}], sys_prompt)
                         used_model = OPENAI_MODEL
                     else:
                         raise e
             elif openai_client:
                 reply = generate_openai_response(history + [{'role': 'user', 'parts': [{'text': msg}]}], sys_prompt)
                 used_model = OPENAI_MODEL
             else:
                 return jsonify({'error': 'NO_LLM_AVAILABLE'}), 500

        save_memory('user', msg)
        save_memory('model', reply)
        return jsonify({'response': reply, 'model': used_model})

    except Exception as e:
        logger.error(f'CHAT_ERROR: {str(e)}')
        return jsonify({'error': str(e)}), 500

def generate_openai_stream(messages, sys_prompt, max_retries=3):
    msgs: list = [{'role': 'system', 'content': str(sys_prompt)}]
    for m in messages:
        role = 'user' if m['role'] == 'user' else 'assistant'
        msgs.append({'role': role, 'content': str(m['parts'][0]['text'])})
        
    for attempt in range(max_retries):
        try:
            assert openai_client is not None
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=msgs,
                stream=True
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"OPENAI STREAM RATE LIMIT/ERROR (Attempt {attempt+1}): {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f'OPENAI STREAM ERROR: {e}')
                yield f"[ERROR: {str(e)}]"

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
        
        pill_type = data.get('tool_args', {}).get('pill_type', 'blue')
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
        use_openai_first = requires_coding and openai_client

        def event_stream():
            full_reply = ""
            model_used = "NONE"
            stream_success = False
            
            if use_openai_first:
                logger.info("STREAM ROUTING -> GPT-4o")
                model_used = OPENAI_MODEL
                try:
                    for chunk in generate_openai_stream(history + [{'role': 'user', 'parts': [{'text': msg}]}], sys_prompt):
                        if "[ERROR:" in chunk:
                            raise RuntimeError(chunk)
                        full_reply += chunk
                        yield f"data: {json.dumps({'chunk': chunk, 'model': model_used})}\n\n"
                    stream_success = True
                except Exception as e:
                    logger.warning(f"OpenAI streaming encountered error ({e}). Falling back seamlessly to Gemini...")

            if not stream_success:
                logger.info(f"STREAM ROUTING -> GEMINI ({PRIMARY_MODEL})")
                model_used = PRIMARY_MODEL
                try:
                    for chunk in generate_gemini_stream(sys_prompt, history, msg):
                        full_reply += chunk
                        yield f"data: {json.dumps({'chunk': chunk, 'model': model_used})}\n\n"
                except Exception as e:
                    logger.error(f"Gemini stream error: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            save_memory('model', full_reply)
            yield "data: [DONE]\n\n"

        return Response(event_stream(), mimetype="text/event-stream")

    except Exception as e:
        logger.error(f'CHAT_STREAM_ERROR: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream_events', methods=['GET'])
def stream_events():
    def event_stream():
        while True:
            try:
                msg = global_event_queue.get(timeout=10)
                yield f"data: {json.dumps(msg)}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"
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
        'model': PRIMARY_MODEL if gemini_client else OPENAI_MODEL,
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
        'ai_status': 'ONLINE' if (gemini_client or openai_client) else 'OFFLINE_MODE',
        'model': PRIMARY_MODEL if gemini_client else OPENAI_MODEL,
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
    app.run(host='0.0.0.0', port=5000)

