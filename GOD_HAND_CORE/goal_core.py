import os
import json
import subprocess
import system_core
import miner_analytics

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GOAL_FILE = os.path.join(BASE_DIR, "jester_directive.json")

def set_directive(goal="passive"):
    with open(GOAL_FILE, "w") as f:
        json.dump({"goal": goal}, f)
    return f"DIRECTIVE_SET: {goal.upper()}"

def get_directive():
    if not os.path.exists(GOAL_FILE): return "passive"
    try:
        with open(GOAL_FILE, "r") as f: return json.load(f).get("goal", "passive")
    except: return "passive"

def notify(title, msg):
    script = f"""
    $t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("{title}")) > $null
    $t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{msg}")) > $null
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JESTER V200").Show([Windows.UI.Notifications.ToastNotification]::new($t))
    """
    subprocess.run(["powershell", "-Command", script], capture_output=True)

def execute_directive():
    goal = get_directive()
    if goal == "passive": return
    
    if goal == "mining_max":
        stats = miner_analytics.analyze_miner()
        if stats.get("status") != "MINING":
            notify("JESTER SINGULARITY", "Miner instability detected. Optimizing system environment...")
            system_core.optimize("mining")
            return "OPTIMIZED_FOR_MINING"
            
    if goal == "gaming_mode":
        # Ensure miner is dead
        killed = system_core.kill_process("SRBMiner")
        if killed:
            notify("JESTER SINGULARITY", "Gaming Mode Enforced. Miner halted.")
