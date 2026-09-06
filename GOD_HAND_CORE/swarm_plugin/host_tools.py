"""Host health, repo state, and log tail utilities for the running JESTER node."""
import os
import re
import subprocess
import time


def _host_load():
    try:
        import psutil
        vm = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        return {
            "ram_percent": vm.percent,
            "ram_used_mb": round((vm.total - vm.available) / (1024 * 1024), 1),
            "ram_free_mb": round(vm.available / (1024 * 1024), 1),
            "cpu_percent": cpu,
            "uptime_seconds": int(time.time() - psutil.boot_time()),
        }
    except Exception as e:
        return {"error": str(e)}


def host_info_tool() -> str:
    """Live host health: RAM %, CPU %, and uptime of the running machine."""
    h = _host_load()
    return " | ".join(f"{k}={v}" for k, v in h.items())


def repo_status_tool() -> str:
    """Git state of the JESTER repo: branch, commit, clean/dirty, top changes."""
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        def sh(*args):
            return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                                  text=True, timeout=30).stdout.strip()
        branch = sh("rev-parse", "--abbrev-ref", "HEAD") or "?"
        sha = sh("rev-parse", "--short", "HEAD") or "?"
        status = sh("status", "--porcelain") or ""
        dirty = "CLEAN" if not status else "DIRTY"
        changed = ", ".join(line[:60].split()[-1] for line in status.splitlines()[:8]) or "none"
        return f"branch={branch} | commit={sha} | tree={dirty} | changed=[{changed}]"
    except Exception as e:
        return f"repo_status error: {e}"


def process_health_tool() -> str:
    """Live process status: server, Ollama, and Vite/node runtimes."""
    try:
        import psutil
        wanted = {"server.py": "server", "ollama": "ollama",
                  "node": "vite/node", "python": "python"}
        found = {}
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                name = (proc.info["name"] or "").lower()
                cmd = " ".join(proc.info["cmdline"] or [])
                for key, label in wanted.items():
                    if key in cmd.lower() or name == key:
                        found.setdefault(label, 0)
                        found[label] += 1
            except Exception:
                continue
        parts = [f"{k}={v}" for k, v in sorted(found.items())] or ["none"]
        return " | ".join(parts)
    except Exception as e:
        return f"process_health error: {e}"


def port_map_tool(port: str = "") -> str:
    """Listening TCP ports with owning process names (optionally filter a port)."""
    try:
        import psutil
        want = str(port or "").strip()
        rows = []
        for conn in psutil.net_connections(kind="inet"):
            try:
                if conn.status != "LISTEN" or conn.laddr is None:
                    continue
                pp = conn.laddr.port
                if want and not re.search(re.escape(want), str(pp)):
                    continue
                pid = conn.pid or 0
                owner = f"pid{pid}"
                if pid:
                    try:
                        owner = psutil.Process(pid).name()
                    except Exception:
                        pass
                rows.append(f"{pp}:{owner}")
            except Exception:
                continue
        rows = sorted(set(rows))
        return "; ".join(rows) if rows else ("no listeners matching " + want if want else "no listeners")
    except Exception as e:
        return f"port_map error: {e}"


def log_tail_tool(lines: int = 15) -> str:
    """Tail the active JESTER server log (up to 50 lines)."""
    lines = max(1, min(int(lines or 15), 50))
    cands = [
        os.path.join(os.environ.get("TEMP", os.environ.get("TMP", "")), "opencode", "jester_server.log"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server.log"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jester_server.log"),
    ]
    for p in cands:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    return "".join(f.readlines()[-lines:])
            except Exception as e:
                return f"log unreadable: {e}"
    return "no server log found"


def _self_check() -> str:
    h = _host_load()
    if "error" in h:
        return "FAIL: " + h["error"]
    return "OK"