import asyncio
import os
import sys

from pydantic import BaseModel, Field

# Add GOD_HAND_CORE itself
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    import pyautogui

    import browser_core
    import coder_core
    import computer_use
    import memory_core
    import offline_brain
    import reddit_core
    import research_core
    import system_core
    import vision_core
    from sandbox_core import sandbox_core

    pyautogui.FAILSAFE = False

except ImportError as e:
    print(f"Error importing core modules: {e}")

def execute_computer_use(action: str, params: dict | None = None) -> str:
    """Direct OS GUI control, keystrokes & mouse navigation."""
    try:
        return computer_use.execute_computer_action(action, params or {})
    except Exception as e:
        return f"Error: {e}"

def dispatch_coder_swarm(prompt: str) -> str:
    """Dispatch autonomous coding task to Architect CoderCore sub-agent."""
    try:
        coder = coder_core.CoderCore(memory_core)
        return asyncio.run(coder.run_coding_task(prompt))
    except Exception as e:
        return f"Error: {e}"

def dispatch_browser_swarm(task: str) -> str:
    """Dispatch web navigation task to Navigator BrowserCore sub-agent."""
    try:
        browser = browser_core.BrowserCore(memory_core)
        return asyncio.run(browser.navigate_and_interact(task))
    except Exception as e:
        return f"Error: {e}"

def conduct_deep_research(query: str) -> str:
    """Multi-query web crawling and research aggregation."""
    try:
        return research_core.deep_research(query)
    except Exception as e:
        return f"Error: {e}"

def check_reddit(subreddit: str) -> str:
    """Subreddit scanner & sentiment extraction."""
    try:
        return reddit_core.scan_subreddit(subreddit)
    except Exception as e:
        return f"Error: {e}"

def optimize_system(target: str = "mining") -> str:
    """Optimize system performance."""
    try:
        return system_core.optimize(target)
    except Exception as e:
        return f"Error: {e}"

def switch_to_offline(message: str = "status") -> str:
    """Switch to offline mode and query local brain."""
    try:
        return offline_brain.brain.chat(message)
    except Exception as e:
        return f"Error: {e}"

def system_control(action: str, value: str = "") -> str:
    """Control IO. Actions: type, press, minimize_all, open_start."""
    try:
        if action == 'type': pyautogui.write(value)
        elif action == 'press': pyautogui.press(value)
        elif action == 'minimize_all': pyautogui.hotkey('win', 'd')
        elif action == 'open_start': pyautogui.press('win')
        return "DONE"
    except Exception as e:
        return f"Error: {e}"

def analyze_screen(prompt: str = "Describe the current screen") -> str:
    """Analyze the current screen semantically."""
    try:
        res = vision_core.vision_core.analyze_screen_semantic(prompt)
        return str(res)
    except Exception as e:
        return f"Error: {e}"

def execute_python_sandbox(code: str) -> str:
    """Execute Python code in a safe Docker sandbox container."""
    try:
        res = sandbox_core.execute_python_code(code)
        return str(res)
    except Exception as e:
        return f"Sandbox Error: {e}"

def dispatch_mcp_swarm(task: str) -> str:
    """Spawns an autonomous background MCP agent to complete a task using Model Context Protocol tools."""
    try:
        import sub_agent_core
        return sub_agent_core.spawn_agent(task, agent_type="mcp_agent")
    except Exception as e:
        return f"Error: {e}"

def start_visual_autopilot(objective: str) -> str:
    """Starts the Visual Auto-Pilot to physically control the computer using semantic screen analysis to complete an objective."""
    try:
        import computer_use
        return computer_use.auto_pilot(objective)
    except Exception as e:
        return f"Error: {e}"

AVAILABLE_TOOLS = [
    execute_computer_use,
    dispatch_coder_swarm,
    dispatch_browser_swarm,
    conduct_deep_research,
    check_reddit,
    optimize_system,
    switch_to_offline,
    system_control,
    analyze_screen,
    execute_python_sandbox,
    dispatch_mcp_swarm,
    start_visual_autopilot
]
