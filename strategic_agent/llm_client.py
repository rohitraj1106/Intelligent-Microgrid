"""
strategic_agent/llm_client.py
=============================
Wrapper for the Google Gemini API using the new 'google-genai' library.
"""
import logging
import os
import json
import time
from typing import Optional, Dict, Any

from google import genai
from google.genai import types

from edge import config

logger = logging.getLogger("StrategicAgent.LLM")

class GeminiClient:
    """
    Communicates with Google Gemini to perform strategic energy reasoning.
    """
    def __init__(self, api_key: Optional[str] = None, model_id: str = config.GEMINI_MODEL):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
             logger.warning("No GEMINI_API_KEY found in environment. LLM calls will fail.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = model_id
        
        self.system_instruction = (
            "You are a Strategic Energy Agent for a residential microgrid node. "
            "Your goal is to optimize energy usage, minimize costs, and maintain battery health "
            "while coordinating with a P2P marketplace. "
            "You must respond ONLY with a valid JSON object. "
            "Valid actions: BUY, SELL, HOLD, CHARGE, DISCHARGE. "
            "Required fields: 'action', 'amount_kwh', 'price_per_kwh', 'target', 'reasoning'."
        )

    def infer(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """
        Sends a prompt to Gemini and returns the raw response text.
        """
        if not self.api_key:
            return '{"action": "HOLD", "reasoning": "API Key missing"}'

        try:
            # Using the new genai SDK pattern
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.2, # Low temperature for consistent JSON
                    response_mime_type="application/json" if schema else None,
                    response_schema=schema,
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini Inference Error: {e}")
            return f'{{"action": "HOLD", "reasoning": "LLM Inference failed: {str(e)[:100]}"}}'

    def infer_json(self, prompt: str) -> Dict[str, Any]:
        """
        Calls infer() and ensures the output is parsed as a dictionary.
        """
        raw = self.infer(prompt)
        try:
            # Clean up potential markdown formatting if not using strict JSON mode
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response as JSON: {raw}")
            return {"action": "HOLD", "reasoning": "JSON parsing error"}
