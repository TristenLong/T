import asyncio
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse

from pydantic import BaseModel, Field

# Add GOD_HAND_CORE itself
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    import pyautogui

    import browser_core
    import coder_core
    import computer_use
    import memory_core
    import offline_brain
    import research_core
    import rss_core
    import swarm_cache
    import system_core
    import vision_core
    from sandbox_core import sandbox_core

    pyautogui.FAILSAFE = False

except ImportError as e:
    print(f"Error importing core modules: {e}")

def execute_computer_use(action: str, params: dict | None = None) -> str:
    """Direct OS GUI control, keystrokes & mouse navigation."""
    try:
        return computer_use.execute_computer_action(action, params or {})
    except Exception as e:
        return f"Error: {e}"

def dispatch_coder_swarm(prompt: str, path: str = "", execute: bool = False) -> str:
    """Dispatch a coding task to the Architect CoderCore: builds new code, or reads an existing file (path) and writes the fixed version back. execute=True also runs it in the sandbox."""
    try:
        coder = coder_core.CoderCore(memory_core)
        return asyncio.run(coder.run_coding_task(prompt, path=path, execute=execute))
    except Exception as e:
        return f"Error: {e}"

def dispatch_browser_swarm(task: str) -> str:
    """Dispatch web navigation task to Navigator BrowserCore sub-agent."""
    try:
        browser = browser_core.BrowserCore(memory_core)
        return asyncio.run(browser.navigate_and_interact(task))
    except Exception as e:
        return f"Error: {e}"

def conduct_deep_research(query: str) -> str:
    """Multi-query web crawling and research aggregation."""
    try:
        return research_core.deep_research(query)
    except Exception as e:
        return f"Error: {e}"

def fetch_rss(query: str, limit: int = 5) -> str:
    """Fetch the latest posts from a subreddit ('r/singularity') or any RSS/Atom feed URL. No API credentials required."""
    try:
        return rss_core.fetch_rss(query, limit)
    except Exception as e:
        return f"Error: {e}"

# --- Swarm cache (shared cross-process memory, wired from task_1788652369) ---
# Persistent mmap file lives in the GOD_HAND_CORE data dir so it survives restarts.
_SWARM_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.swarm_cache.mmap')
_swarm_cache = None


def _get_swarm_cache():
    global _swarm_cache
    if _swarm_cache is None:
        try:
            _swarm_cache = swarm_cache.BoundedMmapCache(
                capacity_bytes=1024 * 1024, cache_file=_SWARM_CACHE_PATH)
        except Exception as e:
            return f"Error initializing swarm cache: {e}"
    return _swarm_cache


def swarm_cache_put(key: str, value: str) -> str:
    """Store a string value in the cross-process swarm cache under `key`."""
    try:
        cache = _get_swarm_cache()
        if isinstance(cache, str):
            return cache
        ok = cache.put(key, value.encode('utf-8'))
        return "STORED" if ok else "CACHE_FULL"
    except Exception as e:
        return f"Error: {e}"


def swarm_cache_get(key: str) -> str:
    """Retrieve a string value from the cross-process swarm cache by `key`."""
    try:
        cache = _get_swarm_cache()
        if isinstance(cache, str):
            return cache
        val = cache.get(key)
        return val.decode('utf-8') if val is not None else f"MISS: {key}"
    except Exception as e:
        return f"Error: {e}"


def swarm_cache_stats() -> str:
    """Report swarm cache occupancy (entries, bytes used, capacity)."""
    try:
        cache = _get_swarm_cache()
        if isinstance(cache, str):
            return cache
        s = cache.stats()
        return (f"entries={s['entries']} used_bytes={s['used_bytes']} "
                f"capacity_bytes={s['capacity_bytes']} file={s['file']}")
    except Exception as e:
        return f"Error: {e}"

def optimize_system(target: str = "mining") -> str:
    """Optimize system performance."""
    try:
        return system_core.optimize(target)
    except Exception as e:
        return f"Error: {e}"

