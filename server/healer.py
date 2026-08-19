import subprocess
import time
import os
import sqlite3

SERVER_SCRIPT = 'server.py'
DB_FILE = 'jester_V63_SINGULARITY.db'
CRASH_THRESHOLD = 3
TIME_WINDOW = 60

crash_history = []

def purge_memory():
    print('[!] CRITICAL INSTABILITY DETECTED. INITIATING MEMORY PURGE...')
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM history')
        c.execute('DELETE FROM system_state')
        conn.commit()
        conn.close()
        print('[+] MEMORY PURGED. SYSTEM CLEAN.')
    except Exception as e:
        print(f'[!] PURGE FAILED: {e}')

print('[-] JESTER AUTO-HEALER ONLINE. MONITORING V64 CORE...')

while True:
    start_time = time.time()
    process = subprocess.Popen(['python', SERVER_SCRIPT])
    process.wait()
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f'[!] CORE CRASH DETECTED (Runtime: {duration:.2f}s). RESTARTING...')
    
    # Track crash frequency
    current_time = time.time()
    crash_history.append(current_time)
    # Remove old crashes
    crash_history = [t for t in crash_history if current_time - t < TIME_WINDOW]
    
    if len(crash_history) >= CRASH_THRESHOLD:
        purge_memory()
        crash_history = []
        
    time.sleep(2)

