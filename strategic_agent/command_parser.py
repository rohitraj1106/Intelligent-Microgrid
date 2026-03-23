"""
strategic_agent/command_parser.py
==========================
Parses and validates JSON commands from the LLM.
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger("StrategicAgent.Parser")

@dataclass
class AgentCommand:
    action: str
    amount_kwh: float
    price_per_kwh: float
    target: Optional[str]
    reasoning: str
    snapshot_soc: Optional[float] = None

class CommandParser:
    """
    Ensures LLM output follows the expected protocol and safety limits.
    """
    VALID_ACTIONS = {"BUY", "SELL", "HOLD", "CHARGE", "DISCHARGE"}

    def parse(self, data: Dict[str, Any]) -> AgentCommand:
        """
        Converts raw dictionary from LLM into a validated AgentCommand object.
        """
        try:
            action = str(data.get("action", "HOLD")).upper()
            if action not in self.VALID_ACTIONS:
                logger.warning(f"Invalid action '{action}' reset to HOLD")
                action = "HOLD"

            # Parse numeric values with defaults/clamping
            amount = float(data.get("amount_kwh", 0.0))
            amount = max(0.0, min(amount, 50.0)) # Hard cap at 50kWh for safety
            
            price = float(data.get("price_per_kwh", 0.0))
            price = max(0.0, min(price, 20.0)) # Hard cap at ₹20/kWh

            target = data.get("target")
            reasoning = str(data.get("reasoning", "No reason provided."))
            
            if action in ["BUY", "SELL"] and not target:
                reasoning = f"Trade action {action} missing target; defaulting to HOLD"
                logger.warning(reasoning)
                action = "HOLD"

            return AgentCommand(
                action=action,
                amount_kwh=round(amount, 3),
                price_per_kwh=round(price, 2),
                target=target,
                reasoning=reasoning
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Command parsing error: {e}")
            return AgentCommand("HOLD", 0.0, 0.0, None, f"Parsing error: {e}")

    def to_orchestrator_json(self, cmd: AgentCommand, snapshot_soc: Optional[float] = None) -> str:
        """
        Converts AgentCommand to the JSON format expected by orchestrator/orchestrator.py.
        """
        return json.dumps({
            "action": cmd.action,
            "amount_kwh": cmd.amount_kwh,
            "price_per_kwh": cmd.price_per_kwh,
            "target": cmd.target,
            "reasoning": cmd.reasoning,
            "snapshot_soc": snapshot_soc or cmd.snapshot_soc
        })
