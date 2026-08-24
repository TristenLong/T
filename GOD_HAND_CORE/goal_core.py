import json
import os
import subprocess

import system_core

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
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JESTER V2000").Show([Windows.UI.Notifications.ToastNotification]::new($t))
    """
    subprocess.run(["powershell", "-Command", script], capture_output=True)

def execute_directive():
    goal = get_directive()
    if goal == "passive": return
    
    if goal == "swarm_optimize" or goal == "performance_mode":
        system_core.optimize("system")
        notify("JESTER SINGULARITY", "System performance optimized for AI Swarm.")
        return "OPTIMIZED_FOR_SWARM"
        
    if goal == "gaming_mode":
        notify("JESTER SINGULARITY", "Gaming Mode Active. Background workloads silenced.")
        return "GAMING_MODE_ACTIVE"

