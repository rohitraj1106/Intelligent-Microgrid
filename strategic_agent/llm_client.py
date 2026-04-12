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

        self.request_timeout_sec = config.LLM_REQUEST_TIMEOUT_SEC
        self.max_retries = max(1, config.LLM_MAX_RETRIES)
        self.initial_backoff_sec = max(0.25, config.LLM_INITIAL_BACKOFF_SEC)
        self.max_output_tokens = max(64, config.LLM_MAX_OUTPUT_TOKENS)
        
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=self.request_timeout_sec)
        )
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

    _FAILURE_PREFIX = "LLM_"

    def _build_config(self, schema: Optional[Dict[str, Any]]) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.35,
            candidate_count=1,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json" if schema else None,
            response_schema=schema,
            thinking_config=types.ThinkingConfig(include_thoughts=False),
            http_options=types.HttpOptions(timeout=self.request_timeout_sec),
        )

    @staticmethod
    def _is_timeout_error(err: Exception) -> bool:
        txt = str(err).lower()
        return (
            "timeout" in txt
            or "timed out" in txt
            or "readtimeout" in txt
            or "connecttimeout" in txt
            or "winerror 10060" in txt
        )

    def _failure_json(self, reason: str) -> str:
        return json.dumps(
            {
                "action": "HOLD",
                "amount_kwh": 0.0,
                "price_per_kwh": 0.0,
                "target": "battery",
                "reasoning": f"{self._FAILURE_PREFIX}{reason}",
            }
        )

    def infer(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """
        Sends a prompt to Gemini and returns the raw response text.
        Includes a retry loop for network-level timeouts (WinError 10060).
        """
        if not self.api_key:
            return self._failure_json("API_KEY_MISSING")

        backoff = self.initial_backoff_sec
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=self._build_config(schema)
                )
                text = (response.text or "").strip()
                if not text:
                    raise ValueError("Gemini returned empty response text")
                return text
            except Exception as e:
                err_kind = "TIMEOUT" if self._is_timeout_error(e) else "INFERENCE_ERROR"
                err_str = str(e).replace("\n", " ")
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Gemini attempt {attempt + 1}/{self.max_retries} failed ({err_kind}: {err_str[:120]}). "
                        f"Retrying in {backoff:.1f}s..."
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 10.0)
                else:
                    logger.error(
                        f"Gemini inference failed after {self.max_retries} attempts "
                        f"(timeout_sec={self.request_timeout_sec}): {err_kind} {err_str[:200]}"
                    )
                    return self._failure_json(err_kind)

        return self._failure_json("INFERENCE_LOOP_EXHAUSTED")

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
            return {
                "action": "HOLD",
                "amount_kwh": 0.0,
                "price_per_kwh": 0.0,
                "target": "battery",
                "reasoning": f"{self._FAILURE_PREFIX}JSON_PARSE_ERROR"
            }

    @classmethod
    def is_failure_response(cls, payload: Dict[str, Any]) -> bool:
        reasoning = str(payload.get("reasoning", ""))
        return reasoning.startswith(cls._FAILURE_PREFIX)
