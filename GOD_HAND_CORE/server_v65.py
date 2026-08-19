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
import cv2
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv
from duckduckgo_search import DDGS
import pyautogui
import webbrowser
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'jester_V65_QUANTUM.db')
load_dotenv()
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('QUANTUM_CORE')
MODELS = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-flash-latest']
API_KEY = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=API_KEY)

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        conn.commit(); conn.close()
    except: pass

def save_memory(role, content):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO history (role, content) VALUES (?, ?)', (role, content))
        conn.commit(); conn.close()
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
init_db()
