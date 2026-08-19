import sqlite3
import os
import datetime
import json
DB_FILE = 'jester_brain.db'
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS memory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  content TEXT,
                  importance INTEGER DEFAULT 1,
                  metadata TEXT DEFAULT '{}',
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''') 
    c.execute("PRAGMA table_info(memory)")
    columns = [col[1] for col in c.fetchall()]
    if 'importance' not in columns:
        c.execute("ALTER TABLE memory ADD COLUMN importance INTEGER DEFAULT 1")
    if 'metadata' not in columns:
        c.execute("ALTER TABLE memory ADD COLUMN metadata TEXT DEFAULT '{}'")
    conn.commit()
    conn.close()
def save(content, importance=1, metadata=None):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        meta_json = json.dumps(metadata) if metadata else '{}'      
        c.execute('INSERT INTO memory (content, importance, metadata) VALUES (?, ?, ?)', (content, importance, meta_json))
        conn.commit()
        conn.close()
        return 'MEMORY_ENCODED'
    except Exception as e:
        return f'MEMORY_ERROR: {str(e)}'
def retrieve(query, limit=10):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT content, timestamp, importance, metadata FROM memory WHERE content LIKE ? ORDER BY importance DESC, id DESC LIMIT ?', (f'%{query}%', limit))
        rows = c.fetchall()
        conn.close()
        if not rows:
            return 'NO_MATCHING_MEMORIES'
        return '\n'.join([f'[{r[1]}] [LVL:{r[2]}] {r[0]} (META: {r[3]})' for r in rows])
    except Exception as e:
        return f'RECALL_ERROR: {str(e)}'
def retrieve_recent(limit=10):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT content, timestamp, importance, metadata FROM memory ORDER BY id DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        return '\n'.join([f'[{r[1]}] {r[0]}' for r in rows])        
    except Exception as e:
        return f'RECALL_ERROR: {str(e)}'
def consolidate():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM memory WHERE importance < 3 AND id NOT IN (SELECT id FROM memory ORDER BY id DESC LIMIT 500)')
        conn.commit()
        conn.close()
        return 'CONSOLIDATION_COMPLETE'
    except Exception as e:
        return f'CONSOLIDATION_ERROR: {str(e)}'
init_db()
