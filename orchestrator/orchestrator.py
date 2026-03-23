"""
orchestrator/orchestrator.py
============================
The main Tactical Orchestrator entry point.
Subscribes to telemetry, manages FSM, enforces safety, and handles LLM commands.
"""
import json
import logging
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt

from edge import config
from edge.models import TelemetryReading
from orchestrator.fsm import MicrogridFSM
from orchestrator.safety_buffer import SafetyBuffer, SafetyVerdict
from orchestrator.failover_manager import FailoverManager, GridStatus
from orchestrator.mqtt_handshake import MQTTHandshake, HandshakeResult
from orchestrator.safe_window import SafeWindowPublisher

logger = logging.getLogger("Orchestrator.Main")

class TacticalOrchestrator:
    """
    Coordinates sub-second safety and operational logic for one home node.
    """
    def __init__(self, node_id: str, edge_node):
        self.node_id = node_id
        self.edge_node = edge_node  # edge.EdgeNode instance
        
        # Sub-modules
        self.fsm = MicrogridFSM(node_id)
        self.safety = SafetyBuffer(node_id)
        self.failover = FailoverManager(node_id)
        
        # MQTT Topics
        self.topic_telemetry = config.telemetry_topic(node_id)
        self.topic_llm_cmds  = config.llm_commands_topic(node_id)
        self.topic_safe_win  = config.safe_window_topic(node_id)
        self.topic_hs_req    = config.handshake_request_topic(node_id)
        self.topic_hs_res    = config.handshake_response_topic(node_id)

        # MQTT Client (internal for orchestrator control loop)
        self._client = mqtt.Client(client_id=f"Orchestrator_{node_id}")
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        
        self.handshake = MQTTHandshake(node_id, self._client)
        self.publisher = SafeWindowPublisher(node_id, self._client)
        
        # Dashboard tracking
        self._last_verdict: str = "WAITING"
        self._last_action: str = "NONE"
        self._current_soc: float = 0.0  # kept fresh from telemetry

    # ------------------------------------------------------------------
    # Dashboard Helper
    # ------------------------------------------------------------------
    def _publish_dashboard_state(self, verdict: str, reason: str, soc: float = None):
        """Push a dashboard trace event so the browser reflects the current FSM state."""
        trace_topic = f"dashboard/trace/{self.node_id}/orchestrator"
        self._client.publish(trace_topic, json.dumps({
            "input": f"FSM update: {self.fsm.state}",
            "output": {
                "verdict": verdict,
                "reason": reason,
                "fsm_state": self.fsm.state,
                "soc": soc if soc is not None else self._current_soc,
                "last_strategy": self._last_action,
                "strategy_status": self._last_verdict
            },
            "ts": __import__("time").strftime('%Y-%m-%dT%H:%M:%SZ', __import__("time").gmtime())
        }))

    # MQTT Callbacks
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe([(self.topic_telemetry, 1), 
                              (self.topic_llm_cmds, 1),
                              (self.topic_hs_req, 1),
                              (self.topic_hs_res, 1)])
            logger.info(f"[{self.node_id}] Orchestrator connected and subscribed to topics.")
        else:
            logger.error(f"[{self.node_id}] Orchestrator connection failed (rc={rc}).")

    def _on_message(self, client, userdata, msg):
        """Dispatches incoming MQTT messages to handlers."""
        try:
            payload = msg.payload.decode("utf-8")
            
            if msg.topic == self.topic_telemetry:
                self._handle_telemetry(payload)
            elif msg.topic == self.topic_llm_cmds:
                threading.Thread(target=self._handle_llm_command, args=(payload,), daemon=True).start()
            elif msg.topic == self.topic_hs_req:
                self._handle_handshake_request(payload)
            elif msg.topic == self.topic_hs_res:
                self.handshake.handle_response(json.loads(payload))
                
        except Exception as e:
            logger.error(f"[{self.node_id}] Error in orchestrator msg handler: {e}")

    # ------------------------------------------------------------------
    # Logic Handlers
    # ------------------------------------------------------------------
    def _handle_telemetry(self, raw_json: str):
        """Processes real-time telemetry and updates FSM/Safety status."""
        reading = TelemetryReading.from_json(raw_json)
        
        # 1. Check Safety
        verdict = self.safety.check(reading.soc_pct)
        if verdict == SafetyVerdict.CRITICAL and self.fsm.state != "EMERGENCY":
            self.fsm.critical_soc()
            
        # 2. Check Grid Failover
        grid_status = self.failover.assess(reading.voltage_v)
        self.fsm.grid_available = (grid_status == GridStatus.CONNECTED)

        # If SoC recovered from critical, allow FSM to leave EMERGENCY.
        if self.fsm.state == "EMERGENCY" and verdict != SafetyVerdict.CRITICAL:
            try:
                if grid_status == GridStatus.CONNECTED:
                    self.fsm.grid_restored()
                else:
                    self.fsm.recover()
            except Exception:
                # If transition fails (e.g. no valid path), force recovery to connected if grid is up
                if grid_status == GridStatus.CONNECTED:
                    self.fsm.grid_restored()
                else:
                    logger.warning(f"[{self.node_id}] FSM trapped in EMERGENCY. Waiting for grid...")

        if grid_status == GridStatus.FAILED and self.fsm.state in ["GRID_CONNECTED", "P2P_TRADING"]:
            self.fsm.grid_failed()
        elif grid_status == GridStatus.CONNECTED and self.fsm.state == "ISLANDED":
            self.fsm.grid_restored()

        # 3. Publish Safe Operating Window
        avail_discharge = self.safety.get_available_capacity_kwh(
            reading.soc_pct, self.edge_node.battery_capacity_kwh
        )
        self.publisher.compute_and_publish(
            topic=self.topic_safe_win,
            timestamp=reading.timestamp,
            state=self.fsm.state,
            grid_status=grid_status.value,
            soc_pct=reading.soc_pct,
            available_discharge_kwh=avail_discharge,
            battery_cap_kwh=self.edge_node.battery_capacity_kwh
        )

        # Track current SoC for dashboard state pushes
        self._current_soc = reading.soc_pct

        # Only push dashboard update if state changed (not as noisy heartbeat)
        # (State change callbacks in FSM handle the main push; we push SoC here)
        self._publish_dashboard_state(
            verdict="HEARTBEAT",
            reason=f"Watching node at SoC={reading.soc_pct:.1f}%",
            soc=reading.soc_pct
        )

    def _handle_llm_command(self, raw_json: str):
        """Validated and executes high-level commands from the LLM agent."""
        try:
            cmd = json.loads(raw_json)
            logger.info(f"[{self.node_id}] Received LLM Command: {cmd}")
            
            # Safety Gate
            last_reading = self.edge_node.get_latest_reading()
            current_soc = last_reading.soc_pct if last_reading else 0.0
            
            # Check for snapshot drift (time-of-observation vs time-of-action)
            snapshot_soc = cmd.get("snapshot_soc")
            if snapshot_soc is not None:
                drift = abs(current_soc - snapshot_soc)
                if drift > config.SOC_DRIFT_TOLERANCE:
                    logger.warning(
                        f"[{self.node_id}] LLM Command STALE: snapshot SoC={snapshot_soc}% vs "
                        f"live={current_soc:.1f}%. Drift ({drift:.1f}%) exceeds "
                        f"tolerance ({config.SOC_DRIFT_TOLERANCE}%). REJECTING."
                    )
                    self._last_verdict = "REJECTED (STALE)"
                    self._publish_dashboard_state(
                        verdict="STALE_REJECTED",
                        reason=f"SoC drifted {drift:.1f}% during reasoning"
                    )
                    return
                # Use the snapshot for safety logic (what the LLM reasoned about)
                current_soc = snapshot_soc

            ok, reason = self.safety.validate_llm_command(cmd, current_soc)

            # Execution logic (Handshake for trades)
            action = cmd.get("action", "").upper()
            self._last_action = action
            self._last_verdict = "ALLOWED" if ok else "REJECTED"

            if not ok:
                logger.error(f"[{self.node_id}] LLM Command REJECTED: {reason}")
                return

            if action in ["BUY", "SELL"]:
                target_peer = cmd.get("target")
                amount = cmd.get("amount_kwh", 0.0)
                price = cmd.get("price_per_kwh", 0.0)
                
                self.fsm.start_trade()
                # --- Immediately push the TRADING state to dashboard ---
                self._publish_dashboard_state(
                    verdict="IN_PROGRESS",
                    reason=f"{action} {amount}kWh @ ₹{price}/kWh via {target_peer or 'Market'}"
                )

                # In this demo, if target is generic "P2P_MARKET", simulate a
                # successful anonymous market trade without a specific peer handshake.
                if target_peer in ["P2P_MARKET", "MARKET", "GRID", "grid", None]:
                    logger.info(f"[{self.node_id}] Executing market {action} via Automated Market Maker...")
                    time.sleep(0.5) # Reduced sleep to avoid blocking dashboard
                    result = HandshakeResult.ACCEPTED
                else:
                    # Perform Real P2P Handshake
                    result = self.handshake.initiate(target_peer, amount, price)
                    if result == HandshakeResult.ACCEPTED:
                        time.sleep(0.5)
                
                if result == HandshakeResult.ACCEPTED:
                    logger.info(f"[{self.node_id}] Trade finalized. Opening simulated circuits...")
                else:
                    logger.warning(f"[{self.node_id}] Trade failed ({result}).")
                
                self.fsm.finish_trade()
                # --- Push COMPLETED state to dashboard ---
                self._publish_dashboard_state(
                    verdict="COMPLETED",
                    reason=f"{action} trade completed ({result})"
                )

            elif action in ["CHARGE", "DISCHARGE"]:
                self.fsm.start_trade()
                # --- Push active battery operation to dashboard ---
                self._publish_dashboard_state(
                    verdict="IN_PROGRESS",
                    reason=f"{action} battery operation in progress..."
                )
                time.sleep(0.5)
                self.fsm.finish_trade()
                # --- Push completion ---
                self._publish_dashboard_state(
                    verdict="COMPLETED",
                    reason=f"{action} operation complete"
                )

            elif action == "HOLD":
                # Just update the dashboard trace to keep things fresh
                self._publish_dashboard_state(
                    verdict="ALLOWED",
                    reason="System in HOLD state (No action required)."
                )


        except Exception as e:
            logger.error(f"[{self.node_id}] Failed to process LLM command: {e}")
            self._last_verdict = "ERROR"
            self._publish_dashboard_state(
                verdict="ERROR",
                reason=f"Command execution failure: {e}"
            )

    def _handle_handshake_request(self, raw_json: str):
        """Automatically respond to peer handshake requests based on local state."""
        try:
            req = json.loads(raw_json)
            sender = req["sender_id"]
            
            # Simple policy: accept if not in EMERGENCY and SoC is above buffer
            current_soc = self.edge_node.get_latest_reading().soc_pct if self.edge_node.get_latest_reading() else 0.0
            verdict = self.safety.check(current_soc)
            
            if self.fsm.state == "EMERGENCY" or verdict != SafetyVerdict.ALLOW:
                self.handshake.send_response(req, HandshakeResult.REJECTED)
            else:
                self.handshake.send_response(req, HandshakeResult.ACCEPTED)
                
        except Exception as e:
            logger.error(f"[{self.node_id}] Error handling handshake request: {e}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self, broker_host=config.MQTT_BROKER, broker_port=config.MQTT_PORT):
        """Starts the Orchestrator loop."""
        logger.info(f"[{self.node_id}] Starting Tactical Orchestrator...")
        self._client.connect(broker_host, broker_port, keepalive=60)
        self._client.loop_start()

    def stop(self):
        """Stops the Orchestrator loop."""
        self._client.loop_stop()
        self._client.disconnect()
        logger.info(f"[{self.node_id}] Orchestrator stopped.")
