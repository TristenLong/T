import subprocess
import time
import sys
import os
import datetime

BOT_SCRIPT = 'bot.py'
UV_PATH = r'C:\Users\trist\.local\bin\uv.exe'
RESTART_DELAY = 5
CRASH_LOG = 'CRASH_REPORT.log'

def log_crash(code):
    with open(CRASH_LOG, 'a') as f:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f'[{timestamp}] CRASH DETECTED. Exit Code: {code}\\n')

def run_bot():
    print(f'?? WATCHDOG V2: Launching {BOT_SCRIPT} with FAILSAFE protection...')
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8' 
    
    crash_count = 0
    
    while True:
        try:
            process = subprocess.Popen(
                [UV_PATH, 'run', BOT_SCRIPT],
                cwd=os.getcwd(),
                env=env
            )
            
            print(f'?? WATCHDOG: Bot running (PID: {process.pid})')
            return_code = process.wait()
            
            if return_code == 42:
                print('?? WATCHDOG: Manual Restart Triggered.')
                crash_count = 0 # Reset on manual restart
                time.sleep(1)
                continue
            elif return_code == 0:
                print('?? WATCHDOG: Bot exited normally. Shutting down.')
                break
            else:
                log_crash(return_code)
                crash_count += 1
                print(f'?? WATCHDOG: Bot crashed (Code {return_code}). Restarting in {RESTART_DELAY}s...')
                
                if crash_count > 5:
                    print('?? WATCHDOG: CRITICAL INSTABILITY. 5 consecutive crashes. Increasing delay.')
                    time.sleep(RESTART_DELAY * 2)
                else:
                    time.sleep(RESTART_DELAY)
                
        except KeyboardInterrupt:
            if process: process.terminate()
            break
        except Exception as e:
            print(f'?? WATCHDOG: Fatal error: {e}')
            time.sleep(RESTART_DELAY)

if __name__ == '__main__':
    run_bot()
