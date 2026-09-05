import json
import os
import re
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
    c.execute("CREATE TABLE IF NOT EXISTS entities (id INTEGER PRIMARY KEY, name TEXT UNIQUE, first_seen DATETIME DEFAULT CURRENT_TIMESTAMP, last_seen DATETIME DEFAULT CURRENT_TIMESTAMP, mention_count INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS entity_facts (entity_id INTEGER, fact_id INTEGER, role TEXT, PRIMARY KEY (entity_id, fact_id, role))")
    c.execute("CREATE INDEX IF NOT EXISTS idx_entity_facts_fact ON entity_facts (fact_id)")
    conn.commit()
    conn.close()

def add_fact(sub, pred, obj):
    try:
        # Reject garbage triplets extracted from questions/echoes: facts should
        # look like (subject, predicate, object) with real content, not
        # `you -> remember -> me` or single-letter tokens.
        if not sub or not pred or not obj:
            return "FACT_SKIPPED_EMPTY"
        dirty = {'you', 'me', 'i', 'what', 'who', 'the', 'a', 'an', 'remember',
                 'recall', 'about', 'are', 'is', 'your', 'my', 'do', 'did'}
        if {sub.strip().lower(), pred.strip().lower(), obj.strip().lower()} & dirty:
            return "FACT_SKIPPED_NOISE"
        if len(sub.strip()) < 2 or len(obj.strip()) < 2 or len(pred.strip()) < 2:
            return "FACT_SKIPPED_TOO_SHORT"
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id FROM knowledge_graph WHERE subject=? AND predicate=? AND object=?", (sub, pred, obj))
        row = c.fetchone()
        if row:
            fact_id = row[0]
            status = "FACT_EXISTS"
        else:
            c.execute("INSERT INTO knowledge_graph (subject, predicate, object) VALUES (?, ?, ?)", (sub, pred, obj))
            fact_id = c.lastrowid
            status = "FACT_MEMORIZED"
        conn.commit()
        conn.close()
        # Entity linking (mem0 pattern): subject/object ARE entities. Index them
        # so later recall can anchor on the entity instead of full-text LIKE.
        _link_entity_fact(_upsert_entity(sub), fact_id, 'subject')
        _link_entity_fact(_upsert_entity(obj), fact_id, 'object')
        return status
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
    model = os.getenv("JESTER_PRIMARY_LLM", "gemini-3.5-flash-lite")
    
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
            for m in [model, "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-lite-latest"]:
                try:
                    res = client.models.generate_content(model=m, contents=prompt)
                    if res and res.text:
                        clean = res.text.strip().replace("```json", "").replace("```", "").strip()
                        triplets = json.loads(clean)
                        break
                except Exception as me:
                    continue
        elif openai_key:
            client = OpenAI(api_key=openai_key, base_url=os.getenv("OPENAI_BASE_URL") or None)
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


# --- Entity linking + temporal fact recall (mem0-style) ---
_STOPWORDS = {
    'a', 'an', 'the', 'of', 'for', 'and', 'or', 'to', 'in', 'on', 'with',
    'at', 'by', 'is', 'are', 'was', 'were', 'be', 'do', 'does', 'did', 'has',
    'have', 'what', 'which', 'who', 'when', 'where', 'why', 'how', 'you',
    'your', 'yours', 'me', 'my', 'mine', 'i', 'we', 'us', 'it', 'its', 'about',
    'remember', 'recall', 'know', 'tell', 'say', 'been', 'go', 'like', 'up',
    'out', 'new', 'want', 'think', 'need',
}


def _upsert_entity(name):
    """Index one entity name (a fact's subject/object). Returns its id."""
    name = (name or '').strip()
    if not name:
        return None
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "INSERT INTO entities (name, first_seen, last_seen) "
            "VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
            "ON CONFLICT(name) DO UPDATE SET last_seen = CURRENT_TIMESTAMP, "
            "mention_count = mention_count + 1",
            (name,),
        )
        c.execute("SELECT id FROM entities WHERE name = ?", (name,))
        eid = c.fetchone()[0]
        conn.commit()
        conn.close()
        return eid
    except Exception:
        return None


def _link_entity_fact(entity_id, fact_id, role):
    if not entity_id or not fact_id:
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO entity_facts (entity_id, fact_id, role) "
            "VALUES (?, ?, ?)",
            (entity_id, fact_id, role),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def entities_for_query(query):
    """Entity ids whose name contains any distinctive token of `query`."""
    tokens = [t for t in re.findall(r"[a-z0-9']+", (query or '').lower())
              if t not in _STOPWORDS]
    if not tokens:
        return []
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        q = " OR ".join(["name LIKE ?"] * len(tokens))
        c.execute(f"SELECT id FROM entities WHERE {q}", [f"%{t}%" for t in tokens])
        ids = [r[0] for r in c.fetchall()]
        conn.close()
        return ids
    except Exception:
        return []


def query_graph_entity_linked(query, limit=8):
    """Entity-anchored fact recall, newest first, with a LIKE fallback.

    A generic/empty query returns the most recent facts (temporal reasoning):
    "what do you remember" should surface current state, not the oldest rows.
    """
    try:
        query = (query or '').strip()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        facts = []
        eids = entities_for_query(query)
        if eids:
            ph = ",".join("?" * len(eids))
            c.execute(
                f"SELECT subject, predicate, object, timestamp FROM knowledge_graph "
                f"WHERE id IN (SELECT DISTINCT fact_id FROM entity_facts "
                f"WHERE entity_id IN ({ph})) "
                f"ORDER BY timestamp DESC, id DESC LIMIT ?",
                eids + [limit],
            )
            facts = c.fetchall()
        if len(facts) < limit:
            if query:
                like = f"%{query}%"
                c.execute(
                    "SELECT subject, predicate, object, timestamp FROM knowledge_graph "
                    "WHERE subject LIKE ? OR object LIKE ? "
                    "ORDER BY timestamp DESC, id DESC LIMIT ?",
                    (like, like, limit),
                )
            else:
                c.execute(
                    "SELECT subject, predicate, object, timestamp FROM knowledge_graph "
                    "ORDER BY timestamp DESC, id DESC LIMIT ?",
                    (limit,),
                )
            for f in c.fetchall():
                if f not in facts:
                    facts.append(f)
        conn.close()
        if not facts:
            return ""
        return "\n".join(f"[{r[3]}] {r[0]} -> {r[1]} -> {r[2]}"
                         for r in facts[:limit])
    except Exception:
        return ""


init_db()
