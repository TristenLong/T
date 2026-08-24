import base64
import json
import os
from io import BytesIO

import pyautogui
import pytesseract
from PIL import Image

import llm_router


class VisionCore:
    def __init__(self):
        # Configure tesseract path if needed, usually in PATH on linux/mac, might need manual path on Windows
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        pass

    def capture_screen(self):
        """Captures the current screen and returns it as a base64 encoded string."""
        screenshot = pyautogui.screenshot()
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def extract_text(self):
        """Extracts text from the current screen using OCR."""
        screenshot = pyautogui.screenshot()
        text = pytesseract.image_to_string(screenshot)
        return text

    def analyze_screen_semantic(self, prompt="Describe what is on the screen in detail."):
        """Uses the multimodal LLM to analyze the screen semantically."""
        print(f"[VISION CORE] Semantic screen analysis requested...")
        try:
            b64_image = self.capture_screen()
            
            # Use OpenAI Vision if available via llm_router
            if llm_router.OPENAI_API_KEY:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64_image}"
                                }
                            }
                        ]
                    }
                ]
                # Assuming llm_router.generate_completion handles the messages properly
                res = llm_router.generate_completion(messages)
                return {"status": "success", "analysis": res}
            else:
                return {"status": "error", "message": "OPENAI_API_KEY required for semantic vision."}
                
        except Exception as e:
            return {"status": "error", "message": f"Semantic analysis failed: {str(e)}"}

    def find_and_click_text(self, target_text):
        """Finds text on the screen and clicks it using real Tesseract OCR."""
        print(f"[VISION CORE] Scanning screen for '{target_text}' to click...")
        screenshot = pyautogui.screenshot()
        
        try:
            # Use Tesseract to get detailed bounding box data
            data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
            
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                if target_text.lower() in text.lower() and text != "":
                    # Found a match, calculate the center of the bounding box
                    x = data['left'][i]
                    y = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    
                    center_x = x + (w / 2)
                    center_y = y + (h / 2)
                    
                    print(f"[VISION CORE] Match found at ({center_x}, {center_y}). Executing click.")
                    pyautogui.click(center_x, center_y)
                    return {"status": "success", "message": f"Clicked '{text}' at ({center_x}, {center_y})"}
            
            return {"status": "failed", "message": f"Could not find '{target_text}' on screen."}
        except Exception as e:
            return {"status": "error", "message": f"OCR failed: {str(e)}"}

    def execute_mouse_command(self, action, x=None, y=None):
        if action == "click" and x and y:
            pyautogui.click(x=x, y=y)
            return {"status": "success"}
        elif action == "scroll":
            pyautogui.scroll(-500) # scroll down
            return {"status": "success"}
        return {"status": "failed", "reason": "Unknown action"}

    def execute_keyboard_command(self, text):
        pyautogui.write(text, interval=0.05)
        pyautogui.press('enter')
        return {"status": "success"}

vision_core = VisionCore()
