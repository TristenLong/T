import logging
import socket
import subprocess
import sys
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Watchdog")

SCRIPT_TO_RUN = "realtime_science_engine.py"
RESTART_DELAY = 5  # seconds to wait before restarting
TARGET_PORT = 8765
MAX_CONSECUTIVE_FAST_FAILS = 5  # Stop if it crashes this many times in a row within FAST_FAIL_WINDOW
FAST_FAIL_WINDOW = 30  # seconds — if process dies within this time, it's a "fast fail"


def kill_port_holder(port):
    """Kill any process holding the target port before launching."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
             f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            logger.info(f"Cleared any zombie process on port {port}.")
    except Exception as e:
        logger.warning(f"Could not clear port {port}: {e}")


def is_port_free(port):
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", port))
            return True
    except OSError:
        return False


def run_watchdog():
    logger.info(f"Starting Watchdog Engine for {SCRIPT_TO_RUN}...")
    consecutive_fast_fails = 0

    while True:
        # --- PRE-LAUNCH: Clear any zombie holding the port ---
        if not is_port_free(TARGET_PORT):
            logger.warning(f"Port {TARGET_PORT} is occupied. Attempting to clear...")
            kill_port_holder(TARGET_PORT)
            time.sleep(2)  # Give OS time to release the socket

            if not is_port_free(TARGET_PORT):
                logger.error(f"Port {TARGET_PORT} STILL occupied after cleanup. Waiting {RESTART_DELAY}s...")
                time.sleep(RESTART_DELAY)
                consecutive_fast_fails += 1
                if consecutive_fast_fails >= MAX_CONSECUTIVE_FAST_FAILS:
                    logger.critical(f"Port {TARGET_PORT} blocked after {MAX_CONSECUTIVE_FAST_FAILS} attempts. "
                                    f"Manual intervention required. Watchdog halting.")
                    break
                continue

        logger.info(f"Launching {SCRIPT_TO_RUN}...")
        start_time = time.time()

        # Start the process
        process = subprocess.Popen([sys.executable, SCRIPT_TO_RUN])

        # Wait for the process to terminate
        process.wait()

        # If it reaches here, the process has stopped (crashed or exited)
        exit_code = process.returncode
        elapsed = time.time() - start_time
        logger.error(f"Process {SCRIPT_TO_RUN} terminated with exit code {exit_code} after {elapsed:.1f}s.")

        if elapsed < FAST_FAIL_WINDOW:
            consecutive_fast_fails += 1
            logger.warning(f"Fast fail detected ({consecutive_fast_fails}/{MAX_CONSECUTIVE_FAST_FAILS}).")
            if consecutive_fast_fails >= MAX_CONSECUTIVE_FAST_FAILS:
                logger.critical(f"{MAX_CONSECUTIVE_FAST_FAILS} consecutive fast failures. "
                                f"Watchdog entering cooldown (60s)...")
                time.sleep(60)
                consecutive_fast_fails = 0  # Reset after cooldown
        else:
            consecutive_fast_fails = 0  # Reset counter on stable run

        logger.info(f"Watchdog self-healing protocol. Restarting in {RESTART_DELAY} seconds...")
        time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    try:
        run_watchdog()
    except KeyboardInterrupt:
        logger.info("Watchdog shutting down manually.")
