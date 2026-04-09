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
from typing import Dict

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from edge import config
from edge.node import EdgeNode
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
        
        # 2. Warm up all 75 Orchestrators
        self.orchestrators: Dict[str, TacticalOrchestrator] = {}
        logger.info("Instantiating 75 Tactical Orchestrators...")
        for nid in config.NODE_CONFIGS:
             # Need an EdgeNode instance for the database it manages
             edge_node = EdgeNode(nid)
             edge_node.start() # Start MQTT/DB ingestion
             
             # Create orchestrator with SHARED MQTT client
             orch = TacticalOrchestrator(nid, edge_node)
             orch._client = self._mqtt # Override with multiplexed client
             self.orchestrators[nid] = orch

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # Multi-Subscribe
            client.subscribe([
                ("microgrid/+/telemetry", 1),
                ("microgrid/+/llm_commands", 1),
                ("microgrid/+/handshake/request", 1),
                ("microgrid/+/handshake/response", 1)
            ])
            logger.info("Multiplexed subscription active for all 75 nodes.")
        else:
            logger.error(f"Multiplexed MQTT connect failed (rc={rc})")

    def _on_message(self, client, userdata, msg):
        """Route messages to the correct per-node orchestrator by ID."""
        try:
            topic_parts = msg.topic.split('/')
            node_id = topic_parts[1]
            if node_id in self.orchestrators:
                # Dispatch internally
                self.orchestrators[node_id]._on_message(client, userdata, msg)
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
