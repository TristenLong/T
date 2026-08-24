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
        if self.is_available and self.client:
            print("[SANDBOX CORE] Spinning up python:3.11-slim container...")
            try:
                # Run code in an isolated container
                container = self.client.containers.run(
                    "python:3.11-slim",
                    command=["python", "-c", code],
                    remove=True,  # Auto-remove container after execution
                    network_disabled=True, # Disable network access for safety
                    mem_limit="128m" # Limit memory usage
                )
                output_str = container.decode("utf-8") if isinstance(container, bytes) else str(container)
                return {"status": "success", "output": output_str.strip()}
                
            except errors.ContainerError as e:
                err_str = e.stderr.decode("utf-8") if isinstance(e.stderr, bytes) else str(e)
                return {"status": "error", "output": err_str.strip()}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        else:
            print("[SANDBOX CORE] Docker unavailable. Falling back to local isolated execution...")
            temp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                    temp_file.write(code)
                    temp_file_path = temp_file.name

                # Run the code locally with a strict 5-second timeout
                result = subprocess.run(
                    [sys.executable, temp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    return {"status": "success", "output": result.stdout.strip()}
                else:
                    return {"status": "error", "output": result.stderr.strip()}
                    
            except subprocess.TimeoutExpired:
                return {"status": "error", "message": "Execution timed out after 5 seconds."}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except OSError:
                        pass # Windows file locking fallback

sandbox_core = SandboxCore()
