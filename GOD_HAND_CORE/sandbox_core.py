import os
import subprocess
import sys
import tempfile

try:
    import docker
    from docker import errors
except ImportError:
    docker = None
    errors = None

# Environment variables that must never be visible to executed code. The
# fallback path below runs in this process's own environment, so without this
# filter any snippet could read every API key the server was started with.
_SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")

EXEC_TIMEOUT = float(os.getenv("JESTER_SANDBOX_TIMEOUT", "5"))
# Local execution is unsandboxed. It stays enabled by default because running
# code is the point of this tool, but set JESTER_ALLOW_UNSANDBOXED_EXEC=0 to
# require a real Docker sandbox.
ALLOW_UNSANDBOXED = os.getenv("JESTER_ALLOW_UNSANDBOXED_EXEC", "1") not in ("0", "false", "False")


def _child_env():
    """A copy of the environment with credential-looking entries removed."""
    return {
        k: v for k, v in os.environ.items()
        if not any(marker in k.upper() for marker in _SECRET_ENV_MARKERS)
    }


class SandboxCore:
    def __init__(self):
        self.is_available = False
        self.client = None

        if docker is not None:
            try:
                self.client = docker.from_env()
                # Test connection
                self.client.ping()
                self.is_available = True
                print("[SANDBOX CORE] Connected to Docker daemon.")
            except Exception as e:
                print(f"[SANDBOX CORE] Warning: Could not connect to Docker daemon. {e}")
        else:
            print("[SANDBOX CORE] Warning: Docker SDK for Python is not installed.")

    def execute_python_code(self, code):
        if not isinstance(code, str) or not code.strip():
            return {"status": "error", "message": "No code provided."}

        if self.is_available and self.client:
            print("[SANDBOX CORE] Spinning up python:3.11-slim container...")
            try:
                # Run code in an isolated container
                container = self.client.containers.run(
                    "python:3.11-slim",
                    command=["python", "-c", code],
                    remove=True,  # Auto-remove container after execution
                    network_disabled=True, # Disable network access for safety
                    mem_limit="128m", # Limit memory usage
                )
                output_str = container.decode("utf-8") if isinstance(container, bytes) else str(container)
                return {"status": "success", "output": output_str.strip()}

            except errors.ContainerError as e:
                err_str = e.stderr.decode("utf-8") if isinstance(e.stderr, bytes) else str(e)
                return {"status": "error", "output": err_str.strip()}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        if not ALLOW_UNSANDBOXED:
            return {
                "status": "error",
                "message": (
                    "Docker is unavailable and unsandboxed execution is disabled "
                    "(JESTER_ALLOW_UNSANDBOXED_EXEC=0). Start Docker to run code."
                ),
            }

        # The previous log line called this "local isolated execution", which it
        # is not: the code runs as the current user with full filesystem and
        # network access. Say so plainly instead of implying containment.
        print(
            "[SANDBOX CORE] *** WARNING: Docker unavailable -- executing code "
            "UNSANDBOXED as the current user (full disk and network access). ***"
        )
        try:
            # A dedicated temp dir doubles as the child's cwd, so relative-path
            # writes land there instead of in the server's working directory.
            with tempfile.TemporaryDirectory(prefix="jester_sandbox_") as work_dir:
                script_path = os.path.join(work_dir, "snippet.py")
                with open(script_path, "w", encoding="utf-8") as handle:
                    handle.write(code)

                try:
                    result = subprocess.run(
                        [sys.executable, script_path],
                        capture_output=True,
                        text=True,
                        timeout=EXEC_TIMEOUT,
                        cwd=work_dir,
                        env=_child_env(),
                        stdin=subprocess.DEVNULL,
                    )
                except subprocess.TimeoutExpired as e:
                    # Surface whatever the snippet managed to print before the
                    # timeout; the old handler discarded it.
                    partial = (e.stdout or "")
                    if isinstance(partial, bytes):
                        partial = partial.decode("utf-8", "replace")
                    return {
                        "status": "error",
                        "message": f"Execution timed out after {EXEC_TIMEOUT:g} seconds.",
                        "output": partial.strip(),
                    }

                if result.returncode == 0:
                    return {"status": "success", "output": result.stdout.strip()}
                return {
                    "status": "error",
                    "output": (result.stderr or result.stdout).strip(),
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

sandbox_core = SandboxCore()
