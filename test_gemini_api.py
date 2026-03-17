import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_id = "gemini-3.1-flash-lite-preview"

print(f"Testing with Key: {api_key[:5]}...{api_key[-5:]}")
print(f"Model: {model_id}")

client = genai.Client(api_key=api_key)
try:
    response = client.models.generate_content(
        model=model_id,
        contents="Say 'Hello World'"
    )
    print("SUCCESS:", response.text)
except Exception as e:
    print("FAILED:", str(e))
