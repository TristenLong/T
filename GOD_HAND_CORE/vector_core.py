import json
import os
import sqlite3

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, '.env'), override=True)

DB_FILE = os.path.join(BASE_DIR, 'jester_brain.db')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except:
        pass

def get_embedding(text):
    if not client: return None
    try:
        response = client.embeddings.create(input=text, model="text-embedding-3-small")
        return response.data[0].embedding
    except: return None

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS semantic_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, embedding BLOB, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

def save_semantic(content):
    if not client: return "NO_CLIENT"
    vec = get_embedding(content)
    if not vec: return "EMBEDDING_FAIL"
    vec_blob = np.array(vec, dtype=np.float32).tobytes()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO semantic_memory (content, embedding) VALUES (?, ?)", (content, vec_blob))
        conn.commit()
        conn.close()
        return "SAVED"
    except Exception as e: return str(e)

def search_semantic(query, limit=5, threshold=0.3):
    if not client: return []
    q_vec = get_embedding(query)
    if not q_vec: return []
    q_arr = np.array(q_vec, dtype=np.float32)
    q_norm = np.linalg.norm(q_arr)
    results = []
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT content, embedding, timestamp FROM semantic_memory")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            if not r[1]: continue
            vec_arr = np.frombuffer(r[1], dtype=np.float32)
            dot = np.dot(q_arr, vec_arr)
            norm = np.linalg.norm(vec_arr)
            sim = 0 if (norm==0 or q_norm==0) else dot/(q_norm*norm)
            if sim > threshold: results.append((sim, r[0], r[2]))
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]
    except: return []

init_db()
