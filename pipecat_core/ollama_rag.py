import os
import requests
import json
import sqlite3
import numpy as np
from loguru import logger

OLLAMA_BASE_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
GEN_MODEL = "llama3.2"
DB_PATH = os.path.join(os.path.dirname(__file__), "ollama_knowledge.db")

class OllamaRAG:
    def __init__(self):
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            content TEXT,
            embedding BLOB,
            metadata TEXT
        )""")
        conn.commit()
        conn.close()

    def get_embedding(self, text):
        url = f"{OLLAMA_BASE_URL}/api/embeddings"
        payload = {"model": EMBED_MODEL, "prompt": text}
        try:
            response = requests.post(url, json=payload)
            return response.json()["embedding"]
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def ingest_file(self, file_path):
        if not os.path.exists(file_path): return "File not found."
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Simple chunking by paragraph/lines for now
            chunks = [content[i:i+1000] for i in range(0, len(content), 800)]
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            for chunk in chunks:
                emb = self.get_embedding(chunk)
                if emb:
                    emb_blob = np.array(emb, dtype=np.float32).tobytes()
                    c.execute("INSERT INTO knowledge (path, content, embedding) VALUES (?, ?, ?)",
                              (file_path, chunk, emb_blob))
            conn.commit()
            conn.close()
            return f"Ingested {len(chunks)} chunks from {file_path}"
        except Exception as e:
            return str(e)

    def search(self, query, limit=5):
        q_emb = self.get_embedding(query)
        if not q_emb: return []
        
        q_vec = np.array(q_emb, dtype=np.float32)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT content, embedding, path FROM knowledge")
        rows = c.fetchall()
        conn.close()
        
        results = []
        for content, emb_blob, path in rows:
            if not emb_blob: continue
            emb_vec = np.frombuffer(emb_blob, dtype=np.float32)
            if len(emb_vec) != len(q_vec): continue
            score = np.dot(q_vec, emb_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(emb_vec))
            results.append({"content": content, "score": float(score), "path": path})
            
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def query(self, prompt):
        context_items = self.search(prompt)
        if not context_items:
            return "No relevant context found in local knowledge base."
            
        context_text = "\n---\n".join([item["content"] for item in context_items])
        
        full_prompt = f"Context:\n{context_text}\n\nQuestion: {prompt}\n\nAnswer based on context provided above. If the context doesn't contain the answer, say you don't know from local data."
        
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {"model": GEN_MODEL, "prompt": full_prompt, "stream": False}
        
        try:
            response = requests.post(url, json=payload)
            return response.json()["response"]
        except Exception as e:
            return f"Query error: {str(e)}"

rag = OllamaRAG()

if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "ingest" and len(sys.argv) > 2:
            print(rag.ingest_file(sys.argv[2]))
        elif sys.argv[1] == "query" and len(sys.argv) > 2:
            print(rag.query(sys.argv[2]))
