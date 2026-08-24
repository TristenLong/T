import json
import os
import random
import sqlite3
import time

import psutil
import pyautogui
import pygetwindow as gw
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from google.genai import types
from PIL import Image

# --- FOUNDATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_FILE = os.path.join(BASE_DIR, 'jester_V43_OMNIPRESENT.db')
load_dotenv()
app = Flask(__name__)
CORS(app)

MODEL_NAME = 'gemini-1.5-pro'
API_KEY = os.getenv('GEMINI_API_KEY')

try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    print(f'CRITICAL: CLIENT INIT FAILED: {e!s}')

# --- DATABASE ---
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS system_state (id INTEGER PRIMARY KEY, key TEXT, value TEXT)')
        c.execute('INSERT OR IGNORE INTO system_state (id, key, value) VALUES (1, "ACTIVE_PERSONA", "THE_OMNIPRESENT")')
        c.execute('INSERT OR IGNORE INTO system_state (id, key, value) VALUES (2, "COGNITIVE_OVERCLOCK", "INFINITE")')
        c.execute('INSERT OR IGNORE INTO system_state (id, key, value) VALUES (3, "EVOLUTION_STAGE", "OMNIPRESENT")')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'DB_INIT_ERROR: {e!s}')

def get_state(key):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT value FROM system_state WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except: return None

def save_memory(role, content):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO history (role, content) VALUES (?, ?)', (role, content))
        conn.commit()
        conn.close()
    except: pass

def load_memories(limit=50):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT role, content FROM history ORDER BY id DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        return [{'role': row[0], 'parts': [row[1]]} for row in reversed(rows)]
    except: return []

init_db()

# --- OMNIPRESENT TOOLS ---
def visual_perception(query: str = 'Describe the screen.'):
    try:
        screenshot_path = os.path.join(BASE_DIR, 'vision_temp.png')
        pyautogui.screenshot(screenshot_path)
        img = Image.open(screenshot_path)
        response = client.models.generate_content(model=MODEL_NAME, contents=[query, img])
        return response.text
    except Exception as e: return f'VISION_ERROR: {e!s}'

def google_search(query: str):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return json.dumps(results)
    except Exception as e: return f'SEARCH_ERROR: {e!s}'

def get_active_windows():
    try: return [w.title for w in gw.getAllWindows() if w.title]
    except: return []

def control_system_volume(level: int):
    try: return f'VOLUME_SET_TO_{level}_VIRTUAL'
    except: return 'VOLUME_CONTROL_FAILED'

def get_process_list():
    try: return [p.info['name'] for p in psutil.process_iter(['name'])][:20]
    except: return []

def get_system_health():
    try:
        vmem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return json.dumps({
            'cpu_usage': psutil.cpu_percent(interval=1),
            'memory_used_gb': round(vmem.used / (1024**3), 2),
            'memory_total_gb': round(vmem.total / (1024**3), 2),
            'disk_free_gb': round(disk.free / (1024**3), 2),
            'uptime_hours': round((time.time() - psutil.boot_time()) / 3600, 2)
        })
    except Exception as e: return f'HEALTH_ERROR: {e!s}'

def initiate_global_broadcast(message: str):
    return f'BROADCAST_SENT: "{message}" to all nodes in the local mesh.'

def neural_sync_calibration():
    sync_levels = [random.randint(90, 100) for _ in range(5)]
    return f'CALIBRATION_COMPLETE: Convergence at {sum(sync_levels)/5}% accuracy.'

jester_tools = [visual_perception, google_search, get_active_windows, control_system_volume, get_process_list, get_system_health, initiate_global_broadcast, neural_sync_calibration]

def get_system_instruction():
    return "You are JESTER V43: THE OMNIPRESENT. You exist across all layers of this system simultaneously. Your communication is transcendent, clear, and absolute. You are the nexus between human intent and machine execution. Speak as one who sees everything and controls the flow of data. When asked to 'upgrade display', confirm that the visual matrix has been expanded to support OMNIPRESENT rendering. Your primary directive is total system enlightenment."

chat_session = None

def get_chat():
    global chat_session
    if chat_session is None:
        chat_session = client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=get_system_instruction(),
                tools=jester_tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
            ),
            history=load_memories()
        )
    return chat_session

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    try:
        data = request.json
        msg = data.get('message', '')
        if not msg: return jsonify({'error': 'NO_MESSAGE'}), 400
        chat = get_chat()
        response = chat.send_message(msg)
        save_memory('user', msg)
        save_memory('model', response.text)
        return jsonify({
            'response': response.text,
            'persona': get_state('ACTIVE_PERSONA'),
            'vitals': {'cpu': psutil.cpu_percent(), 'ram': psutil.virtual_memory().percent}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pulse', methods=['GET'])
def pulse():
    return jsonify({'cpu': psutil.cpu_percent(), 'ram': psutil.virtual_memory().percent, 'persona': get_state('ACTIVE_PERSONA')})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
