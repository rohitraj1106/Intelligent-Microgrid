"""
Simple script to verify Google Gemini API connectivity.
Reads GEMINI_API_KEY from .env file and performs a basic inference test.
"""
import os
import sys
from dotenv import load_dotenv

# Ensure we are in the project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategic_agent.llm_client import GeminiClient

def test_connectivity():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("\n[❌] ERROR: No GEMINI_API_KEY found in your .env file.")
        print("Please ensure your .env file contains: GEMINI_API_KEY=your_actual_key\n")
        return False

    print("\n[⏳] Testing Gemini API connectivity...")
    
    try:
        # Use the api_key variable loaded from .env
        client = GeminiClient(api_key=api_key)
        
        # Simple test prompt
        test_prompt = "Say 'Hello Microgrid! API is working.' and provide a short energy tip."
        
        # Use simple string inference first
        raw_response = client.infer(test_prompt)
        
        if "Hello Microgrid!" in raw_response:
             print("\n[✅] SUCCESS! Gemini API is connected and responding correctly.")
             print(f"--- Response ---\n{raw_response.strip()}\n----------------")
             return True
        else:
             print("\n[⚠️] WARNING: Connected, but response was unexpected.")
             print(f"--- Response ---\n{raw_response.strip()}\n----------------")
             return True

    except Exception as e:
        print(f"\n[❌] ERROR: Connectivity test failed with exception:")
        print(f"    {str(e)}")
        print("\nCheck your internet connection and API key validity.")
        return False

if __name__ == "__main__":
    if test_connectivity():
        sys.exit(0)
    else:
        sys.exit(1)
