"""
strategic_agent/prompt_builder.py
==========================
Synthesizes the natural language prompt for the Strategic LLM Agent.
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

class PromptBuilder:
    """
    Transforms system state, market data, and forecasts into a reasoning prompt.
    """
    def build(self, 
              node_id: str,
              node_status: Dict[str, Any],
              safe_window: Dict[str, Any],
              market_snapshot: Dict[str, Any],
              load_forecast: List[float],
              solar_forecast: List[float],
              grid_prices: Dict[str, float],
              trade_history: List[Dict[str, Any]] = None) -> str:
        
        # Summary of current telemetry
        current_state = (
            f"### CURRENT STATE (Node: {node_id})\n"
            f"- Timestamp: {node_status.get('as_of', datetime.now().isoformat())}\n"
            f"- Battery SoC: {node_status.get('current_soc_pct', 0.0):.1f}%\n"
            f"- Current Load: {node_status.get('avg_load_kw', 0.0):.3f} kW\n"
            f"- Current Solar: {node_status.get('avg_solar_kw', 0.0):.3f} kW\n"
            f"- Net Energy: {node_status.get('net_energy_kw', 0.0):.3f} kW ({node_status.get('intent', 'BALANCED')})\n"
        )

        # Safety constraints from Orchestrator
        safety = (
            f"### SAFE OPERATING WINDOW\n"
            f"- FSM State: {safe_window.get('state', 'UNKNOWN')}\n"
            f"- Grid Status: {safe_window.get('grid_status', 'UNKNOWN')}\n"
            f"- Available Discharge: {safe_window.get('available_discharge_kwh', 0.0):.3f} kWh\n"
            f"- Available Charge: {safe_window.get('available_charge_kwh', 0.0):.3f} kWh\n"
            f"- Max BUY P2P Limit: {safe_window.get('max_buy_p2p_kw', 0.0):.2f} kW\n"
            f"- Max SELL P2P Limit: {safe_window.get('max_sell_p2p_kw', 0.0):.2f} kW\n"
            f"- Constraints: {', '.join(safe_window.get('constraints', [])) if safe_window.get('constraints') else 'NONE'}\n"
        )

        # Market conditions
        market = (
            f"### MARKET CONDITIONS\n"
            f"- Best BUY Order (Market): ₹{market_snapshot.get('best_buy_price', 'N/A')}/kWh\n"
            f"- Best SELL Order (Market): ₹{market_snapshot.get('best_sell_price', 'N/A')}/kWh\n"
            f"- Grid BUY Price: ₹{grid_prices.get('buy', 8.50):.2f}/kWh\n"
            f"- Grid SELL Price (Net Metering): ₹{grid_prices.get('sell', 3.00):.2f}/kWh\n"
            f"- Market Activity: {len(market_snapshot.get('pending_buy_orders', []))} buys, "
            f"{len(market_snapshot.get('pending_sell_orders', []))} sells pending.\n"
        )

        # Forecast context (Summarized for LLM context window efficiency)
        # We group 24h into 4 blocks of 6 hours
        def summarize_forecast(f: List[float]) -> str:
            if not f: return "No forecast available."
            blocks = [sum(f[i:i+6])/6 for i in range(0, 24, 6)]
            return f"Next 24h average: {sum(f)/24:.2f}kW. (6h blocks: {', '.join([f'{b:.2f}' for b in blocks])})"

        forecasts = (
            f"### 24-HOUR FORECASTS\n"
            f"- Load Profile: {summarize_forecast(load_forecast)}\n"
            f"- Solar Profile: {summarize_forecast(solar_forecast)}\n"
        )

        # Historical context
        history = ""
        if trade_history:
            history = "### RECENT TRADE HISTORY\n"
            for t in trade_history[:5]:
                history += f"- {t['executed_at']}: {t['quantity_kwh']}kWh @ ₹{t['price_per_kwh']}/kWh\n"

        # The Call to Action
        instructions = (
            "\n### TASK\n"
            "Evaluate the current state and forecasts to decide the optimal action for the next 15 minutes. "
            "Prioritize: 1. System Safety (Battery health), 2. Cost Reduction (Arbitrage), 3. Grid Independence. "
            "You MUST output as a single JSON object with these fields:\n"
            "- action: 'BUY', 'SELL', 'HOLD', 'CHARGE', 'DISCHARGE'\n"
            "- amount_kwh: float (quantity to trade or battery command)\n"
            "- price_per_kwh: float (target price for P2P trading)\n"
            "- target: string (peer Node ID for P2P, or 'battery' for internal actions)\n"
            "- reasoning: string (brief logic for this decision)\n"
        )

        return current_state + safety + market + forecasts + history + instructions