def switch_to_offline(message: str = "status") -> str:
    """Switch to offline mode and query local brain."""
    try:
        return offline_brain.brain.chat(message)
    except Exception as e:
        return f"Error: {e}"

def system_control(action: str, value: str = "") -> str:
    """Control IO. Actions: type, press, minimize_all, open_start."""
    try:
        if action == 'type': pyautogui.write(value)
        elif action == 'press': pyautogui.press(value)
        elif action == 'minimize_all': pyautogui.hotkey('win', 'd')
        elif action == 'open_start': pyautogui.press('win')
        return "DONE"
    except Exception as e:
        return f"Error: {e}"

def analyze_screen(prompt: str = "Describe the current screen") -> str:
    """Analyze the current screen semantically."""
    try:
        res = vision_core.vision_core.analyze_screen_semantic(prompt)
        return str(res)
    except Exception as e:
        return f"Error: {e}"

def execute_python_sandbox(code: str) -> str:
    """Execute Python code in a safe Docker sandbox container."""
    try:
        res = sandbox_core.execute_python_code(code)
        if isinstance(res, dict):
            return str(res.get('output') or res.get('message') or res)
        return str(res)
    except Exception as e:
        return f"Sandbox Error: {e}"

def dispatch_mcp_swarm(task: str) -> str:
    """Spawns an autonomous background MCP agent to complete a task using Model Context Protocol tools."""
    try:
        import sub_agent_core
        return sub_agent_core.spawn_agent(task, agent_type="mcp_agent")
    except Exception as e:
        return f"Error: {e}"

def start_visual_autopilot(objective: str) -> str:
    """Starts the Visual Auto-Pilot to physically control the computer using semantic screen analysis to complete an objective."""
    try:
        import computer_use
        return computer_use.auto_pilot(objective)
    except Exception as e:
        return f"Error: {e}"

def run_rovo_dev(prompt: str) -> str:
    """Dispatches the Atlassian Rovo Dev CLI autonomous agent to execute complex coding or system upgrade tasks."""
    try:
        # Assuming acli.exe is in the project root relative to GOD_HAND_CORE
        acli_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'acli.exe')
        res = subprocess.run([acli_path, 'rovodev', 'run', prompt, '--yolo'], capture_output=True, text=True)
        return f"Rovo Dev Output:\n{res.stdout}\n{res.stderr}"
    except Exception as e:
        return f"Rovo Dev Error: {e}"

def open_app_or_url(target: str) -> str:
    """Open a URL in the default browser, or launch an installed app by name, on the user's machine."""
    import re
    import webbrowser
    t = (target or "").strip()
    if not t:
        return "Error: no target specified"
    # Bare app-ish name (no dot, no scheme) -> try launching via OS
    if not re.match(r"^[a-zA-Z0-9]+://", t) and "." not in t and " " not in t:
        try:
            subprocess.Popen(f'start "" "{t}"', shell=True)
            return f"[SUCCESS] Launched {t}"
        except Exception as e:
            return f"Error launching {t}: {e}"
    url = t if re.match(r"^[a-zA-Z0-9]+://", t) else f"https://{t}"
    try:
        webbrowser.open(url)
        return f"[SUCCESS] Opened {url} in default browser"
    except Exception as e:
        return f"Error opening {url}: {e}"

def search_web(query: str) -> str:
    """Perform a live web search and return concise results for a query."""
    try:
        browser = browser_core.BrowserCore(memory_core)
        return str(asyncio.run(browser.search_web(query)))
    except Exception as e:
        return f"Search Error: {e}"

web_search = search_web


def diagnostics_report() -> str:
    """Run the full system diagnostic suite and return the report (status, keys, internet, stress test)."""
    try:
        import diagnostics_suite
        lines = [
            f"Internet: {'OK' if diagnostics_suite.check_internet() else 'DOWN'}",
            f"OpenAIKey: {diagnostics_suite.check_api_key('OPENAI_API_KEY')}",
            f"PuterBackendKey: {diagnostics_suite.check_api_key('PUTER_AUTH_TOKEN')}",
            diagnostics_suite.get_system_report(),
        ]
        try:
            lines.append("Stress: " + diagnostics_suite.run_stress_test())
        except Exception:
            pass
        return "\n".join(lines)
    except Exception as e:
        return f"Diagnostics Error: {e}"

