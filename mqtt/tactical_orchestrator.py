"""
# d:\Intelligent-Microgrid-main\Intelligent-Microgrid-main\mqtt\tactical_orchestrator.py

Implements a constrained Finite State Machine (FSM) for Home Node operations structurally.
Processes asynchronous LLM commands logically enforcing critical battery degradation safety bounds dynamically.
"""
import json
import asyncio
import paho.mqtt.client as mqtt
from datetime import datetime

try:
    import config
except ImportError:
    from . import config

# Definitive Finite State Machine operational baseline nodes globally modeled mapping behaviors implicitly
STATE_GRID_CONNECTED = "GRID_CONNECTED"
STATE_P2P_TRADING = "P2P_TRADING"
STATE_ISLANDED = "ISLANDED"
STATE_EMERGENCY = "EMERGENCY"

class TacticalOrchestrator:
    def __init__(self):
        # Initialization defaults establishing normative default system operational constraints
        self.state = STATE_GRID_CONNECTED
        self.battery_soc = 50.0  # Safe logical initial baseline assumed pre-telemetry synch dynamically
        self.client = mqtt.Client(f"Orchestrator_{config.HOME_ID}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.connect_broker()

    def connect_broker(self):
        """Safely bind internal MQTT abstractions onto generic operational domains structurally."""
        try:
            self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            config.logger.error(f"Orchestrator operational connection logical failure: {e}")

    def on_connect(self, client, userdata, flags, rc):
        """Explicit tracking verifying connection logically dynamically."""
        if rc == 0:
            config.logger.info("Tactical Orchestrator instantiated explicitly.")
            # Subscribe structurally tracking 4 specific data planes implicitly
            topics = [
                (config.TOPIC_TELEMETRY, 1),
                (config.TOPIC_LLM_COMMANDS, 1),
                (config.TOPIC_HANDSHAKE_REQUEST, 1),
                (config.TOPIC_HANDSHAKE_RESPONSE_ALL, 1)
            ]
            self.client.subscribe(topics)
            config.logger.info(f"Subscribed mapping streams conditionally: {topics}")
        else:
            config.logger.error(f"Orchestrator context connection rejected statically: {rc}")

    def on_message(self, client, userdata, msg):
        """Routes operational commands globally depending on topical explicit boundaries linearly."""
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except json.JSONDecodeError:
            config.logger.warning(f"Malformed JSON operational command received structurally {topic}")
            return

        # Simple dispatch table implementation inherently mapping routing boundaries conditionally
        if topic == config.TOPIC_TELEMETRY:
            self.handle_telemetry(payload)
        elif topic == config.TOPIC_LLM_COMMANDS:
            self.handle_llm_command(payload)
        elif topic == config.TOPIC_HANDSHAKE_REQUEST:
            self.handle_handshake_request(payload)
        elif topic == config.TOPIC_HANDSHAKE_RESPONSE_ALL:
            self.handle_handshake_response(payload)

    def handle_telemetry(self, data):
        """Updates internal SoC explicit logical condition triggering FSM transitions natively."""
        new_soc = data.get("battery_soc")
        if new_soc is not None:
            self.battery_soc = new_soc
            
            # Critical System Transition Logical Rule structurally executing EMERGENCY state unconditionally
            if self.battery_soc <= config.SAFETY_BUFFER_SOC:
                if self.state != STATE_EMERGENCY:
                    config.logger.warning(f"CRITICAL: Battery SoC context ({self.battery_soc}%). Entering STRICT EMERGENCY state.")
                    self.state = STATE_EMERGENCY
            # Implement logical hysteresis natively effectively avoiding immediate flapping implicitly
            elif self.state == STATE_EMERGENCY and self.battery_soc > config.SAFETY_BUFFER_SOC + 5.0:
                config.logger.info("Battery context stabilized contextually. Returning structurally into GRID_CONNECTED dynamically.")
                self.state = STATE_GRID_CONNECTED

    def handle_llm_command(self, cmd_data):
        """
        Interprets systematically external LLM JSON intent payload structured explicitly contextually:
        {"action": "BUY|SELL|CHARGE|IDLE", "target": "home_X", "amount": "1.5kWh", "min_price": "5"}
        """
        action = cmd_data.get("action")
        target = cmd_data.get("target")

        # RULE OVERRIDE: Prevent explicit physical battery damage dynamically natively.
        if self.battery_soc <= config.SAFETY_BUFFER_SOC and action == "SELL":
            config.logger.error(f"SAFETY OVERRIDE NATIVE: Sell structurally rejected locally. SoC {self.battery_soc}% below constraint {config.SAFETY_BUFFER_SOC}%")
            return

        # FSM Violation Tracking unconditionally explicitly
        if self.state == STATE_EMERGENCY and action in ["SELL", "ISLAND"]:
            config.logger.error("STATE VIOLATION: Resource depletion logically restricted statically due to FSM contextual EMERGENCY status.")
            return

        # Dispatch action directives globally resolving intent structurally 
        if action == "SELL":
            self.state = STATE_P2P_TRADING
            config.logger.info(f"Authorized explicit peer routing initiating sell operation towards {target}.")
            req_payload = json.dumps({
                "from": config.HOME_ID,
                "to": target,
                "amount": cmd_data.get("amount"),
                "price": cmd_data.get("min_price"),
                "timestamp": datetime.now().isoformat()
            })
            target_topic = f"microgrid/{target}/handshake/request"
            self.client.publish(target_topic, req_payload, qos=1)
        elif action == "BUY":
            # Initiates similar request structurally if natively implemented later contextually
            config.logger.info(f"Authorized explicit peer routing towards {target} representing BUY condition.")
        elif action == "CHARGE":
            config.logger.info("Orchestrating internal system structurally executing CHARGE prioritization sequence.")
        elif action == "IDLE":
            config.logger.info("Executing native systemic restriction reverting node contextual explicitly to default.")
            if self.state == STATE_P2P_TRADING:
                self.state = STATE_GRID_CONNECTED

    def handle_handshake_request(self, payload):
        """Resolves P2P structurally explicitly implicitly mapped requests programmatically natively."""
        from_peer = payload.get("from")
        # Logical simulated simplistic systemic response context explicitly authorizing request intrinsically natively
        config.logger.info(f"Received explicit systemic handshake native request internally originating {from_peer}.")
        
        reply = {
            "from": config.HOME_ID,
            "to": from_peer,
            "status": "ACCEPTED",
            "timestamp": datetime.now().isoformat()
        }
        self.client.publish(config.TOPIC_HANDSHAKE_RESPONSE_ALL, json.dumps(reply), qos=1)

    def handle_handshake_response(self, payload):
        """Closes loop structurally mapping P2P execution natively resolving context globally."""
        to_peer = payload.get("to")
        # Ensure message matches targeted native boundaries exclusively
        if to_peer == config.HOME_ID and payload.get("status") == "ACCEPTED":
            config.logger.info(f"Explicit sequence handshake effectively authorized globally by {payload.get('from')}. Processing structurally settling dynamically.")
            self.client.publish(config.TOPIC_MARKETPLACE_SETTLE, json.dumps({
                "seller": config.HOME_ID,
                "buyer": payload.get("from"),
                "status": "SETTLED"
            }), qos=1)
            # Revert inherently resolving default operations statically
            self.state = STATE_GRID_CONNECTED

    async def broadcast_safe_operating_window(self):
        """Looping abstraction publishing physical systemic operational thresholds logically implicitly."""
        while True:
            # Native assumed battery bound logically sized resolving 10kWh conditionally
            available_kwh = max(0, (self.battery_soc - config.SAFETY_BUFFER_SOC) / 100.0 * 10.0)
            
            payload = {
                "home_id": config.HOME_ID,
                "timestamp": datetime.now().isoformat(),
                "fsm_state": self.state,
                "safe_discharge_kwh": round(available_kwh, 2),
                "can_island": self.battery_soc > 50.0
            }
            self.client.publish(config.TOPIC_SAFE_WINDOW, json.dumps(payload), qos=0)
            config.logger.info(f"Executing explicit window publishing systematically generically: {payload}")
            
            # Constrained interval delay implicitly establishing a 60-second execution context bound natively
            await asyncio.sleep(60)

    def stop(self):
        """Cleanup abstractions gracefully."""
        self.client.loop_stop()
        self.client.disconnect()


async def main():
    """Execution abstraction natively running explicitly orchestrated logic natively."""
    orchestrator = TacticalOrchestrator()
    try:
        # Establish background systemic task intrinsically natively conditionally
        await orchestrator.broadcast_safe_operating_window()
    except asyncio.CancelledError:
        config.logger.info("Executing cancellation abstraction structurally naturally shutting logic down locally.")
    finally:
        orchestrator.stop()

if __name__ == "__main__":
    try:
        # Resolve inherently native logic intrinsically cleanly explicitly
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
