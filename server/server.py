import socket
import os
import sqlite3
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv
import psutil
from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DB_FILE = os.path.join(BASE_DIR, 'jester_V73_OMNIPRESENCE.db')

# Load .env from root
load_dotenv(os.path.join(ROOT_DIR, '.env'), override=True)

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SOURCE_CORE')


def get_miner_data():
    log_path = r"C:\Users\trist\Downloads\SRBMiner-Multi-3-1-1-win64\SRBMiner-Multi-3-1-1\Log.txt"
    data = {'hashrate': 'OFFLINE', 'algo': 'Unknown', 'status': 'STOPPED'}
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-20:]
                for line in reversed(lines):
                    if "Hashrate" in line:
                        # Example: [2026-01-22 18:40:49] Algorithm: randomx Hashrate: 1200 H/s
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if "Hashrate" in part:
                                data['hashrate'] = parts[i+1] if i+1 < len(parts) else "N/A"
                                data['status'] = "MINING"
                                break
                    if "Algorithm" in line:
                        # Try to find algo
                        pass
        except:
            pass
    return data


GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PRIMARY_MODEL = os.getenv('JESTER_PRIMARY_LLM', 'gemini-2.0-flash-lite')
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
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO history (role, content) VALUES (?, ?)', (role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f'SAVE_MEMORY ERROR: {e}')

def load_memories(limit=10):
    try:
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
        logger.error(f'LOAD_MEMORIES ERROR: {e}')
        return []

def semantic_search_memory(query, top_k=3):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT content FROM history WHERE role="user" ORDER BY id DESC LIMIT 500')
        rows = c.fetchall()
        conn.close()
        
        if not rows: return ""
        
        docs = [r[0] for r in rows]
        vectorizer = TfidfVectorizer().fit(docs + [query])
        tfidf_docs = vectorizer.transform(docs)
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

def generate_openai_response(messages, sys_prompt):
    try:
        msgs = [{'role': 'system', 'content': sys_prompt}]
        for m in messages:
            role = 'user' if m['role'] == 'user' else 'assistant'
            msgs.append({'role': role, 'content': m['parts'][0]['text']})
        
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=msgs
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f'OPENAI ERROR: {e}')
        raise e

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
                     chat = gemini_client.chats.create(model=PRIMARY_MODEL, config=types.GenerateContentConfig(system_instruction=sys_prompt), history=history)
                     reply = chat.send_message(msg).text
                     used_model = PRIMARY_MODEL
                 else:
                     raise e
        else:
             logger.info("ROUTING: CHAT INTENT DETECTED -> GEMINI")
             if gemini_client:
                 try:
                     chat = gemini_client.chats.create(model=PRIMARY_MODEL, config=types.GenerateContentConfig(system_instruction=sys_prompt), history=history)
                     reply = chat.send_message(msg).text
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
    miner = get_miner_data()
    return jsonify({
        'cpu': psutil.cpu_percent(),
        'ram': psutil.virtual_memory().percent,
        'miner': miner,
        'ai_status': 'ONLINE' if (gemini_client or openai_client) else 'OFFLINE_MODE'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
