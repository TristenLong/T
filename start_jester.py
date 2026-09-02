import os
import socket
import subprocess
import sys
import time

VITE_HOST = "127.0.0.1"
VITE_PORT = 5173
VITE_TIMEOUT = 30

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_TIMEOUT = 60


def is_port_open(host, port, timeout=0.75):
    """Single-shot check: is something already accepting connections there?"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host, port, timeout):
    """Block until something accepts connections on host:port, or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def stop_process_tree(proc, label):
    """Kill proc and its children without touching unrelated processes.

    Popen(..., shell=True) returns the PID of the intermediary shell, so
    terminate() would leave the real Vite/Node child orphaned. On Windows
    'taskkill /T' walks the tree from that PID -- targeted, unlike a
    machine-wide '/IM node.exe'.
    """
    if proc.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/pid", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc.terminate()

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print(f"[WARN] {label} did not exit gracefully; killing.")
        proc.kill()


def main():
    print("=" * 63)
    print("   INITIALIZING JESTER V2000: SINGULARITY (SWARM HYPERVISOR)...")
    print("=" * 63)

    # Locate Python executable in virtual environments or fallback to system
    base_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = os.path.join(base_dir, "GOD_HAND_CORE", ".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    print(f"[SYSTEM] Using Python: {python_exe}")

    # Start the backend here, guarded by a port check.
    #
    # This used to be Electron's job alone ("Electron owns the backend
    # lifecycle") to avoid two instances racing for port 5000. That turned
    # Electron into a single point of failure: if it failed to launch, Vite
    # still served the UI, every /api call proxied into a dead port, and the app
    # looked broken with no error anywhere explaining why. main.cjs now performs
    # the same check, so whichever launcher gets there first starts the backend
    # and the other attaches -- no duplicate, no EADDRINUSE, and no silent
    # backend-less UI.
    flask_process = None
    god_hand_dir = os.path.join(base_dir, "GOD_HAND_CORE")
    if is_port_open(FLASK_HOST, FLASK_PORT):
        print(f"[SYSTEM] Backend already listening on {FLASK_HOST}:{FLASK_PORT}; attaching.")
    elif not os.path.isfile(os.path.join(god_hand_dir, "server.py")):
        print(f"[ERROR] Backend not found at {os.path.join(god_hand_dir, 'server.py')}")
        return 1
    else:
        print("[SYSTEM] Starting Flask backend (GOD_HAND_CORE/server.py)...")
        # python_exe is the GOD_HAND_CORE venv interpreter when it exists, so
        # this does not depend on 'uv' being installed the way main.cjs does.
        flask_process = subprocess.Popen([python_exe, "server.py"], cwd=god_hand_dir)

    electron_path = os.path.join(base_dir, "node_modules", ".bin", "electron.cmd")
    if not os.path.exists(electron_path):
        print(f"[ERROR] Electron not found at {electron_path}")
        print("[ERROR] Run 'npm install' first.")
        if flask_process is not None:
            stop_process_tree(flask_process, "Flask backend")
        return 1

    print("[SYSTEM] Starting Vite Dev Server...")
    vite_process = subprocess.Popen(["npx", "vite"], shell=True)

    try:
        if flask_process is not None:
            print(f"[SYSTEM] Waiting for backend on {FLASK_HOST}:{FLASK_PORT}...")
            if wait_for_port(FLASK_HOST, FLASK_PORT, FLASK_TIMEOUT):
                print("[SYSTEM] Backend is up.")
            else:
                # Loud, because this is exactly the failure that used to be
                # invisible: the UI loads and then nothing works.
                print(
                    f"[ERROR] Backend did not bind {FLASK_HOST}:{FLASK_PORT} within "
                    f"{FLASK_TIMEOUT}s. The UI will load but every /api call will fail."
                )
                if flask_process.poll() is not None:
                    print(f"[ERROR] Backend process already exited (code {flask_process.returncode}).")

        print(f"[SYSTEM] Waiting for Vite on {VITE_HOST}:{VITE_PORT}...")
        if wait_for_port(VITE_HOST, VITE_PORT, VITE_TIMEOUT):
            print("[SYSTEM] Vite is up.")
        else:
            # Not fatal: main.cjs retries loadURL, so Electron can still recover.
            print(f"[WARN] Vite did not bind within {VITE_TIMEOUT}s; starting Electron anyway.")

        print("[SYSTEM] Booting JESTER Electron HUD...")
        subprocess.run([electron_path, ".", "--dev"], shell=True)
    finally:
        # Terminate only the tree we started. The previous implementation ran
        # 'taskkill /f /im node.exe', which killed every Node process on the
        # machine -- unrelated dev servers and editor language servers included.
        print("[SYSTEM] Shutting down...")
        stop_process_tree(vite_process, "Vite")
        if flask_process is not None:
            stop_process_tree(flask_process, "Flask backend")
        input("Press Enter to exit...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
