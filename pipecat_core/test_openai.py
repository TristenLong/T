import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

api_key = os.getenv("OPENAI_API_KEY")
print(f"API Key found: {bool(api_key)}")

if api_key:
    try:
        client = OpenAI(api_key=api_key)
        models = client.models.list()
        print("OpenAI connectivity: SUCCESS")
    except Exception as e:
        print(f"OpenAI connectivity: FAILED - {str(e)}")
else:
    print("OpenAI connectivity: SKIPPED (No Key)")
