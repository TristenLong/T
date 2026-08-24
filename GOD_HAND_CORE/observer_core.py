import base64
import io
import json
import os

import pyautogui
from dotenv import load_dotenv
from google import genai
from openai import OpenAI
from PIL import Image

import learning_core

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def analyze_and_extract():
    try:
        screenshot = pyautogui.screenshot()
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format="PNG")
        img_bytes = img_byte_arr.getvalue()
        
        prompt = "Analyze this screen. Extract KEY FACTS as a JSON list of {subject, predicate, object}. Return ONLY JSON."
        raw_text = ""

        if GEMINI_API_KEY:
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                pil_img = Image.open(io.BytesIO(img_bytes))
                model_name = os.getenv("JESTER_PRIMARY_LLM", "gemini-3.1-pro")
                response = client.models.generate_content(model=model_name, contents=[prompt, pil_img])
                raw_text = response.text
            except: pass

        if not raw_text and OPENAI_API_KEY:
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                response = client.chat.completions.create(model="gpt-4o", messages=[
                    {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}
                ])
                raw_text = response.choices[0].message.content
            except: pass

        if raw_text:
            clean = raw_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean)
            learned = []
            for item in data:
                if learning_core.add_fact(item.get("subject"), item.get("predicate"), item.get("object")) == "FACT_MEMORIZED":
                    learned.append(f"{item.get('subject')} -> {item.get('object')}")
            return {"status": "SUCCESS", "new_facts": learned}
            
        return {"status": "NO_DATA"}
    except Exception as e: return {"error": str(e)}
