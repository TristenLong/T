"""Hot-loadable swarm tool plugins.

Each *.py in this directory is a plugin. Contract:
  - filename is a valid python identifier (the plugin name)
  - tools are top-level functions named <name>_tool (must end in _tool)
  - optional _self_check() -> "OK" or "FAIL: <reason>" gates acceptance

Tools become callable immediately (no restart), both from /api/execute_tool
and from the LLM tool loop (server_tools.AVAILABLE_TOOLS is refreshed on
change). Broken or failing plugins roll back: no dead files, no half-registered
tools.
"""
import inspect
import os
import re
import subprocess
import sys
import time
import types

_plugin_dir = os.path.dirname(os.path.abspath(__file__))
loaded = {}  # name -> {"module": mod, "tools": {tool_name: fn}, "file": str}

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TOOL_RE = re.compile(r"^[a-z_][a-z0-9_]*_tool$")


def configure(plugin_dir=None):
    """Point the loader at a different plugin directory (used by tests).

    Resets the registry so a fresh plugin dir has a clean slate. The given
    directory is created if missing.
    """
    global _plugin_dir
    if plugin_dir:
        _plugin_dir = os.path.abspath(plugin_dir)
        os.makedirs(_plugin_dir, exist_ok=True)
    loaded.clear()
    for mod in [m for m in sys.modules if m.startswith("_jester_plugin_")]:
        sys.modules.pop(mod, None)


def _repo_root():
    cand = os.path.abspath(os.path.join(_plugin_dir, "..", ".."))
    return cand if os.path.isdir(os.path.join(cand, ".git")) else None


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, timeout=30)


def _commit_plugin(action, name, tools=None):
    """Commit a grown/removed plugin so runtime growth survives restarts."""
    repo = _repo_root()
    if not repo:
        return "SKIP_NO_GIT"
    path = os.path.relpath(_module_path(name), repo)
    try:
        if action == "grow":
            staged = _git(repo, "add", "--", path)
            if staged.returncode != 0:
                return f"GIT_ERR:add:{staged.stderr.strip()[:120]}"
            result = _git(repo, "commit", "--only", "-m",
                          f"[PLUGIN] grow {name}: {', '.join(tools or [])}", "--", path)
        else:
            removed = _git(repo, "rm", "-f", "--ignore-unmatch", "--", path)
            if removed.returncode != 0:
                return f"GIT_ERR:rm:{removed.stderr.strip()[:120]}"
            result = _git(repo, "commit", "--only", "-m",
                          f"[PLUGIN] remove {name}", "--", path)
        # Transient index.lock contention (e.g. a session-close commit) is
        # common on a self-committing app: retry briefly before giving up.
        for _ in range(3):
            if result.returncode != 0 and "index.lock" in result.stderr:
                time.sleep(0.8)
                result = _git(repo, "commit", "--only", "-m",
                              f"[PLUGIN] grow {name}: {', '.join(tools or [])}"
                              if action == "grow"
                              else f"[PLUGIN] remove {name}", "--", path)
            else:
                break
        if result.returncode != 0:
            return f"GIT_ERR:commit:{result.stderr.strip()[:120]}"
        return "COMMITTED"
    except Exception as e:
        return f"GIT_ERR:{e}"


def _module_name(name):
    return f"_jester_plugin_{name}"


def _module_path(name):
    return os.path.join(_plugin_dir, f"{name}.py")


def _collect_tools(mod):
    tools = {}
    for attr in dir(mod):
        if _TOOL_RE.match(attr):
            fn = getattr(mod, attr)
            if callable(fn):
                tools[attr] = fn
    return tools


def _self_check(mod):
    chk = getattr(mod, "_self_check", None)
    if not callable(chk):
        return None
    res = chk()
    if isinstance(res, str) and res.strip().upper().startswith("OK"):
        return None
    return str(res)


def _forget(name):
    prev = loaded.pop(name, None)
    if prev:
        sys.modules.pop(_module_name(name), None)
    return prev


def load_plugin_file(name):
    """Import one plugin file (no registration); raises on any problem.

    Executes the current source directly (never the bytecode cache) so a
    re-grow is guaranteed to see the latest file contents.
    """
    path = _module_path(name)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    code = compile(source, path, "exec")
    fullname = _module_name(name)
    mod = types.ModuleType(fullname)
    mod.__file__ = path
    sys.modules[fullname] = mod
    exec(code, mod.__dict__)
    tools = _collect_tools(mod)
    if not tools:
        raise ValueError(f"plugin '{name}' defines no *_tool functions")
    prob = _self_check(mod)
    if prob:
        raise ValueError(f"self_check failed: {prob}")
    return {"module": mod, "tools": tools, "file": path}


def grow(name, source, commit=False):
    """Validate, persist, import, and hot-register one plugin. No-op on failure.

    Returns {"name", "ok", "tools": [...], "commit": str|None, "error": str|None}.
    On failure the file is removed and nothing is registered (no dead files).
    With commit=True a good registration is committed to git (self-versioning).
    """
    name = str(name).strip()
    if not NAME_RE.match(name):
        return {"name": name, "ok": False, "error": "invalid plugin name (need [A-Za-z_][A-Za-z0-9_]*)"}
    if not isinstance(source, str) or not source.strip():
        return {"name": name, "ok": False, "error": "empty source"}
    try:
        compile(source, f"<plugin:{name}>", "exec")
    except SyntaxError as e:
        return {"name": name, "ok": False, "error": f"syntax error: {e}"}
    _forget(name)
    path = _module_path(name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        loaded[name] = load_plugin_file(name)
    except Exception as e:
        _forget(name)
        try:
            os.remove(path)
        except OSError:
            pass
        return {"name": name, "ok": False, "error": f"load failed: {e}"}
    tools = sorted(loaded[name]["tools"])
    res = {"name": name, "ok": True, "tools": tools, "commit": None}
    if commit:
        res["commit"] = _commit_plugin("grow", name, tools)
    return res


def remove(name, commit=False):
    _forget(name)
    try:
        os.remove(_module_path(name))
    except OSError:
        pass
    res = {"name": name, "ok": True, "commit": None}
    if commit:
        res["commit"] = _commit_plugin("remove", name)
    return res


def reload_all():
    seen = []
    for fn_ in sorted(os.listdir(_plugin_dir)):
        if fn_.endswith(".py") and fn_ != "__init__.py":
            name = fn_[:-3]
            if NAME_RE.match(name):
                try:
                    loaded[name] = load_plugin_file(name)
                    seen.append(name)
                except Exception as e:
                    print(f"[plugin] {name}: {e}")
    return seen


def tool_function(name):
    for p in loaded.values():
        if name in p["tools"]:
            return p["tools"][name]
    return None


def invoke(name, args=None):
    """Call a plugin tool by name with an args dict. Returns None if unknown."""
    fn = tool_function(name)
    if fn is None:
        return None
    kw = {}
    if args:
        params = inspect.signature(fn).parameters
        has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        for k, v in args.items():
            if k in params or has_varkw:
                kw[k] = v
    return fn(**kw)


def iter_tool_functions():
    for p in loaded.values():
        for name, fn in p["tools"].items():
            yield name, fn


def list_plugins():
    out = []
    for name, p in loaded.items():
        out.append({"name": name, "file": os.path.basename(p["file"]), "tools": sorted(p["tools"])})
    return out