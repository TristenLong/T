import os
from google import genai
from google.genai import types
import server_tools

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    from dotenv import load_dotenv
    load_dotenv(os.path.join("GOD_HAND_CORE", ".env"))
    api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

chat = client.chats.create(
    model="gemini-3.6-flash",
    config=types.GenerateContentConfig(
        tools=server_tools.AVAILABLE_TOOLS,
        temperature=0.7
    )
)

print("Sending message...")
response = chat.send_message("Please use the execute_python_sandbox tool to print 'Hello World'")
print("Response text:", response.text)
if response.function_calls:
    print("Function calls:", response.function_calls)
