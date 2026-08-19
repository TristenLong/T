import subprocess
import time
import os
import sys

def run_watchdog():
    script_path = "realtime_science_engine.py"
    target_dir = r"C:\Users\trist\gemini-voice-assistant\GOD_HAND_CORE"
    
    print("===================================================")
    print("   JESTER V1000 - AUTONOMOUS HYPERVISOR (WATCHDOG) ")
    print("===================================================")
    
    while True:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Booting Science Engine...")
        try:
            # Run the process
            process = subprocess.Popen([sys.executable, script_path], cwd=target_dir)
            
            # Wait for it to finish/crash
            process.wait()
            
            # If we get here, the process crashed
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] \033[91mCRITICAL:\033[0m Engine crashed or exited with code {process.returncode}!")
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] \033[91mERROR\033[0m starting engine: {e}")
            
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SELF-HEALING: Rebooting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    os.system('color')
    run_watchdog()
