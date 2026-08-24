import importlib.util
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.join(BASE_DIR, "plugins")

if not os.path.exists(PLUGIN_DIR):
    os.makedirs(PLUGIN_DIR)
    # Create __init__.py
    with open(os.path.join(PLUGIN_DIR, "__init__.py"), "w") as f: f.write("")

def create_tool(name, code):
    try:
        name = "".join(x for x in name if x.isalnum() or x == "_")
        filepath = os.path.join(PLUGIN_DIR, f"{name}.py")
        
        # Enforce signature
        if "async def" not in code:
            return "ERROR: Code must have 'async def run(f,t,a,l,c,r):'"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
            
        return f"GENESIS_COMPLETE: Tool '{name}' created. Restarting systems to integrate..."
    except Exception as e: return str(e)

def load_plugins(llm):
    loaded = []
    if not os.path.exists(PLUGIN_DIR): return []
    
    sys.path.append(PLUGIN_DIR)
    
    for f in os.listdir(PLUGIN_DIR):
        if f.endswith(".py") and not f.startswith("__"):
            mod_name = f[:-3]
            try:
                spec = importlib.util.spec_from_file_location(mod_name, os.path.join(PLUGIN_DIR, f))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                
                # Expecting 'run' function
                func = getattr(mod, "run", None)
                if func:
                    llm.register_function(mod_name, func)
                    loaded.append(mod_name)
            except Exception as e:
                print(f"PLUGIN_FAIL: {mod_name} - {e}")
    return loaded
