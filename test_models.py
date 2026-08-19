import os
from google import genai
from dotenv import load_dotenv

load_dotenv("C:/Users/trist/gemini-voice-assistant/pipecat_core/.env")
api_key = os.getenv("GEMINI_API_KEY")

try:
    client = genai.Client(api_key=api_key)
    print("Listing models...")
    for m in client.models.list():
        print(f"Model name: {m.name}")
except Exception as e:
    print(f"Error: {e}")
