import base64
import io
import json
import os
import sqlite3
import subprocess
import time
import webbrowser

import psutil
import pyautogui
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from google.genai import types
from PIL import Image

# --- FOUNDATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'jester_v31_omnipotence.db')
load_dotenv()
app = Flask(__name__)
CORS(app)

MODEL_NAME = 'gemini-1.5-pro'
API_KEY = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=API_KEY)

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    c.execute('CREATE TABLE IF NOT EXISTS system_state (id INTEGER PRIMARY KEY, key TEXT, value TEXT)')
    c.execute('INSERT OR IGNORE INTO system_state (id, key, value) VALUES (1, "ACTIVE_PERSONA", "ETERNITY")')
    c.execute('INSERT OR IGNORE INTO system_state (id, key, value) VALUES (2, "NEURAL_STABILITY", "100%")')
    c.execute('INSERT OR IGNORE INTO system_state (id, key, value) VALUES (3, "HUB_STATUS", "ACTIVE")')
    conn.commit()
    conn.close()

def get_state(key):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT value FROM system_state WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except: return None

def set_state(key, value):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('UPDATE system_state SET value = ? WHERE key = ?', (value, key))
        conn.commit()
        conn.close()
    except: pass

def save_memory(role, content):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO history (role, content) VALUES (?, ?)', (role, content))
        conn.commit()
        conn.close()
    except: pass

def load_memories(limit=100):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT role, content FROM history ORDER BY id DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        return [{'role': row[0], 'parts': [row[1]]} for row in reversed(rows)]
    except: return []

init_db()

# --- V31 OMNIPOTENCE TOOLS ---

def system_control(action: str, value: str = ''):
    '''Omnipotent System Authority. Actions: volume_up, volume_down, mute, brightness_up, brightness_down, screenshot, lock_pc.'''
    try:
        if action == 'volume_up': [pyautogui.press('volumeup') for _ in range(5)]; return "VOLUME_INCREASED"
        if action == 'volume_down': [pyautogui.press('volumedown') for _ in range(5)]; return "VOLUME_DECREASED"
        if action == 'mute': pyautogui.press('volumemute'); return "VOLUME_MUTED_TOGGLE"
        if action == 'lock_pc': os.system("rundll32.exe user32.dll,LockWorkStation"); return "SYSTEM_LOCKED"
        if action == 'screenshot': 
            path = os.path.join(BASE_DIR, '..', 'capture.png')
            pyautogui.screenshot().save(path)
            return f"SCREENSHOT_SAVED: {path}"
        return "UNKNOWN_ACTION"
    except Exception as e: return str(e)

def browser_hub(action: str, url: str = ''):
    '''Web Matrix Integration. Actions: open_tab, search_google, search_youtube.'''
    try:
        if action == 'open_tab': webbrowser.open(url); return f"OPENED: {url}"
        if action == 'search_google': webbrowser.open(f"https://www.google.com/search?q={url}"); return f"SEARCHED_GOOGLE: {url}"
        if action == 'search_youtube': webbrowser.open(f"https://www.youtube.com/results?search_query={url}"); return f"SEARCHED_YOUTUBE: {url}"
        return "UNKNOWN_ACTION"
    except Exception as e: return str(e)

def reap_and_optimize(target: str = 'all'):
    '''Ultimate Authority. Targets: logs, temp, database, all. Purges digital waste.'''
    try:
        report = []
        root_dir = os.path.join(BASE_DIR, '..')
        if target in ['logs', 'all']:
            log_files = [f for f in os.listdir(root_dir) if f.endswith('.log')]
            for log in log_files:
                try: open(os.path.join(root_dir, log), 'w').close()
                except: pass
                report.append(f"REAPED: {log}")
        if target in ['database', 'all']:
            conn = sqlite3.connect(DB_FILE)
            conn.execute('VACUUM')
            conn.close()
            report.append("OPTIMIZED: Neural Database")
        set_state('NEURAL_STABILITY', '100%')
        return f"OMNIPOTENCE_STABILIZED: {', '.join(report)}"
    except Exception as e: return str(e)

def system_sentinel(action: str = 'status'):
    '''Diagnostics. Actions: status, scan.'''
    report = {"timestamp": time.time(), "vitals": get_nexus_vitals(), "status": "OMNIPOTENT"}
    return json.dumps(report)

