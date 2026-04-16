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

        # 2. Status Blocks (More explicit than markdown tables for LLM consistency)
        table = "### CURRENT NODE STATES\n"
        for node_id, status in nodes_status.items():
            soc = status.get('current_soc_pct', 0.0)
            load = status.get('avg_load_kw', 0.0)
            solar = status.get('avg_solar_kw', 0.0)
            outlook_4h = status.get('outlook_4h', 0.0)
            intent = status.get('intent', 'BALANCED')
            
            table += (
                f"--- NODE: {node_id} ---\n"
                f"  Current SoC: {soc:.1f}%\n"
                f"  Avg Load: {load:.2f} kW | Avg Solar: {solar:.2f} kW\n"
                f"  4H Outlook: {outlook_4h:+.2f} kWh | Goal: {intent}\n\n"
            )

        # 3. Market context
        market = (
            f"\n### MARKET CONDITIONS\n"
            f"- Best P2P BUY: ₹{market_snapshot.get('best_buy_price', 'N/A')}\n"
            f"- Best P2P SELL: ₹{market_snapshot.get('best_sell_price', 'N/A')}\n"
            f"- Grid BUY: ₹{grid_prices.get('buy', 8.50):.2f} | Grid SELL: ₹{grid_prices.get('sell', 3.00):.2f}\n"
        )

        # 4. Instructions
        instructions = (
            "Analyze these 5 nodes as a portfolio manager. Decisions MUST be based strictly on the provided SoC values and outlooks. NO HALLUCERNATIONS.\n"
            "STRICT DECISION LOGIC:\n"
            "1. **BUY**: MANDATORY if SoC <= 35%. STRONGLY RECOMMENDED if SoC < 60% AND 4H Outlook < -1.0.\n"
            "2. **SELL**: MANDATORY if SoC >= 65%. Prioritize P2P community selling to maximize profit.\n"
            "3. **HOLD**: Only allowed if SoC is between 36% and 64% AND outlook is stable (> -1.0).\n"
            "4. **PRICING**: If selling, undercut Grid BUY price slightly. If buying, try to match or beat Best P2P Sell.\n"
            "\n**REQUIRED FORMAT**:\n"
            "- Return EXACTLY 5 JSON objects in one JSON array.\n"
            "- Double-check that 'node_id' and 'reasoning' match the correct SoC from the blocks above.\n"
            "- Reasoning must be very short and reflect the ACTUAL data shown.\n"
            "Result Format: [{\"node_id\": \"...\", \"action\": \"BUY|SELL|HOLD\", \"amount_kwh\": 0.1, \"price_per_kwh\": 5.0, \"target\": \"grid|peer_id\", \"reasoning\": \"...\"}, ...]"
        )

        return header + table + market + instructions

    def build_single(
        self,
        city_name: str,
        node_id: str,
        node_status: Dict[str, Any],
        market_snapshot: Dict[str, Any],
        grid_prices: Dict[str, float],
        cycle_id: int = 0,
    ) -> str:
        """Build a focused prompt for one node and require one JSON object output."""
        as_of = node_status.get('as_of', '')
        soc = float(node_status.get('current_soc_pct', 0.0) or 0.0)
        load = float(node_status.get('avg_load_kw', 0.0) or 0.0)
        solar = float(node_status.get('avg_solar_kw', 0.0) or 0.0)
        net = float(node_status.get('net_energy_kw', 0.0) or 0.0)
        outlook_4h = float(node_status.get('outlook_4h', 0.0) or 0.0)
        intent = str(node_status.get('intent', 'BALANCED'))

        header = (
            f"### NODE REASONING CYCLE: {cycle_id} | CITY: {city_name} | NODE: {node_id}\n"
            f"### SYSTEM TIME: {as_of}\n\n"
        )

        node_state = (
            "### NODE STATE\n"
            f"- SoC: {soc:.1f}%\n"
            f"- Avg Load (1h): {load:.2f} kW\n"
            f"- Avg Solar (1h): {solar:.2f} kW\n"
            f"- Net Energy: {net:+.2f} kW\n"
            f"- 4H Outlook: {outlook_4h:+.2f} kWh\n"
            f"- Prior Intent: {intent}\n"
        )

        market = (
            "\n### MARKET CONDITIONS\n"
            f"- Best P2P BUY: INR {market_snapshot.get('best_buy_price', 'N/A')}\n"
            f"- Best P2P SELL: INR {market_snapshot.get('best_sell_price', 'N/A')}\n"
            f"- Grid BUY: INR {grid_prices.get('buy', 8.50):.2f}\n"
            f"- Grid SELL: INR {grid_prices.get('sell', 3.00):.2f}\n"
        )

        instructions = (
            "\n### STRATEGIC TASK\n"
            "Return ONE decision for this node only.\n"
            "1. BUY if SoC < 35% OR (SoC < 60% and outlook_4h is strongly negative).\n"
            "2. SELL if SoC > 65%. Prioritize community trade over grid export.\n"
            "3. HOLD is default when SoC is in stable range (35-65%).\n"
            "4. amount_kwh must be between 0.0 and 0.5.\n"
            "5. target must be 'grid', 'P2P', or a peer node id.\n"
            "\nREQUIRED FORMAT: Return exactly one raw JSON object with keys:\n"
            "{node_id, action, amount_kwh, price_per_kwh, target, reasoning}.\n"
            "Do not include markdown, code fences, or extra text.\n"
        )

        return header + node_state + market + instructions
