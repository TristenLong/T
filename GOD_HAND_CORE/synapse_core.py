import os
import shutil
import datetime
import sqlite3
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(os.path.dirname(BASE_DIR), "backups")

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def create_backup():
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        db_src = os.path.join(BASE_DIR, "jester_brain.db")
        if os.path.exists(db_src):
            shutil.copy2(db_src, os.path.join(BACKUP_DIR, f"brain_{timestamp}.db"))
            
            conn = sqlite3.connect(db_src)
            c = conn.cursor()
            c.execute("SELECT subject, predicate, object FROM knowledge_graph")
            rows = c.fetchall()
            conn.close()
            
            data = [{"s": r[0], "p": r[1], "o": r[2]} for r in rows]
            with open(os.path.join(BACKUP_DIR, f"knowledge_{timestamp}.json"), "w") as f:
                json.dump(data, f, indent=2)
                
        return "SYNC_OK"
    except Exception as e: return str(e)

def prune_backups():
    try:
        files = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)], key=os.path.getmtime)
        while len(files) > 10: os.remove(files.pop(0))
    except: pass
