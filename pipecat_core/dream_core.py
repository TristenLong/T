import os
import requests
from openai import OpenAI
from dotenv import load_dotenv
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

PUBLIC_DREAMS_DIR = r"C:\Users\trist\gemini-voice-assistant\public\dreams"
if not os.path.exists(PUBLIC_DREAMS_DIR):
    os.makedirs(PUBLIC_DREAMS_DIR)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def generate_dream(prompt):
    if not OPENAI_API_KEY:
        return {"status": "ERROR", "message": "No OpenAI Key"}

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url
        
        timestamp = int(time.time())
        filename = f"dream_{timestamp}.png"
        filepath = os.path.join(PUBLIC_DREAMS_DIR, filename)
        
        img_data = requests.get(image_url).content
        with open(filepath, "wb") as f:
            f.write(img_data)
            
        local_url = f"http://localhost:5173/dreams/{filename}"
        webbrowser.open(local_url)
        
        return {"status": "DREAM_MANIFESTED", "url": local_url}
        
    except Exception as e:
        return {"status": "NIGHTMARE", "error": str(e)}
