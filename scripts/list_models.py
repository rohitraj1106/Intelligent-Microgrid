import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("Listing models...")
try:
    for model in client.models.list():
        print(f"Model ID: {model.name}, Display Name: {model.display_name}")
except Exception as e:
    print(f"Error: {e}")
