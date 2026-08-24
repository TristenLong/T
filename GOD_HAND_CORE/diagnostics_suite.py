import importlib
import os
import subprocess
import sys
import time

import psutil
import requests
from dotenv import load_dotenv

REQUIRED_PACKAGES = [
    'requests', 'psutil', 'rich', 'openai', 'pyautogui', 
    'pyperclip', 'numpy', 'opencv-python', 'duckduckgo-search'
]

def check_internet():
    try:
        requests.get('https://www.google.com', timeout=3)
        return True
    except:
        return False

def check_api_key(name):
    key = os.getenv(name)
    if not key or len(key) < 5:
        return False
    return True

def self_heal_packages():
    print('?? SCANNING NEURAL MODULES (Dependencies)...')
    for package in REQUIRED_PACKAGES:
        try:
            import_name = package.replace('-', '_')
            if package == 'opencv-python': import_name = 'cv2'
            if package == 'duckduckgo-search': import_name = 'duckduckgo_search'
            
            importlib.import_module(import_name)
        except ImportError:
            print(f'?? {package} CORRUPTED. INITIATING AUTO-REPAIR...')
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f'?? {package} RESTORED.')

def test_openai_connection():
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "PING"}],
            max_tokens=5
        )
        return True, response.choices[0].message.content
    except Exception as e:
        return False, str(e)

def get_system_report():
    load_dotenv(override=True)
    report = []
    
    # 1. Internet
    if check_internet(): report.append("Internet: ONLINE.")
    else: report.append("Internet: OFFLINE.")

    # 2. Resources
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    report.append(f"CPU: {cpu}%. RAM: {ram}%.")

    # 3. OpenAI Core
    if check_api_key('OPENAI_API_KEY'):
        status, msg = test_openai_connection()
        if status: report.append("OpenAI Core: OPERATIONAL.")
        else: report.append(f"OpenAI Core: FAILED ({msg}).")
    else:
        report.append("OpenAI Key: MISSING.")

    # 4. Legacy/Backup Keys
    for key in ['GEMINI_API_KEY', 'DEEPGRAM_API_KEY']:
        if check_api_key(key): report.append(f"{key.split('_')[0]}: Ready.")
    
    return " ".join(report)

def run_stress_test():
    from rich.console import Console
    console = Console()
    console.print('\n[bold cyan]>> INITIATING DIAGNOSTICS (JESTER V081)...[/bold cyan]')
    print(get_system_report())

if __name__ == '__main__':
    self_heal_packages()
    run_stress_test()
