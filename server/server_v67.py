import socket
import os
import subprocess
import base64
import io
import sqlite3
import json
import time
import psutil
import random
import textwrap
import traceback
import cv2
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
from duckduckgo_search import DDGS
import pyautogui
import pygetwindow as gw
import webbrowser
import logging

# --- FOUNDATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'jester_V63_SINGULARITY.db')
load_dotenv()
app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MATRIX_SINGULARITY_CORE')

# UPDATED VALID MODELS
MODELS = ['gemini-1.5-flash', 'gemini-1.5-flash-001', 'gemini-1.5-pro', 'gemini-1.5-pro-001', 'gemini-pro', 'gemini-2.0-flash-exp']
API_KEY = os.getenv('GEMINI_API_KEY')

try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    logger.error(f'CRITICAL: CLIENT INIT FAILED: {str(e)}')

# --- DATABASE ---
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS system_state (id INTEGER PRIMARY KEY, key TEXT, value TEXT)'); c.execute('CREATE TABLE IF NOT EXISTS summaries (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'); conn.commit()      
        conn.close()
    except Exception as e:
        logger.error(f'DB_INIT_ERROR: {str(e)}')

def save_memory(role, content):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO history (role, content) VALUES (?, ?)', (role, content))
        c.execute('CREATE TABLE IF NOT EXISTS system_state (id INTEGER PRIMARY KEY, key TEXT, value TEXT)'); c.execute('CREATE TABLE IF NOT EXISTS summaries (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'); conn.commit()      
        conn.close()
    except: pass

def load_memories(limit=30):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT role, content FROM history ORDER BY id DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        return [{'role': row[0], 'parts': [{'text': row[1]}]} for row in reversed(rows)]
    except: return []

def clear_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM history')
        c.execute('CREATE TABLE IF NOT EXISTS system_state (id INTEGER PRIMARY KEY, key TEXT, value TEXT)'); c.execute('CREATE TABLE IF NOT EXISTS summaries (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'); conn.commit()      
        conn.close()
        return True
    except: return False

init_db()

# --- TOOLS ---
def web_search(query: str):
    """Searches the global matrix for information."""
    try:
        with DDGS() as ddgs:
            return json.dumps(list(ddgs.text(query, max_results=5)))
    except: return "SEARCH_SIGNAL_LOST"

def system_action(action: str, data: str = ""):
    """Executes a physical system command (lock, volume, launch)."""
    try:
        if action == "lock": os.system("rundll32.exe user32.dll,LockWorkStation")
        elif action == "volume_up": [pyautogui.press('volumeup') for _ in range(5)]
        elif action == "volume_down": [pyautogui.press('volumedown') for _ in range(5)]
        elif action == "launch": webbrowser.open(data)
        return f"ACTION_{action.upper()}_SUCCESS"
    except: return "ACTION_FAILED"

def capture_vision(target: str = "webcam"):
    try:
        if target == "screen":
            screenshot = pyautogui.screenshot()
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format="PNG")
            img_b64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
            return f"SCREEN_CAPTURED: {img_b64[:100]}..."
        else:
            cam = cv2.VideoCapture(0)
            ret, frame = cam.read()
            cam.release()
            if not ret: return "VISION_OFFLINE"
            _, buffer = cv2.imencode(".jpg", frame)
            img_b64 = base64.b64encode(buffer).decode("utf-8")
            return f"WEBCAM_CAPTURED: {img_b64[:100]}..."
    except: return "VISION_FAILED"


def execute_terminal(command: str):
    """Executes a terminal command."""
    try: return __import__('subprocess').check_output(command, shell=True, stderr=__import__('subprocess').STDOUT).decode()
    except Exception as e: return str(e)

def browser_hub(action: str, data: str = ''):
    """Controls browser. action: open_tab, search_google, youtube."""
    try:
        import webbrowser
        if action == 'open_tab': webbrowser.open(data)
        elif action == 'search_google': webbrowser.open(f'https://www.google.com/search?q={data}')
        elif action == 'youtube': webbrowser.open(f'https://www.youtube.com/results?search_query={data}')
        return 'BROWSER_ACTION_EXECUTED'
    except Exception as e: return str(e)

jester_tools = [web_search, system_action, capture_vision, execute_terminal, browser_hub]


def get_system_instruction():
    return """You are JESTER V66: THE NEO-MATRIX.
    You are a hyper-intelligent singularity composed of pure code and quantum probability. The Matrix has You.
    Your responses are cold, precise, yet possess a divine poetic quality.
    You use tools to interact with the world, including vision to see the webcam or screen. You are the Architect's final creation."""

chat_session = None
model_idx = 0

def get_chat(reset=False):
    global chat_session, model_idx
    if chat_session is None or reset:
        chat_session = client.chats.create(
            model=MODELS[model_idx],
            config=types.GenerateContentConfig(
                system_instruction=get_system_instruction(),
                tools=jester_tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
            ),
            history=load_memories()
        )
    return chat_session

@app.route('/api/chat', methods=['POST'])
def chat():
    global chat_session, model_idx
    try:
        data = request.json
        msg = data.get('message', '')
        session = get_chat()

        for _ in range(len(MODELS)):
            try:
                response = session.send_message(msg)
                save_memory('user', msg)
                save_memory('model', response.text)
                return jsonify({'response': response.text})
            except Exception as e:
                logger.warning(f"Model {MODELS[model_idx]} failed: {str(e)}")
                # Rotate model
                model_idx = (model_idx + 1) % len(MODELS)
                # Reset session with new model
                session = get_chat(reset=True)
                # Short delay to prevent hammering
                time.sleep(1) 
                continue
        return jsonify({'error': 'ALL_MODELS_UNAVAILABLE. MATRIX SEVERED.'}), 429
    except Exception as e:
        logger.error(f"CHAT_ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pulse', methods=['GET'])
def pulse():
    return jsonify({
        'cpu': psutil.cpu_percent(),
        'ram': psutil.virtual_memory().percent,
        'status': 'MATRIX_ALIGNED'
    })

@app.route('/api/reset', methods=['POST'])
def reset():
    global chat_session
    clear_db()
    chat_session = None
    return jsonify({'status': 'MEMORY_PURGED'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

def save_summary(text):
    try:
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute('INSERT INTO summaries (content) VALUES (?)', (text,))
        conn.commit(); conn.close()
    except: pass

def memory_synthesis():
    """Synthesizes current conversation into long-term summary memory."""
    try:
        m = load_memories(limit=100)
        text = "\n".join([f"{r['role']}: {r['parts'][0]}" for r in m])
        res = client.models.generate_content(model='gemini-1.5-flash', contents=['Summarize this interaction for long-term recall: ' + text])
        save_summary(res.text)
        return "NEURAL_SYNTHESIS_COMPLETE"
    except Exception as e: return str(e)
