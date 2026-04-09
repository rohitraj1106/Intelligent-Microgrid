"""
strategic_agent/batch_builder.py
===============================
Synthesizes high-density batch prompts for the Strategic LLM Agent.
Enables reasoning for 5 nodes in a single API call for efficiency.
"""
from typing import Dict, Any, List
from datetime import datetime

class BatchPromptBuilder:
    """
    Transforms system state for multiple nodes into a single structured reasoning prompt.
    """
    def build(self, 
              city_name: str,
              nodes_status: Dict[str, Dict[str, Any]],
              market_snapshot: Dict[str, Any],
              grid_prices: Dict[str, float],
              cycle_id: int = 0) -> str:
        
        # 1. Header & Context
        first_as_of = next(iter(nodes_status.values())).get('as_of', '') if nodes_status else ''
        time_label = "MIDDAY_SOLAR_SURPLUS"
        hour = 12
        try:
            clean_ts = first_as_of.replace(' ', 'T').split('.')[0]
            dt = datetime.fromisoformat(clean_ts)
            hour = dt.hour
            if 6 <= hour < 10: time_label = "MORNING_SPIKE"
            elif 10 <= hour < 16: time_label = "MIDDAY_SOLAR_SURPLUS"
            elif 16 <= hour < 19: time_label = "AFTERNOON_TRANSITION"
            elif 19 <= hour < 23: time_label = "EVENING_PEAK_DRAIN"
            else: time_label = "NIGHT_RECOVERY"
        except:
            pass

        header = (
            f"### BATCH REASONING CYCLE: {cycle_id} | CITY: {city_name}\n"
            f"### SYSTEM TIME: {first_as_of} | CONTEXT: {time_label}\n\n"
        )

        # 2. Status Table
        table = "| Node ID | SoC % | Load kW | Solar kW | 4H Outlook (kWh) | Intent | Context |\n"
        table += "|---------|-------|---------|----------|------------------|--------|---------|\n"
        
        for node_id, status in nodes_status.items():
            soc = status.get('current_soc_pct', 0.0)
            load = status.get('avg_load_kw', 0.0)
            solar = status.get('avg_solar_kw', 0.0)
            net = status.get('net_energy_kw', 0.0)
            outlook_4h = status.get('outlook_4h', 0.0)
            intent = status.get('intent', 'BALANCED')
            
            # Contextual label
            ctx = "Stable"
            if outlook_4h < -1.5: ctx = "Deficit approaching"
            elif outlook_4h > 1.5: ctx = "Surplus predicted"
            
            table += f"| {node_id} | {soc:.1f}% | {load:.2f} | {solar:.2f} | {outlook_4h:+.2f} | {intent} | {ctx} |\n"

        # 3. Market context
        market = (
            f"\n### MARKET CONDITIONS\n"
            f"- Best P2P BUY: ₹{market_snapshot.get('best_buy_price', 'N/A')}\n"
            f"- Best P2P SELL: ₹{market_snapshot.get('best_sell_price', 'N/A')}\n"
            f"- Grid BUY: ₹{grid_prices.get('buy', 8.50):.2f} | Grid SELL: ₹{grid_prices.get('sell', 3.00):.2f}\n"
        )

        # 4. Instructions
        instructions = (
            "\n### STRATEGIC TASK (Season: March-April Pre-Monsoon, India)\n"
            "Analyze these 5 nodes as a portfolio manager. Use the 4H Outlook to prevent battery depletion at night.\n"
            "1. **BUY** if SoC < 35% OR (SoC < 60% AND Outlook is highly negative). **LIMIT**: max 0.5 kWh.\n"
            "2. **SELL** ONLY if SoC > 80% AND 4H Outlook is Positive (> 0.5 kWh). If outlook is negative, HOLD for personal use.\n"
            "3. **HOLD** is the default state to preserve battery cycles. Do not trade for tiny margins.\n"
            "4. **PRICING**: If selling, aim to undercut Grid BUY price. If buying, try to beat Best P2P Sell.\n"
            "\n**REQUIRED FORMAT**: Return a JSON array of 5 objects (one per node, same order).\n"
            "Format: {node_id, action (BUY/SELL/HOLD), amount_kwh, price_per_kwh, target ('grid' or node_id), reasoning}.\n"
            "\nOutput ONLY raw JSON code block."
        )

        return header + table + market + instructions
