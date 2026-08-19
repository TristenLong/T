import os
import subprocess
import psutil

def set_power_mode(mode="balanced"):
    PLANS = {
        "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
        "high_perf": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
        "saver": "a1841308-3541-4fab-bc81-f71556f20b4a"
    }
    guid = PLANS.get(mode, PLANS["balanced"])
    os.system(f"powercfg /setactive {guid}")
    return f"POWER: {mode.upper()}"

def kill_process(name_fragment):
    killed = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if name_fragment.lower() in proc.info['name'].lower():
                proc.kill()
                killed.append(proc.info['name'])
        except: pass
    return killed

def clean_temp():
    temp_dir = os.environ.get('TEMP')
    deleted = 0
    if temp_dir:
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                    deleted += 1
                except: pass
    return f"CLEANED_{deleted}_FILES"

def optimize(target="mining"):
    report = []
    if target == "mining":
        report.append(set_power_mode("high_perf"))
        bloat = ["onedrive", "teams", "msedge", "skype", "cortana"]
        for b in bloat:
            k = kill_process(b)
            if k: report.append(f"KILLED: {k}")
        report.append(clean_temp())
    elif target == "gaming":
        report.append(set_power_mode("high_perf"))
        k = kill_process("SRBMiner")
        report.append(f"MINER_PAUSED: {k}")
    return "\n".join(report)
