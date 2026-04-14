"""
strategic_agent/llm_client.py
=============================
Wrapper for the Google Gemini API using DIRECT REST calls via httpx.

The google-genai SDK v1.67 has a confirmed timeout bug where it silently
ignores the configured HttpOptions.timeout for certain models (including
gemma-4-26b-a4b-it). This module bypasses the SDK entirely and uses raw
httpx.post() calls which are proven to work reliably.

THREAD SAFETY: Uses a shared pooled httpx.Client. httpx clients support
concurrent access from multiple threads.
"""
import logging
import os
import json
import time
import random
from typing import Optional, Dict, Any

import httpx

from edge import config

logger = logging.getLogger("StrategicAgent.LLM")

# Base URL for the Gemini REST API
_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    """
    Communicates with Google Gemini to perform strategic energy reasoning.
    Uses direct REST calls instead of the google-genai SDK to avoid timeout bugs.
    Thread-safe: uses a shared pooled httpx connection.
    """
    def __init__(self, api_key: Optional[str] = None, model_id: str = config.GEMINI_MODEL):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
             logger.warning("No GEMINI_API_KEY found in environment. LLM calls will fail.")

        self.request_timeout_sec = config.LLM_REQUEST_TIMEOUT_SEC
        self.max_retries = max(1, config.LLM_MAX_RETRIES)
        self.initial_backoff_sec = max(0.25, config.LLM_INITIAL_BACKOFF_SEC)
        self.max_output_tokens = max(64, config.LLM_MAX_OUTPUT_TOKENS)
        self.model_id = model_id
        self._url = f"{_API_BASE}/models/{self.model_id}:generateContent?key={self.api_key}"
        self._closed = False

        # Keep connect timeout strict, but allow reads to consume the full total budget.
        # Gemma responses can stream late; a short read timeout causes premature failures.
        connect_timeout = min(15.0, max(5.0, self.request_timeout_sec * 0.15))
        read_timeout = float(self.request_timeout_sec)
        self._timeout = httpx.Timeout(
            timeout=self.request_timeout_sec,
            connect=connect_timeout,
            read=read_timeout,
            write=10.0,
            pool=10.0,
        )
        self._client = httpx.Client(
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
            http2=False,
        )

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
            "You are a Strategic Energy Agent for a residential microgrid. "
            "Optimize energy costs and battery health. "
            "Always output ONLY valid JSON. Follow the exact format requested in the prompt."
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

    def _build_request_body(self, prompt: str, json_mode: bool = False) -> Dict:
        """Builds the REST API request body."""
        body: Dict[str, Any] = {
            "system_instruction": {
                "parts": [{"text": self.system_instruction}]
            },
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.35,
                "candidateCount": 1,
                "maxOutputTokens": self.max_output_tokens,
            }
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        return body

    def infer(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """
        Sends a prompt to Gemini via direct REST API and returns the raw response text.
        THREAD-SAFE: Uses a shared pooled httpx.Client.
        Includes a retry loop for network-level timeouts.
        """
        if not self.api_key:
            return self._failure_json("API_KEY_MISSING")
        if self._closed:
            return self._failure_json("CLIENT_CLOSED")

        backoff = self.initial_backoff_sec
        body = self._build_request_body(prompt, json_mode=(schema is not None))
        
        for attempt in range(self.max_retries):
            started = time.monotonic()
            try:
                response = self._client.post(self._url, json=body)
                response.raise_for_status()
                
                data = response.json()
                
                # Extract text from API response
                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError(f"Gemini returned no candidates: {data}")
                
                parts = candidates[0].get("content", {}).get("parts", [])
                # Filter out "thought" parts (thinking model internal reasoning)
                text_parts = [p["text"] for p in parts if "text" in p and not p.get("thought")]
                
                if not text_parts:
                    # Fallback: use all text parts including thoughts
                    text_parts = [p["text"] for p in parts if "text" in p]
                
                text = "\n".join(text_parts).strip()
                if not text:
                    raise ValueError("Gemini returned empty response text")

                elapsed = time.monotonic() - started
                logger.info(f"Gemini responded successfully ({len(text)} chars, {elapsed:.2f}s)")
                return text

            except httpx.ConnectError as e:
                err_kind = "CONNECT_ERROR"
                err_str = str(e).replace("\n", " ")
                elapsed = time.monotonic() - started
                sleep_for = backoff * random.uniform(0.8, 1.2)
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Gemini attempt {attempt + 1}/{self.max_retries} failed "
                        f"({err_kind} after {elapsed:.2f}s: {err_str[:120]}). Retrying in {sleep_for:.1f}s..."
                    )
                    time.sleep(sleep_for)
                    backoff = min(backoff * 2, 10.0)
                else:
                    logger.error(
                        f"Gemini inference failed after {self.max_retries} attempts "
                        f"(timeout_sec={self.request_timeout_sec}): {err_kind} {err_str[:200]}"
                    )
                    return self._failure_json(err_kind)

            except (httpx.TimeoutException, TimeoutError) as e:
                err_kind = "TIMEOUT"
                err_str = str(e).replace("\n", " ")
                elapsed = time.monotonic() - started
                sleep_for = backoff * random.uniform(0.8, 1.2)
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Gemini attempt {attempt + 1}/{self.max_retries} failed "
                        f"({err_kind} after {elapsed:.2f}s: {err_str[:120]}). Retrying in {sleep_for:.1f}s..."
                    )
                    time.sleep(sleep_for)
                    backoff = min(backoff * 2, 10.0)
                else:
                    logger.error(
                        f"Gemini inference failed after {self.max_retries} attempts "
                        f"(timeout_sec={self.request_timeout_sec}): {err_kind} {err_str[:200]}"
                    )
                    return self._failure_json(err_kind)

            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else "unknown"
                err_kind = f"HTTP_{status}"
                err_str = str(e).replace("\n", " ")
                elapsed = time.monotonic() - started
                sleep_for = backoff * random.uniform(0.8, 1.2)
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Gemini attempt {attempt + 1}/{self.max_retries} failed "
                        f"({err_kind} after {elapsed:.2f}s: {err_str[:120]}). Retrying in {sleep_for:.1f}s..."
                    )
                    time.sleep(sleep_for)
                    backoff = min(backoff * 2, 10.0)
                else:
                    logger.error(
                        f"Gemini inference failed after {self.max_retries} attempts "
                        f"(timeout_sec={self.request_timeout_sec}): {err_kind} {err_str[:200]}"
                    )
                    return self._failure_json(err_kind)

            except Exception as e:
                err_kind = "TIMEOUT" if self._is_timeout_error(e) else "INFERENCE_ERROR"
                err_str = str(e).replace("\n", " ")
                elapsed = time.monotonic() - started
                sleep_for = backoff * random.uniform(0.8, 1.2)
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Gemini attempt {attempt + 1}/{self.max_retries} failed "
                        f"({err_kind} after {elapsed:.2f}s: {err_str[:120]}). Retrying in {sleep_for:.1f}s..."
                    )
                    time.sleep(sleep_for)
                    backoff = min(backoff * 2, 10.0)
                else:
                    logger.error(
                        f"Gemini inference failed after {self.max_retries} attempts "
                        f"(timeout_sec={self.request_timeout_sec}): {err_kind} {err_str[:200]}"
                    )
                    return self._failure_json(err_kind)

        return self._failure_json("INFERENCE_LOOP_EXHAUSTED")

    def _normalize_one(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single decision dictionary."""
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

    def _normalize_response(self, data: Any) -> Any:
        """Rename any aliased field names to the canonical versions. Handles lists and dicts."""
        if isinstance(data, list):
            return [self._normalize_one(item) for item in data if isinstance(item, dict)]
        
        if isinstance(data, dict):
            # Check if it's a map of node_id -> decision (batch format)
            first_val = next(iter(data.values()), None) if data else None
            if isinstance(first_val, dict) and "action" not in data:
                # It's a {node_id: {action: ...}} map
                result = {}
                for k, v in data.items():
                    if isinstance(v, dict):
                        result[k] = self._normalize_one(v)
                return result
            # Single decision dict
            return self._normalize_one(data)
            
        return data

    def infer_json(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Any:
        """
        Calls infer() and ensures the output is parsed with canonical field names.
        Can return a dict, list, or nested dict depending on LLM output format.
        """
        raw = self.infer(prompt, schema=schema)
        try:
            # Clean up potential markdown formatting if not using strict JSON mode
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            parsed = json.loads(cleaned.strip())
            return self._normalize_response(parsed)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response as JSON: {raw[:300]}")
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

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._client.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
