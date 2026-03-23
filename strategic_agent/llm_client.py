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
        
        self.response_schema = {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["BUY", "SELL", "HOLD", "CHARGE", "DISCHARGE"]},
                "amount_kwh": {"type": "NUMBER"},
                "price_per_kwh": {"type": "NUMBER"},
                "target": {"type": "STRING", "description": "battery, grid, or a peer node ID"},
                "reasoning": {"type": "STRING", "description": "Concise technical justification"}
            },
            "required": ["action", "amount_kwh", "price_per_kwh", "target", "reasoning"]
        }

        self.system_instruction = (
            "You are a Strategic Energy Agent for a residential microgrid node. "
            "Optimize energy costs and battery health. "
            "Output JSON with these EXACT field names: action, amount_kwh, price_per_kwh, target, reasoning."
        )

    # Field aliases Gemini sometimes uses — map them to canonical names
    _FIELD_ALIASES = {
        "amount":       "amount_kwh",
        "amount_kw":    "amount_kwh",
        "quantity":     "amount_kwh",
        "quantity_kwh": "amount_kwh",
        "price":        "price_per_kwh",
        "price_kwh":    "price_per_kwh",
        "price_inr":    "price_per_kwh",
    }

    def infer(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """
        Sends a prompt to Gemini and returns the raw response text.
        Includes a retry loop for network-level timeouts (WinError 10060).
        """
        if not self.api_key:
            return '{"action": "HOLD", "reasoning": "API Key missing"}'

        max_retries = 3
        backoff = 2
        
        for attempt in range(max_retries):
            try:
                # Using the new genai SDK pattern
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        temperature=0.4, # Moderate temperature for variety without breaking JSON
                        response_mime_type="application/json" if schema else None,
                        response_schema=schema,
                    )
                )
                return response.text
            except Exception as e:
                err_str = str(e)
                if attempt < max_retries - 1:
                    logger.warning(f"Gemini Attempt {attempt+1} failed ({err_str[:80]}). Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(f"Gemini Inference Error (Final Attempt): {e}")
                    # Return a JSON error so the dashboard can show the failure gracefully
                    return f'{{"action": "HOLD", "reasoning": "LLM Inference failed: {err_str[:120]}"}}'
        
        return '{"action": "HOLD", "reasoning": "Inference loop exhausted"}'

    def _normalize_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Rename any aliased field names to the canonical versions."""
        normalized = {}
        for key, value in data.items():
            canonical = self._FIELD_ALIASES.get(key, key)
            normalized[canonical] = value
        # Guarantee required fields exist with safe defaults
        normalized.setdefault("amount_kwh",    0.0)
        normalized.setdefault("price_per_kwh", 0.0)
        normalized.setdefault("target",        "grid")
        normalized.setdefault("reasoning",     "No reasoning provided.")
        return normalized

    def infer_json(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calls infer() and ensures the output is parsed as a dictionary
        with canonical field names.
        """
        raw = self.infer(prompt, schema=schema)
        try:
            # Clean up potential markdown formatting if not using strict JSON mode
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            parsed = json.loads(cleaned.strip())
            return self._normalize_response(parsed)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response as JSON: {raw}")
            return {"action": "HOLD", "amount_kwh": 0.0, "price_per_kwh": 0.0, "target": "grid", "reasoning": "JSON parsing error"}
