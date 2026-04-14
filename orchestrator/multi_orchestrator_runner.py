"""
orchestrator/multi_orchestrator_runner.py
=========================================
Tactical Performance Driver: Runs all 75 Orchestrators in a single process.
Uses a multiplexed MQTT subscription for extreme efficiency.
"""
import json
import logging
import signal
import sys
import os
import threading
from typing import Dict, Optional
import requests

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from edge import config
from edge.node import EdgeNode
from edge.models import TelemetryReading
from orchestrator.orchestrator import TacticalOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-24s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("MultiOrchestrator")

class MultiOrchestrator:
    def __init__(self, broker_host: str = config.MQTT_BROKER, broker_port: int = config.MQTT_PORT):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.is_running = False
        
        # 1. Initialize MQTT Multiplexed Client
        self._mqtt = mqtt.Client(client_id="MultiOrchestrator")
        self._mqtt.on_connect = self._on_connect
        self._mqtt.on_message = self._on_message
        self.gateway_url = os.getenv("API_GATEWAY_BASE_URL", "http://localhost:8100").rstrip("/")
        self.gateway_key = os.getenv("GATEWAY_WRITE_API_KEY", "demo-write-key")
        
        # 2. Warm up all 75 Orchestrators (Lazy Mode)
        self.orchestrators: Dict[str, TacticalOrchestrator] = {}
        self.active_city: Optional[str] = None
        self._started_cities = set()
        self._db_ready_nodes = set()
        logger.info("Instantiating 75 Tactical Orchestrators (Lazy Load Mode)...")
        for nid in config.NODE_CONFIGS:
             # Need an EdgeNode instance for the database it manages
             edge_node = EdgeNode(nid)
             # NOTE: we don't call start() here; we will handle ingestion via this shared client instead
             
             # Create orchestrator with SHARED MQTT client
             orch = TacticalOrchestrator(nid, edge_node)
             orch._client = self._mqtt # Override with multiplexed client
             self.orchestrators[nid] = orch

    def _post_state_snapshot(self, node_id: str, reading: TelemetryReading):
        """Push current node state to the frontend API gateway for UI-safe reads."""
        orch = self.orchestrators[node_id]
        city = node_id.split("_")[0]
        payload = {
            "node_id": node_id,
            "city": city,
            "timestamp": (
                reading.timestamp.isoformat()
                if hasattr(reading.timestamp, "isoformat")
                else str(reading.timestamp)
            ),
            "telemetry": {
                "soc_pct": reading.soc_pct,
                "voltage_v": reading.voltage_v,
                "power_solar_kw": reading.power_solar_kw,
                "power_load_kw": reading.power_load_kw,
                "battery_power_kw": reading.battery_power_kw,
                "grid_import_kw": reading.grid_import_kw,
                "grid_export_kw": reading.grid_export_kw,
            },
            "orchestrator": {
                "fsm_state": orch.fsm.state,
                "strategy_status": orch._last_verdict,
                "verdict": orch._last_verdict,
                "reason": getattr(orch, "_last_action", "NONE"),
            },
        }

        try:
            response = requests.post(
                f"{self.gateway_url}/api/internal/orchestrator/state",
                json=payload,
                headers={"X-API-Key": self.gateway_key},
                timeout=1.5,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Gateway state ingest failed for %s: %s %s",
                    node_id,
                    response.status_code,
                    response.text[:200],
                )
        except Exception as exc:
            logger.warning(f"Gateway state ingest skipped for {node_id}: {exc}")

    def _start_city_nodes(self, city: str):
        """Lazy loader for city-wide database initialisation."""
        if city in self._started_cities: return
        
        logger.info(f"LAZY START: Initializing DBs for {city}...")
        city_prefix = city.lower()
        for nid, orch in self.orchestrators.items():
            if nid.startswith(city_prefix):
                # Only init the DB, don't start a whole MQTT client per node!
                orch.edge_node._db.initialize()
        
        self._started_cities.add(city)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # Multi-Subscribe
            client.subscribe([
                ("microgrid/+/telemetry", 1),
                ("microgrid/+/llm_commands", 1),
                ("microgrid/+/control", 1),
                ("microgrid/+/handshake/request", 1),
                ("microgrid/+/handshake/response", 1),
                ("dashboard/active_city", 1)
            ])
            logger.info("Multiplexed subscription active for all 75 nodes + Dashboard.")
        else:
            logger.error(f"Multiplexed MQTT connect failed (rc={rc})")

    def _on_message(self, client, userdata, msg):
        """Route messages to the correct per-node orchestrator by ID."""
        if msg.topic == "dashboard/active_city":
            try:
                payload = json.loads(msg.payload.decode())
                new_city = payload.get("city")
                if new_city:
                    self.active_city = new_city.lower()
                    self._start_city_nodes(self.active_city)
                    logger.info(f"Orchestrator focused on ACTIVE CITY: {self.active_city}")
                else:
                    self.active_city = None
            except Exception as e:
                logger.error(f"Failed to parse active_city payload: {e}")
            return

        try:
            topic_parts = msg.topic.split('/')
            node_id = topic_parts[1]
            if node_id in self.orchestrators:
                # LAZY ORCHESTRATION: Only process if city is active
                if self.active_city and not node_id.lower().startswith(self.active_city):
                    return

                if topic_parts[2] == "control":
                    try:
                        orch = self.orchestrators[node_id]
                        payload = json.loads(msg.payload.decode())
                        action = str(payload.get("action", "")).lower()

                        if action == "start_trading":
                            orch.set_trading_enabled(True, "Control command: start_trading")
                            logger.info(f"[{node_id}] start_trading applied")
                        elif action == "stop_trading":
                            orch.set_trading_enabled(False, "Control command: stop_trading")
                            orch.apply_hold_command("Control command: hold while trading is paused")
                            logger.info(f"[{node_id}] stop_trading applied")
                        elif action == "reset_soc":
                            # Forward reset request to simulator command topic.
                            client.publish(
                                f"microgrid/{node_id}/simulator_commands",
                                json.dumps(payload),
                                qos=1,
                            )
                            logger.info(f"[{node_id}] reset_soc forwarded to simulator")
                    except Exception as exc:
                        logger.error(f"Control command error for {node_id}: {exc}")
                    return
                
                # 1. MULTIPLEXED INGESTION: Read telemetry and write to DB immediately
                if topic_parts[2] == "telemetry":
                    try:
                        orch = self.orchestrators[node_id]
                        reading = None
                        if node_id not in self._db_ready_nodes:
                            orch.edge_node._db.initialize()
                            self._db_ready_nodes.add(node_id)

                        reading = TelemetryReading.from_json(msg.payload.decode())
                        # Write directly to the node's private DB when possible.
                        try:
                            orch.edge_node._db.insert_reading(reading)
                        except Exception as db_err:
                            logger.error(f"Ingestion DB write failed for {node_id}: {db_err}")

                        # 1b. DASHBOARD BRIDGE: Always publish edge trace for UI continuity.
                        dashboard_payload = json.dumps({
                            "input": f"Telemetry from {node_id}",
                            "output": {
                                "soc_pct": reading.soc_pct,
                                "voltage_v": reading.voltage_v,
                                "power_solar_kw": reading.power_solar_kw,
                                "power_load_kw": reading.power_load_kw,
                                "battery_power_kw": reading.battery_power_kw,
                                "grid_import_kw": reading.grid_import_kw,
                                "grid_export_kw": reading.grid_export_kw,
                            },
                            "ts": (
                                reading.timestamp.isoformat()
                                if hasattr(reading.timestamp, "isoformat")
                                else str(reading.timestamp)
                            )
                        })
                        client.publish(f"dashboard/trace/{node_id}/edge", dashboard_payload, qos=0)
                    except Exception as e:
                        logger.error(f"Ingestion error for {node_id}: {e}")
                        reading = None
                else:
                    reading = None

                # 2. STRATEGIC DISPATCH: Pass to FSM logic
                # Dispatch internally
                self.orchestrators[node_id]._on_message(client, userdata, msg)

                if reading is not None:
                    self._post_state_snapshot(node_id, reading)
        except Exception as e:
            logger.error(f"Routing error on {msg.topic}: {e}")

    def start(self):
        self.is_running = True
        self._mqtt.connect(self.broker_host, self.broker_port)
        self._mqtt.loop_start()
        logger.info("Multi-Orchestrator ACTIVE. Running safety for 75 nodes.")
        
        while self.is_running:
            import time
            time.sleep(1)

    def stop(self):
        self.is_running = False
        self._mqtt.loop_stop()
        self._mqtt.disconnect()
        for nid, orch in self.orchestrators.items():
             orch.stop()
             orch.edge_node.stop()

if __name__ == "__main__":
    multi_orch = MultiOrchestrator()
    
    def shutdown(sig, frame):
        logger.info("Shutting down Multi-Orchestrator...")
        multi_orch.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    multi_orch.start()