def ocr_screen(prompt: str = "Extract all visible text") -> str:
    """OCR the current screen and return the extracted text."""
    try:
        text = vision_core.vision_core.extract_text()
        return str(text)
    except Exception as e:
        return f"Error: {e}"

def capture_webcam_analysis(prompt: str = "Describe what the webcam sees in detail.") -> str:
    """Capture the webcam and analyze the frame semantically."""
    try:
        res = vision_core.vision_core.analyze_webcam(prompt)
        return str(res)
    except Exception as e:
        return f"Error: {e}"

def query_knowledge_graph(query: str = "") -> str:
    """Query the local semantic knowledge graph (subject->predicate->object triplets) for remembered facts."""
    try:
        import learning_core
        res = learning_core.query_graph(query)
        if res == "NO_DATA_FOUND":
            return "NO_FACTS_STORED"
        return res
    except Exception as e:
        return f"Error: {e}"

def list_apps(filter: str = "") -> str:
    """List installed applications on this computer. Optional `filter` narrows by name (e.g. 'chrome', 'code', 'spotify')."""
    import re
    names = set()
    try:
        # Start-menu .lnk files (user + all users) are the fastest reliable source.
        roots = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
        ]
        for root in roots:
            if not os.path.isdir(root):
                continue
            for dirpath, _, filenames in os.walk(root):
                for fn in filenames:
                    if fn.lower().endswith(".lnk"):
                        names.add(os.path.splitext(fn)[0])
    except Exception:
        pass
    try:
        # Registry uninstall keys as a backup source of app names.
        import winreg
        for hive, key in [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]:
            try:
                with winreg.OpenKey(hive, key) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        try:
                            with winreg.OpenKey(k, winreg.EnumKey(k, i)) as sub:
                                name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                if name:
                                    names.add(str(name).strip())
                        except OSError:
                            continue
            except OSError:
                continue
    except Exception:
        pass

    names = sorted(n for n in names if n)
    f = (filter or "").strip().lower()
    if f:
        names = [n for n in names if f in n.lower()]
    names = names[:60]
    if not names:
        return "No applications matched."
    listing = "\n".join(f"- {n}" for n in names)
    return f"Installed apps ({len(names)} shown):\n{listing}"

def apilayer_request(endpoint: str, params: dict | None = None) -> str:
    """Make a request to an APILayer API using the configured APILAYER_API_KEY.
    `endpoint` should be the path after api.apilayer.com (e.g. 'bad_words', 'exchangerates_data/latest').
    `params` is a dictionary of query parameters.
    """
    import os
    import urllib.request
    import urllib.error
    import urllib.parse
    import json
    
    api_key = os.environ.get('APILAYER_API_KEY')
    if not api_key:
        return "Error: APILAYER_API_KEY is not set in environment."
        
    endpoint = endpoint.lstrip('/')
    url = f"https://api.apilayer.com/{endpoint}"
    
    if params:
        query_string = urllib.parse.urlencode(params)
        url = f"{url}?{query_string}"
        
    req = urllib.request.Request(url)
    req.add_header("apikey", api_key)
    
    try:
        with urllib.request.urlopen(req) as response:
            result = response.read()
            return result.decode('utf-8')
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        return f"APILayer HTTP Error {e.code}: {err_msg}"
    except Exception as e:
        return f"APILayer Error: {e}"

# --- Named MCP server registry (Jarvis/Miko management surface) ---
# MCP servers in bot.py were spawned ad-hoc per request from `command`/`args`
# passed by the caller. Registering servers here gives the model (and the UI) a
# stable name to call into, and keeps the precise spawn argv out of the prompt.
_MCP_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_servers.json')


