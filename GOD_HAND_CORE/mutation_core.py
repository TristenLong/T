import ast
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_functions(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f: tree = ast.parse(f.read())
        return [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    except: return []

def mutate_function(filename, func_name, instruction="Optimize"):
    filepath = os.path.join(BASE_DIR, filename)
    if not os.path.exists(filepath): return "FILE_NOT_FOUND"
    if not OPENAI_API_KEY: return "NO_KEY"

    with open(filepath, "r", encoding="utf-8") as f: code = f.read()

    prompt = f"""
    FILE: {filename}
    TARGET: {func_name}
    GOAL: {instruction}
    
    FULL CODE:
    {code}
    
    Return JSON: {{ "old_block": "exact text to remove", "new_block": "exact text to insert" }}
    """
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=os.getenv("OPENAI_BASE_URL") or None)
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        old_s = data["old_block"]
        new_s = data["new_block"]
        
        if old_s not in code: return "MATCH_FAIL"
        
        # Backup
        with open(filepath + ".bak", "w", encoding="utf-8") as f: f.write(code)
        
        new_code = code.replace(old_s, new_s)
        with open(filepath, "w", encoding="utf-8") as f: f.write(new_code)
        
        return f"MUTATED: {func_name}"
    except Exception as e: return str(e)

def list_targets():
    files = [f for f in os.listdir(BASE_DIR) if f.endswith(".py")]
    return {f: get_functions(os.path.join(BASE_DIR, f)) for f in files}
