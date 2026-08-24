import json
import os
import sqlite3

from google import genai
from loguru import logger
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "jester_brain.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS knowledge_graph (id INTEGER PRIMARY KEY, subject TEXT, predicate TEXT, object TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

def add_fact(sub, pred, obj):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id FROM knowledge_graph WHERE subject=? AND predicate=? AND object=?", (sub, pred, obj))
        if c.fetchone(): return "FACT_EXISTS"
        
        c.execute("INSERT INTO knowledge_graph (subject, predicate, object) VALUES (?, ?, ?)", (sub, pred, obj))
        conn.commit()
        conn.close()
        return "FACT_MEMORIZED"
    except Exception as e: return str(e)

def query_graph(query):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        q = f"%{query}%"
        c.execute("SELECT subject, predicate, object FROM knowledge_graph WHERE subject LIKE ? OR object LIKE ?", (q, q))
        rows = c.fetchall()
        conn.close()
        if not rows: return "NO_DATA_FOUND"
        return "\n".join([f"{r[0]} -> {r[1]} -> {r[2]}" for r in rows])
    except Exception as e: return str(e)

def auto_extract_and_learn(text: str) -> list:
    """Uses LLM to extract semantic triplets (Subject, Predicate, Object) and stores them."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("JESTER_PRIMARY_LLM", "gemini-3.1-pro")
    
    prompt = (
        "Extract semantic knowledge triplets from the following text in JSON array format: "
        "[{\"subject\": \"...\", \"predicate\": \"...\", \"object\": \"...\"}]. "
        "Return ONLY valid JSON array with no extra markdown.\n\n"
        f"Text: {text}"
    )
    
    triplets = []
    try:
        if gemini_key:
            client = genai.Client(api_key=gemini_key)
            res = client.models.generate_content(model=model, contents=prompt)
            clean = res.text.strip().replace("```json", "").replace("```", "").strip()
            triplets = json.loads(clean)
        elif openai_key:
            client = OpenAI(api_key=openai_key)
            res = client.chat.completions.create(
                model=os.getenv("JESTER_OPENAI_MODEL", "gpt-4o"),
                messages=[{"role": "user", "content": prompt}]
            )
            clean = res.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
            triplets = json.loads(clean)
    except Exception as e:
        logger.warning(f"[learning_core] Extraction failed: {e}")
        return []
        
    saved = []
    if isinstance(triplets, list):
        for item in triplets:
            if isinstance(item, dict) and "subject" in item and "predicate" in item and "object" in item:
                status = add_fact(item["subject"], item["predicate"], item["object"])
                saved.append(f"{item['subject']} -> {item['predicate']} -> {item['object']} ({status})")
    return saved

init_db()
