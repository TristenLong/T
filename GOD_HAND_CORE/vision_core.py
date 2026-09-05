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
        for candidate in (
            os.getenv('TESSERACT_CMD'),
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ):
            if candidate and os.path.isfile(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                break

    def _ocr_text(self, image):
        """OCR an image, unwrapping the TesseractNotFoundError into a clean message."""
        try:
            return pytesseract.image_to_string(image)
        except pytesseract.TesseractNotFoundError:
            return "OCR_UNAVAILABLE: Tesseract binary not found. Install Tesseract-OCR and set TESSERACT_CMD."
        except Exception as e:
            return f"OCR_ERROR: {e}"

    def capture_screen(self):
        """Captures the current screen and returns it as a base64 encoded string."""
        screenshot = pyautogui.screenshot()
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def extract_text(self):
        """Extracts text from the current screen using OCR."""
        screenshot = pyautogui.screenshot()
        text = self._ocr_text(screenshot)
        return text

    def analyze_screen_semantic(self, prompt="Describe what is on the screen in detail."):
        """Uses the multimodal LLM to analyze the screen semantically."""
        print(f"[VISION CORE] Semantic screen analysis requested...")
        try:
            b64_image = self.capture_screen()

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
            try:
                res, _model = llm_router.generate_vision_completion(messages)
                return {"status": "success", "analysis": res}
            except ValueError as ve:
                # No vision model configured: fall back to OCR so the tool still
                # returns something instead of a cryptic 400.
                ocr = self.extract_text().strip()
                if ocr:
                    return {
                        "status": "success",
                        "analysis": f"(Vision model unavailable; showing OCR text instead. {ve})\n\nOCR:\n{ocr}",
                    }
                return {"status": "error", "message": str(ve)}


        except Exception as e:
            return {"status": "error", "message": f"Semantic analysis failed: {str(e)}"}

    def analyze_webcam(self, prompt: str = "Describe what the webcam sees in detail."):
        """Capture a webcam frame and analyze it semantically via the multimodal LLM."""
        print("[VISION CORE] Webcam capture requested...")
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return {"status": "error", "message": "Webcam not accessible."}
            ok, frame = cap.read()
            cap.release()
            if not ok or frame is None:
                return {"status": "error", "message": "Failed to capture webcam frame."}
            success, jpg = cv2.imencode('.jpg', frame)
            if not success:
                return {"status": "error", "message": "Failed to encode frame."}
            b64_image = base64.b64encode(jpg.tobytes()).decode('utf-8')

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                    ]
                }
            ]
            try:
                res, _model = llm_router.generate_vision_completion(messages)
                return {"status": "success", "analysis": res}
            except ValueError as ve:
                return {"status": "error", "message": str(ve)}
        except Exception as e:
            return {"status": "error", "message": f"Webcam analysis failed: {str(e)}"}

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
