import os

import vector_core

IGNORE_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", "venv", "env", "AppData"}
EXTENSIONS = {".txt", ".md", ".py", ".js", ".json", ".bat", ".sh", ".html", ".css", ".log", ".csv", ".yml"}

def chunk_text(text, size=1000, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

def ingest_directory(path):
    if not os.path.exists(path): return "PATH_NOT_FOUND"
    
    total_files = 0
    total_chunks = 0
    errors = 0
    
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            if os.path.splitext(file)[1].lower() in EXTENSIONS:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    if not content.strip(): continue
                    if len(content) > 100000: continue # Skip huge files
                    
                    chunks = chunk_text(content)
                    for chunk in chunks:
                        # Contextual Header
                        vec_data = f"SOURCE: {filepath}\nCONTENT:\n{chunk}"
                        vector_core.save_semantic(vec_data)
                        total_chunks += 1
                    
                    total_files += 1
                except: errors += 1
                
    return f"ARCHIVE_UPDATED: Files: {total_files} | Vectors: {total_chunks} | Errors: {errors}"
