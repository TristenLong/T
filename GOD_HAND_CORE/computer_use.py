import logging
import os
import time

try:
    import pyautogui
    # Configure failsafe and pause
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

logger = logging.getLogger("COMPUTER_USE")
logger.setLevel(logging.INFO)

def execute_computer_action(action: str, params: dict) -> str:
    """
    Executes a physical computer action.
    action: 'move', 'click', 'type', 'press', 'screenshot', 'info'
    params: dict of arguments for the action.
    """
    if not PYAUTOGUI_AVAILABLE:
        return "[ERROR: pyautogui is not installed. Run pip install pyautogui]"

    try:
        if action == 'info':
            w, h = pyautogui.size()
            x, y = pyautogui.position()
            return f"[INFO] Screen Resolution: {w}x{h}, Current Mouse Position: ({x}, {y})"
            
        elif action == 'move':
            x = int(params.get('x', 0))
            y = int(params.get('y', 0))
            dur = float(params.get('duration', 0.5))
            w, h = pyautogui.size()
            x = max(5, min(x, w - 5))
            y = max(5, min(y, h - 5))
            pyautogui.moveTo(x, y, duration=dur)
            return f"[SUCCESS] Mouse moved to ({x}, {y})"
            
        elif action == 'click':
            if 'x' in params and 'y' in params:
                x = int(params['x'])
                y = int(params['y'])
                w, h = pyautogui.size()
                x = max(5, min(x, w - 5))
                y = max(5, min(y, h - 5))
                pyautogui.click(x, y)
                return f"[SUCCESS] Clicked at ({x}, {y})"
            else:
                pyautogui.click()
                return "[SUCCESS] Clicked at current position"
                
        elif action == 'type':
            text = params.get('text', '')
            interval = float(params.get('interval', 0.05))
            pyautogui.write(text, interval=interval)
            if params.get('enter', False):
                pyautogui.press('enter')
            return f"[SUCCESS] Typed: '{text}'"
            
        elif action == 'press':
            key = params.get('key', '')
            pyautogui.press(key)
            return f"[SUCCESS] Pressed key: '{key}'"
            
        elif action == 'hotkey':
            keys = params.get('keys', [])
            if keys:
                pyautogui.hotkey(*keys)
                return f"[SUCCESS] Executed hotkey: {'+'.join(keys)}"
            return "[ERROR] No keys provided for hotkey"
            
        elif action == 'screenshot':
            path = params.get('path', 'screenshot.png')
            pyautogui.screenshot(path)
            return f"[SUCCESS] Screenshot saved to {path}"
            
        else:
            return f"[ERROR] Unknown computer action: {action}"
            
    except Exception as e:
        logger.error(f"Action {action} failed: {e}")
        return f"[ERROR] Execution failed: {str(e)}"

def auto_pilot(objective: str, max_steps: int = 10) -> str:
    """
    Visual Auto-Pilot: Runs a loop to achieve an objective by capturing the screen, 
    asking the multimodal LLM for the next action, and executing it.
    """
    import vision_core
    import json
    
    logger.info(f"Starting Visual Auto-Pilot for objective: {objective}")
    
    for step in range(max_steps):
        logger.info(f"Auto-Pilot Step {step + 1}/{max_steps}")
        prompt = (
            f"You are a Visual Auto-Pilot. Objective: '{objective}'.\n"
            "Analyze this screenshot and return ONLY valid JSON representing the next physical computer action.\n"
            "Format: {\"action\": \"click\", \"params\": {\"x\": 100, \"y\": 200}} "
            "OR {\"action\": \"type\", \"params\": {\"text\": \"hello\", \"enter\": true}} "
            "OR {\"action\": \"done\", \"params\": {}} if the objective is complete.\n"
            "Make sure to output ONLY JSON."
        )
        
        analysis = vision_core.vision_core.analyze_screen_semantic(prompt)
        if analysis.get('status') == 'error':
            return f"Auto-Pilot Failed: {analysis.get('message')}"
            
        response_text = analysis.get('analysis', '')
        
        try:
            # Strip out markdown block if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            cmd = json.loads(response_text)
            action = cmd.get('action')
            params = cmd.get('params', {})
            
            if action == 'done':
                return f"Auto-Pilot completed objective: {objective}"
                
            logger.info(f"Auto-Pilot executing: {action} with {params}")
            res = execute_computer_action(action, params)
            logger.info(res)
            
            # Wait a moment for the screen to update
            time.sleep(1.5)
            
        except json.JSONDecodeError:
            logger.error(f"Auto-Pilot received invalid JSON: {response_text}")
            return f"Auto-Pilot Failed due to invalid LLM output."
        except Exception as e:
            logger.error(f"Auto-Pilot error: {e}")
            return f"Auto-Pilot Failed: {str(e)}"
            
    return "Auto-Pilot reached max steps without completing the objective."
