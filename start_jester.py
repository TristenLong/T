import os
import subprocess
import sys
import time


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
    print("[SYSTEM] Starting Vite Dev Server...")
    
    # Start Vite and Electron processes
    vite_process = subprocess.Popen(["npx", "vite"], shell=True)
    
    print("[SYSTEM] Waiting for Vite...")
    time.sleep(3)

    print("[SYSTEM] Booting JESTER Electron HUD...")
    electron_path = os.path.join(base_dir, "node_modules", ".bin", "electron.cmd")
    subprocess.run([electron_path, ".", "--dev"], shell=True)

    # Clean up
    print("[SYSTEM] Shutting down...")
    try:
        subprocess.run(["taskkill", "/f", "/im", "node.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        vite_process.terminate()
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
