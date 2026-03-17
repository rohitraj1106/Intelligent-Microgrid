"""
test/test_strategic_agent.py
============================
Unit tests for the Strategic LLM Agent.
"""
import pytest
from unittest.mock import MagicMock, patch
import json

from strategic_agent.prompt_builder import PromptBuilder
from strategic_agent.command_parser import CommandParser
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

@patch("strategic_agent.llm_client.genai.Client")
def test_llm_client_infer_json(mock_genai_client):
    # Mock the response object from Gemini
    mock_response = MagicMock()
    mock_response.text = '{"action": "SELL", "amount_kwh": 0.5, "price_per_kwh": 4.0, "target": "peer_B", "reasoning": "Surplus detected"}'
    
    mock_genai_instance = mock_genai_client.return_value
    mock_genai_instance.models.generate_content.return_value = mock_response
    
    client = GeminiClient(api_key="fake-key")
    res = client.infer_json("Give me a sell order")
    
    assert res["action"] == "SELL"
    assert res["amount_kwh"] == 0.5
    assert res["target"] == "peer_B"
