import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "jester_brain.db")

class OfflineBrain:
    def __init__(self):
        self.name = "JESTER [OFFLINE]"
        self.is_ready = True
        
    def initialize(self):
        self.is_ready = True
        return True

    def query_db(self, query):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            # Search Knowledge Graph
            c.execute("CREATE TABLE IF NOT EXISTS knowledge_graph (subject TEXT, predicate TEXT, object TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()
            
            c.execute("SELECT subject, predicate, object FROM knowledge_graph WHERE subject LIKE ? OR object LIKE ?", (f"%{query}%", f"%{query}%"))
            facts = c.fetchall()
            
            c.execute("SELECT content FROM history WHERE content LIKE ? ORDER BY id DESC LIMIT 3", (f"%{query}%",))
            logs = c.fetchall()
            conn.close()
            return facts, logs
        except Exception:
            return [], []

    def solve(self, problem, tools=None):
        """Solves basic tasks offline using local tools and heuristics."""
        tools = tools or {}
        p_lower = (problem or "").lower()
        
        if "time" in p_lower or "clock" in p_lower:
            import datetime
            return f"Current local time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
        if "dir" in p_lower or "list files" in p_lower:
            if 'list_dir' in tools:
                return f"Directory contents: {tools['list_dir']('.')}"
            return str(os.listdir('.'))
            
        facts, logs = self.query_db(problem)
        if facts or logs:
            return self.chat(problem)
            
        return f"[OFFLINE REASONING] Processed objective: '{problem}'. Local heuristics applied. Matrix fallback active."

    def chat(self, message):
        msg = message.lower()
        if "who are you" in msg:
            return "I am JESTER (Offline Mode). Systems are running locally."
        if "status" in msg:
            return "Offline Mode Active. Neural Uplink Severed."
        
        facts, logs = self.query_db(msg)
        
        if not facts and not logs:
            return f"CONNECTION_LOST: No local data found on '{message}'."
            
        resp = "OFFLINE_ARCHIVE_RETRIEVAL:\n"
        if facts:
            resp += "KNOWLEDGE_GRAPH:\n" + "\n".join([f"> {f[0]} {f[1]} {f[2]}" for f in facts]) + "\n"
        if logs:
            resp += "RECENT_LOGS:\n" + "\n".join([f"> {l[0]}" for l in logs])
            
        return resp

brain = OfflineBrain()
