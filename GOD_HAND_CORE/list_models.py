import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=API_KEY)

print("AVAILABLE MODELS:")
try:
    for model in client.models.list():
        print(f"- {model.name}")
except Exception as e:
    print(f"ERROR LISTING MODELS: {str(e)}")
