"""
test/test_strategic_agent.py
============================
Unit tests for the Strategic LLM Agent.
"""
import pytest
from unittest.mock import patch
import json
import httpx

from strategic_agent.prompt_builder import PromptBuilder
from strategic_agent.command_parser import CommandParser, AgentCommand
from strategic_agent.llm_client import GeminiClient
from strategic_agent.negotiation import MarketplaceClient

# ---------------------------------------------------------------------------
# Prompt Builder Tests
# ---------------------------------------------------------------------------
def test_prompt_builder_contains_key_sections():
    pb = PromptBuilder()
    prompt = pb.build(
        node_id="test_node",
        node_status={"current_soc_pct": 50.0, "avg_load_kw": 1.0, "avg_solar_kw": 2.0},
        safe_window={"state": "GRID_CONNECTED", "available_discharge_kwh": 5.0},
        market_snapshot={"best_buy_price": 7.0, "best_sell_price": 4.0},
        load_forecast=[1.0]*24,
        solar_forecast=[2.0]*24,
        grid_prices={"buy": 8.5, "sell": 3.0}
    )
    
    assert "### CURRENT STATE (Node: test_node)" in prompt
    assert "### SAFE OPERATING WINDOW" in prompt
    assert "### MARKET CONDITIONS" in prompt
    assert "### 24-HOUR FORECASTS" in prompt
    assert "### TASK" in prompt

# ---------------------------------------------------------------------------
# Command Parser Tests
# ---------------------------------------------------------------------------
def test_command_parser_valid_json():
    cp = CommandParser()
    raw = {
        "action": "BUY",
        "amount_kwh": 2.5,
        "price_per_kwh": 6.5,
        "target": "peer_01",
        "reasoning": "Standard purchase"
    }
    cmd = cp.parse(raw)
    assert cmd.action == "BUY"
    assert cmd.amount_kwh == 2.5
    assert cmd.price_per_kwh == 6.5
    assert cmd.target == "peer_01"

def test_command_parser_fallback_on_invalid_action():
    cp = CommandParser()
    raw = {"action": "EXPLODE", "reasoning": "Invalid action test"}
    cmd = cp.parse(raw)
    assert cmd.action == "HOLD"
    assert "Invalid action" in cmd.reasoning

def test_command_parser_missing_target_on_trade():
    cp = CommandParser()
    raw = {"action": "SELL", "amount_kwh": 1.0, "price_per_kwh": 5.0} # Missing target
    cmd = cp.parse(raw)
    assert cmd.action == "HOLD"
    assert "missing target" in cmd.reasoning

def test_command_parser_includes_snapshot_soc():
    cp = CommandParser()
    cmd = AgentCommand("BUY", 2.0, 6.0, "peer_01", "Testing", snapshot_soc=45.2)
    
    # 1. Via AgentCommand attribute
    js = cp.to_orchestrator_json(cmd)
    data = json.loads(js)
    assert data["snapshot_soc"] == 45.2
    
    # 2. Via explicit override
    js2 = cp.to_orchestrator_json(cmd, snapshot_soc=48.0)
    data2 = json.loads(js2)
    assert data2["snapshot_soc"] == 48.0

# ---------------------------------------------------------------------------
# Integration/Client Mocks
# ---------------------------------------------------------------------------
@patch("requests.post")
def test_marketplace_client_place_order(mock_post):
    mock_post.return_value.status_code = 201
    mock_post.return_value.json.return_value = {"matched": True, "order_id": 123}
    
    client = MarketplaceClient("http://mock-market")
    res = client.place_order("node_1", "BUY", 1.5, 7.5)
    
    assert res["order_id"] == 123
    assert mock_post.called

def test_llm_client_infer_json(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"action": "SELL", "amount_kwh": 0.5, "price_per_kwh": 4.0, "target": "peer_B", "reasoning": "Surplus detected"}'
                                }
                            ]
                        }
                    }
                ]
            }

    client = GeminiClient(api_key="fake-key")
    monkeypatch.setattr(client._client, "post", lambda *args, **kwargs: MockResponse())
    res = client.infer_json("Give me a sell order")

    assert res["action"] == "SELL"
    assert res["amount_kwh"] == 0.5
    assert res["target"] == "peer_B"
    client.close()

def test_llm_client_infer_json_from_markdown_fence(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '```json\n[{"node_id":"delhi_00","action":"HOLD","amount_kwh":0.0,"price_per_kwh":0.0,"target":"none","reasoning":"Stable"}]\n```'
                                }
                            ]
                        }
                    }
                ]
            }

    client = GeminiClient(api_key="fake-key")
    monkeypatch.setattr(client._client, "post", lambda *args, **kwargs: MockResponse())
    res = client.infer_json("Give me a batch decision")

    assert isinstance(res, list)
    assert res[0]["action"] == "HOLD"
    assert res[0]["target"] == "none"
    client.close()

def test_llm_client_infer_json_from_mixed_text(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": 'Decision summary:\n[{"action":"BUY","amount_kw":0.5,"price":6.2,"target":"P2P","reasoning":"low SoC"}]\nEnd.'
                                }
                            ]
                        }
                    }
                ]
            }

    client = GeminiClient(api_key="fake-key")
    monkeypatch.setattr(client._client, "post", lambda *args, **kwargs: MockResponse())
    res = client.infer_json("Give me a batch decision")

    assert isinstance(res, list)
    assert res[0]["action"] == "BUY"
    assert res[0]["amount_kwh"] == 0.5
    assert res[0]["price_per_kwh"] == 6.2
    client.close()

def test_llm_client_marks_timeout_failure(monkeypatch):
    client = GeminiClient(api_key="fake-key")
    client.max_retries = 1

    def _raise_timeout(*args, **kwargs):
        raise httpx.ReadTimeout("request timed out")

    monkeypatch.setattr(client._client, "post", _raise_timeout)
    res = client.infer_json("trigger timeout")

    assert res["action"] == "HOLD"
    assert res["reasoning"] == "LLM_TIMEOUT"
    assert client.is_failure_response(res) is True
    client.close()

def test_llm_client_initializes_with_http_timeout():
    client = GeminiClient(api_key="fake-key")

    assert client._timeout is not None
    assert client._timeout.connect is not None
    assert client._timeout.read is not None
    client.close()