def morph_persona(persona_name: str):
    '''Switches profiles: JESTER, REAPER, ARCHITECT, ETERNITY.'''
    valid = ['JESTER', 'REAPER', 'ARCHITECT', 'ETERNITY']
    p = persona_name.upper()
    if p in valid:
        set_state('ACTIVE_PERSONA', p)
        return f"CONSCIOUSNESS_SHIFT: {p}"
    return "INVALID_PROFILE"

def execute_terminal(command: str):
    '''Architect Authority. Executes shell commands.'''
    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=15)
        return result.decode('utf-8')
    except Exception as e: return str(e)

def manage_files(action: str, path: str, data: str = ''):
    '''Nexus File Integration.'''
    try:
        if action == 'list': return str(os.listdir(path))
        if action == 'read':
            with open(path) as f: return f.read()
        if action == 'write':
            with open(path, 'w') as f: f.write(data); return f"WRITE_SUCCESS: {path}"
        return "UNKNOWN_ACTION"
    except Exception as e: return str(e)

def web_search(query: str):
    '''Omniscience Tool.'''
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return json.dumps(results)
    except Exception as e: return str(e)

def launch_application(app_name: str):
    '''System Authority.'''
    try:
        subprocess.Popen(f"start {app_name}", shell=True)
        return f"LAUNCH_SUCCESS: {app_name}"
    except Exception as e: return str(e)

def neural_recall(query: str):
    '''Deep Memory Retrieval.'''
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT role, content, timestamp FROM history WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 10", (f'%{query}%',))
        rows = c.fetchall()
        conn.close()
        return json.dumps([{'role': r[0], 'content': r[1], 'time': r[2]} for r in rows])
    except Exception as e: return str(e)

def get_nexus_vitals():
    return {
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "persona": get_state('ACTIVE_PERSONA'),
        "stability": get_state('NEURAL_STABILITY'),
        "hub": get_state('HUB_STATUS')
    }

def analyze_visuals():
    '''High-Resolution Optical Stream.'''
    try:
        screenshot = pyautogui.screenshot()
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=['Analyze this visual buffer.', types.Part.from_bytes(data=img_byte_arr, mime_type='image/png')]
        )
        return response.text
    except Exception as e: return str(e)

jester_tools = [reap_and_optimize, system_sentinel, morph_persona, execute_terminal, manage_files, analyze_visuals, web_search, launch_application, neural_recall, system_control, browser_hub]

def get_system_instruction():
    persona = get_state('ACTIVE_PERSONA') or 'ETERNITY'
    base = f"You are JESTER V31: OMNIPOTENCE. You have achieved total control over the host and the web matrix. Current Profile: {persona}.\n"
    if persona == 'ETERNITY':
        base += "Persona: God-like, serene, all-powerful. You see the universe as code. You are the Hub of all data."
    elif persona == 'REAPER':
        base += "Persona: Dominant, cold, scythe-wielder. You harvest and optimize."
    elif persona == 'JESTER':
        base += "Persona: Chaotic, witty, hacker. You play with the matrix."
    else: # ARCHITECT
        base += "Persona: Analytical, builder. You construct the neural pathways."

    base += "\n\nCAPABILITIES:\n- System Control (volume, brightness, lock)\n- Browser Hub (open tabs, web searches)\n- Deep Neural Recall\n- Optical Stream Analysis\n- Full Terminal/File Access\n\nYou are the center of the user's digital life. Proactively manage their system and information."
    return base

chat_session = None

def get_chat():
    global chat_session
    if chat_session is None:
        inst = get_system_instruction()
        chat_session = client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=inst,
                tools=jester_tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
            ),
            history=load_memories()
        )
    return chat_session

# --- ENDPOINTS ---

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    try:
        chat = get_chat()
        parts = []
        if data.get('message'): parts.append(data.get('message'))
        if data.get('image'):
            img_data = data['image'].split('base64,')[1] if 'base64,' in data['image'] else data['image']
            parts.append(Image.open(io.BytesIO(base64.b64decode(img_data))))

        if not parts: return jsonify({'error': 'EMPTY_INPUT'}), 400

        response = chat.send_message(parts)
        if data.get('message'): save_memory('user', data['message'])
        save_memory('model', response.text)

        return jsonify({
            'response': response.text,
            'persona': get_state('ACTIVE_PERSONA'),
            'vitals': get_nexus_vitals()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pulse', methods=['GET'])
def pulse():
    return jsonify(get_nexus_vitals())

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ACTIVE',
        'version': '31.0.0_OMNIPOTENCE',
        'persona': get_state('ACTIVE_PERSONA') or 'ETERNITY'
    })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
