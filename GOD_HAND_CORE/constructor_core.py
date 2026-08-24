import os
import re
import subprocess
import webbrowser

PUBLIC_DIR = r"C:\Users\trist\gemini-voice-assistant\public\dashboards"
if not os.path.exists(PUBLIC_DIR):
    os.makedirs(PUBLIC_DIR)

def scan_network():
    try:
        output = subprocess.check_output("arp -a", shell=True).decode()
        devices = []
        for line in output.splitlines():
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(\w+)", line)
            if m: devices.append({"ip": m.group(1), "mac": m.group(2), "type": m.group(3)})
        return devices
    except Exception as e: return str(e)

def create_dashboard(filename, content):
    if not filename.endswith(".html"): filename += ".html"
    path = os.path.join(PUBLIC_DIR, filename)
    
    if "<html" not in content:
        content = f"""<!DOCTYPE html>
<html>
<head>
<title>JESTER CONSTRUCT: {filename}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>body {{ background: #000; color: #0f0; font-family: monospace; }}</style>
</head>
<body class="p-10">
<h1 class="text-3xl font-bold mb-5 border-b border-green-500 pb-2">CONSTRUCT // {filename}</h1>
{content}
</body></html>"""

    try:
        with open(path, "w", encoding="utf-8") as f: f.write(content)
        url = f"http://localhost:5173/dashboards/{filename}"
        webbrowser.open(url)
        return f"DEPLOYED: {url}"
    except Exception as e: return str(e)