def _load_mcp_servers() -> list:
    try:
        with open(_MCP_REGISTRY_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def register_mcp_server(name: str, command: str, args: list) -> str:
    servers = _load_mcp_servers()
    servers = [s for s in servers if s.get('name') != name]
    servers.append({'name': name, 'command': command, 'args': list(args or [])})
    with open(_MCP_REGISTRY_FILE, 'w', encoding='utf-8') as fh:
        json.dump(servers, fh, indent=2)
    return f"MCP server '{name}' registered."


def list_mcp_servers() -> str:
    servers = _load_mcp_servers()
    if not servers:
        return "No MCP servers registered."
    return "\n".join(f"- {s.get('name')}: {s.get('command')} {' '.join(s.get('args', []))}".rstrip() for s in servers)


# --- Persistent todo working-memory (MS agent-framework TodoProvider) ---
# Lets the model track multi-step work ("mark step done" after each tool result)
# without depending on the chat transcript -- survives across turns and sessions.
_TODOS_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jester_V73_OMNIPRESENCE.db')


def _todos_conn():
    import sqlite3
    conn = sqlite3.connect(_TODOS_DB)
    conn.cursor().execute(
        "CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "text TEXT, done INTEGER DEFAULT 0, created DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    return conn


def todo_add(text: str) -> str:
    """Add a task to the persistent todo list used during multi-step work."""
    import sqlite3
    text = (text or '').strip()
    if not text:
        return 'Error: empty todo'
    try:
        conn = _todos_conn()
        c = conn.cursor()
        c.execute("INSERT INTO todos (text) VALUES (?)", (text,))
        tid = c.lastrowid
        conn.commit()
        conn.close()
        return f"TODO #{tid} added: {text}"
    except Exception as e:
        return f'Error: {e}'


def todo_list(done: bool = False) -> str:
    """List open todos. Pass done=True to show completed ones (or False for open only)."""
    import sqlite3
    try:
        conn = _todos_conn()
        c = conn.cursor()
        c.execute("SELECT id, text FROM todos WHERE done=? ORDER BY id", (1 if done else 0,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            return f"No {'completed' if done else 'open'} todos."
        return "\n".join(f"{'[x]' if done else '[ ]'} #{r[0]}: {r[1]}" for r in rows)
    except Exception as e:
        return f'Error: {e}'


def todo_mark(id: int, done: bool = True) -> str:
    """Mark a todo by its id as done (or undone with done=False)."""
    import sqlite3
    try:
        conn = _todos_conn()
        c = conn.cursor()
        c.execute("UPDATE todos SET done=? WHERE id=?", (1 if done else 0, int(id)))
        conn.commit()
        conn.close()
        return f"TODO #{id} {'DONE' if done else 'REOPENED'}."
    except Exception as e:
        return f'Error: {e}'


# Tools whose real result IS the answer (pi-agent-go Terminate): after a pure
# round of these, the agent loop summarizes once instead of running another
# tool-calling turn.
TERMINAL_TOOLS = frozenset({
    'open_app_or_url', 'list_apps', 'list_mcp_servers', 'query_knowledge_graph',
    'diagnostics_report', 'mcp_execute', 'plan_and_execute',
})

# The ONLY tools a generated CodeAct-style plan may call. Everything else
# (keystrokes, mouse, screens, sandbox, coder subagents) is off-limits to the
# planner: the plan runs with the same safety posture as the tool loop.
_PLAN_EXEC_WHITELIST = frozenset({
    'open_app_or_url', 'search_web', 'fetch_rss', 'list_apps',
    'query_knowledge_graph', 'diagnostics_report', 'list_mcp_servers',
    'conduct_deep_research', 'todo_add', 'todo_list', 'todo_mark',
    'swarm_cache_put', 'swarm_cache_get', 'swarm_cache_stats',
})


def _call_tool_arg_tolerant(fn, args):
    """Run one plan step with the same arg tolerance as the agent loop."""
    import inspect
    try:
        sig = inspect.signature(fn)
        params = set(sig.parameters)
        val_args = {k: v for k, v in (args or {}).items() if k in params}
        missing = [
            p for p, prm in sig.parameters.items()
            if prm.default is inspect.Parameter.empty and p not in val_args
        ]
        if missing:
            for p in missing:
                val_args[p] = ''
        return str(fn(**val_args) if val_args else fn())
    except TypeError as te:
        return f'Error (bad arguments): {te}'
    except Exception as ex:
        return f'Error: {ex}'


def plan_and_execute(task: str) -> str:
    """Break a multi-step task into one plan and run every step in a single pass (CodeAct). Steps may only use the safe plan whitelist (web, apps, graphs, diagnostics, MCP servers); anything else is refused."""
    task = (task or '').strip()
    if not task:
        return 'Error: no task specified'
    try:
        import json as _json
        import llm_router
        allowed = ", ".join(sorted(_PLAN_EXEC_WHITELIST))
        prompt = (
            'You are a task planner. Break the user request into at most 5 tool '
            'steps. Return ONLY a JSON object with a steps array, each step like '
            '{"steps": [{"tool": "<name>", "args": {"<param>": value}}]}. '
            f'Allowed tools: {allowed}. Never include tools outside that list, '
            'never nest plans, keep args to scalar values. No code fences.\n\n'
            'Task: ' + task
        )
        plan_text, _model = llm_router.generate_completion_with_model(
            [{'role': 'user', 'content': prompt}], require_json=True)
        clean = plan_text.strip().replace('```json', '').replace('```', '').strip()
        plan = _json.loads(clean)
        steps = plan.get('steps') or []
        if not isinstance(steps, list) or not steps or len(steps) > 5:
            return 'Error: planner returned an unusable plan.'
        lines = []
        for i, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                continue
            name = (step.get('tool') or step.get('name') or '').strip()
            args = step.get('args') or {}
            if not name or name not in _PLAN_EXEC_WHITELIST:
                lines.append(f'Step {i} ({name or "unknown"}): BLOCKED_BY_POLICY (not on plan whitelist)')
                continue
            fn = getattr(sys.modules[__name__], name, None)
            if fn is None:
                lines.append(f'Step {i} ({name}): UNKNOWN_TOOL')
                continue
            out = _call_tool_arg_tolerant(fn, args)
            lines.append(f'Step {i} ({name}): {str(out)[:500]}')
        if not lines:
            return 'Error: plan produced no executable steps.'
        return '\n'.join(lines)
    except Exception as e:
        return f'Plan error: {e}'


def mcp_execute(server: str, tool_name: str, tool_args: dict | None = None) -> str:
    """Execute a tool on a registered MCP server. `server` is the registered name (see list_mcp_servers)."""
    import mcp_client_core
    servers = _load_mcp_servers()
    match = next((s for s in servers if s.get('name') == server), None)
    if not match:
        return f"UNKNOWN MCP SERVER: {server} (registered: {', '.join(s.get('name', '?') for s in servers) or 'none'})"
    return mcp_client_core.run_mcp_tool(
        match.get('command', 'npx'),
        match.get('args', []),
        tool_name,
        dict(tool_args or {}),
    )


AVAILABLE_TOOLS = [
    execute_computer_use,
    dispatch_coder_swarm,
    dispatch_browser_swarm,
    conduct_deep_research,
    fetch_rss,
    optimize_system,
    switch_to_offline,
    system_control,
    analyze_screen,
    execute_python_sandbox,
    dispatch_mcp_swarm,
    start_visual_autopilot,
    run_rovo_dev,
    open_app_or_url,
    search_web,
    diagnostics_report,
    list_apps,
    query_knowledge_graph,
    apilayer_request,
    mcp_execute,
    list_mcp_servers,
    plan_and_execute,
    todo_add,
    todo_list,
    todo_mark,
    swarm_cache_put,
    swarm_cache_get,
    swarm_cache_stats,
]
