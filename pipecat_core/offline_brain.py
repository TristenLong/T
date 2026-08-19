import sqlite3
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "jester_brain.db")

class OfflineBrain:
    def __init__(self):
        self.name = "JESTER [OFFLINE]"
        
    def query_db(self, query):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            # Search Knowledge Graph
            c.execute("SELECT subject, predicate, object FROM knowledge_graph WHERE subject LIKE ? OR object LIKE ?", (f"%{query}%", f"%{query}%"))
            facts = c.fetchall()
            
            # Search Logs
            c.execute("SELECT content FROM history WHERE content LIKE ? ORDER BY id DESC LIMIT 3", (f"%{query}%",))
            logs = c.fetchall()
            conn.close()
            return facts, logs
        except: return [], []

    def chat(self, message):
        msg = message.lower()
        if "who are you" in msg: return "I am JESTER (Offline Mode). Systems are running locally."
        if "status" in msg: return "Offline Mode Active. Neural Uplink Severed."
        
        facts, logs = self.query_db(msg)
        
        if not facts and not logs:
            return "CONNECTION_LOST: No local data found on this topic."
            
        resp = "OFFLINE_ARCHIVE_RETRIEVAL:\n"
        if facts:
            resp += "KNOWLEDGE_GRAPH:\n" + "\n".join([f"> {f[0]} {f[1]} {f[2]}" for f in facts]) + "\n"
        if logs:
            resp += "RECENT_LOGS:\n" + "\n".join([f"> {l[0]}" for l in logs])
            
        return resp

brain = OfflineBrain()
