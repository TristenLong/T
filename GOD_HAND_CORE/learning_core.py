import sqlite3
import os

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
        # Check duplicate
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
        # Simple wildcard search
        q = f"%{query}%"
        c.execute("SELECT subject, predicate, object FROM knowledge_graph WHERE subject LIKE ? OR object LIKE ?", (q, q))
        rows = c.fetchall()
        conn.close()
        if not rows: return "NO_DATA_FOUND"
        return "\n".join([f"{r[0]} -> {r[1]} -> {r[2]}" for r in rows])
    except Exception as e: return str(e)

init_db()
