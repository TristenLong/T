import os
import socket
import subprocess
import sys
import time

VITE_HOST = "127.0.0.1"
VITE_PORT = 5173
VITE_TIMEOUT = 30


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

    # NOTE: the backend is intentionally NOT started here. main.cjs already
    # spawns GOD_HAND_CORE/server.py ("Flask API") on Electron's ready event,
    # and starting it here too made a second instance race for port 5000 and
    # die with EADDRINUSE. Electron owns the backend lifecycle.

    electron_path = os.path.join(base_dir, "node_modules", ".bin", "electron.cmd")
    if not os.path.exists(electron_path):
        print(f"[ERROR] Electron not found at {electron_path}")
        print("[ERROR] Run 'npm install' first.")
        return 1

    print("[SYSTEM] Starting Vite Dev Server...")
    vite_process = subprocess.Popen(["npx", "vite"], shell=True)

    try:
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
        input("Press Enter to exit...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
