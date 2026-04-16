"""
edge/simulator.py
=================
Microgrid telemetry simulator — generates and MQTT-publishes realistic sensor
readings for ALL 5 home nodes simultaneously.

Solar / load physics are adapted from the teammate's sensor_simulator.py
(which had good math) but expanded to:
  - Support all 5 NODE_CONFIGS at once (not just one hardcoded home_id)
  - Use kW units (matching TelemetryReading / EdgeDatabase schema)
  - Derive battery_power_kw, grid_import_kw, grid_export_kw
  - Allow configurable interval and start time
  - Proper OOP design (MicrogridSimulator class)
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

import paho.mqtt.client as mqtt

from edge import config
from edge.config import NODE_CONFIGS, TELEMETRY_INTERVAL
from edge.models import TelemetryReading

logger = logging.getLogger("Edge.Simulator")


def _simulate_solar_kw(hour_decimal: float, peak_kw: float = 3.0, seed_noise: float = 1.0) -> float:
    """
    Bell-curve solar generation matching the Solar Forecaster's physics.
    Active between 06:00 and 18:00 only.
    """
    if 6.0 <= hour_decimal <= 18.0:
        x = (hour_decimal - 6.0) / 12.0 * math.pi
        cloud_factor = random.uniform(0.88, 1.0) * seed_noise
        return round(math.sin(x) * peak_kw * cloud_factor, 3)
    return 0.0


def _simulate_load_kw(hour_decimal: float, rng: random.Random, load_scale: float = 1.0) -> float:
    """
    Double-peak residential load profile (Load Forecaster pattern):
      - Morning peak  07:00–09:00
      - Evening peak  18:00–21:00
      - Night baseline otherwise
    """
    base = rng.uniform(0.2, 0.4)
    if 7.0 <= hour_decimal < 9.0:
        load = base + rng.uniform(1.0, 2.5)
    elif 18.0 <= hour_decimal < 21.0:
        load = base + rng.uniform(1.5, 3.5)
    else:
        load = base
    return round(max(0.05, load * max(0.6, load_scale)), 3)


class MicrogridSimulator:
    """
    Continuously generates synthetic telemetry for all 5 home nodes and
    publishes each reading to its dedicated MQTT topic.

    Parameters
    ----------
    broker_host : MQTT broker hostname
    broker_port : MQTT broker port
    interval    : Seconds between publish ticks (default from config)
    start_time  : Simulation start time (default: current UTC time)
    time_step   : Simulated minutes advanced per real-time interval
                  (e.g. 15 means 1 tick = 15 simulated minutes)
    """

    def __init__(
        self,
        broker_host:  str = config.MQTT_BROKER,
        broker_port:  int = config.MQTT_PORT,
        interval:     int = TELEMETRY_INTERVAL,
        start_time:   Optional[datetime] = None,
        time_step_min: int = 1,
    ):
        self.broker_host   = broker_host
        self.broker_port   = broker_port
        self.interval      = interval
        self.time_step_min = time_step_min
        self._running      = False

        # Simulation clock — defaults to 00:00 today so we see a full day cycle
        self._sim_time = start_time or datetime.utcnow().replace(hour=0, minute=0, second=0)

        # Per-node persistent state (SoC evolves across ticks)
        self._node_state: Dict[str, dict] = {
            node_id: {
                "soc_pct": (
                    random.uniform(65.0, 90.0)
                    if NODE_CONFIGS[node_id].get("tier") == "prosumer_anchor"
                    else random.uniform(45.0, 75.0)
                ),
                "rng":      random.Random(hash(node_id)),  # Deterministic per-node noise
            }
            for node_id in NODE_CONFIGS
        }

        # MQTT client (one shared client publishes for all nodes)
        self._client = mqtt.Client(client_id="MicrogridSimulator", clean_session=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self.active_city: Optional[str] = None
        self.require_active_city = str(os.getenv("SIMULATOR_REQUIRE_ACTIVE_CITY", "false")).lower() == "true"
        self._paused = True # Start paused as per user request

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Simulator connected to broker at {self.broker_host}:{self.broker_port}.")
            client.subscribe("dashboard/active_city")
            client.subscribe("dashboard/simulation_state")
            client.subscribe("microgrid/+/simulator_commands")
        else:
            logger.error(f"Simulator broker connection failed (rc={rc}).")

    def _on_message(self, client, userdata, msg):
        if msg.topic == "dashboard/simulation_state":
            try:
                payload = json.loads(msg.payload.decode())
                state = payload.get("state", "paused").lower()
                if state == "running":
                    self._paused = False
                    print(f"\n[PHYSIC] >>> SIMULATION RESUMED <<<\n")
                else:
                    self._paused = True
                    print(f"\n[PHYSIC] >>> SIMULATION PAUSED <<<\n")
            except Exception as e:
                logger.error(f"Failed to parse simulation_state: {e}")
            return

        if msg.topic == "dashboard/active_city":
            try:
                payload = json.loads(msg.payload.decode())
                city_name = payload.get("city")
                if city_name:
                    self.active_city = city_name.strip().lower()
                    print(f"\n[PHYSIC] >>> CITY ACTIVATED: {self.active_city.upper()} <<<")
                    print(f"[PHYSIC] Starting telemetry stream for 15 nodes in {self.active_city}...\n")
                    logger.info(f"Simulator focused on ACTIVE CITY: {self.active_city}")
                else:
                    self.active_city = None
                    print(f"\n[PHYSIC] >>> SIMULATION IDLE (No active city) <<<\n")
            except Exception as e:
                logger.error(f"Failed to parse active_city payload: {e}")
            return

        if msg.topic.startswith("microgrid/") and msg.topic.endswith("/simulator_commands"):
            try:
                parts = msg.topic.split("/")
                node_id = parts[1]
                payload = json.loads(msg.payload.decode())
                action = str(payload.get("action", "")).lower()

                if node_id not in self._node_state:
                    return

                if action == "reset_soc":
                    target_soc = float(payload.get("target_soc_pct", 50.0))
                    target_soc = max(0.0, min(100.0, target_soc))
                    self._node_state[node_id]["soc_pct"] = target_soc
                    logger.info(f"[{node_id}] reset_soc applied: SoC set to {target_soc:.1f}%")
                elif action == "inject_fault":
                    fault = payload.get("params", {}).get("type", "generic")
                    if fault == "battery_drain":
                        drop_pct = float(payload.get("params", {}).get("drop_pct", 20.0))
                        self._node_state[node_id]["soc_pct"] = max(
                            0.0,
                            self._node_state[node_id]["soc_pct"] - max(0.0, drop_pct),
                        )
                        logger.info(f"[{node_id}] inject_fault battery_drain applied")
                    else:
                        logger.info(f"[{node_id}] inject_fault received ({fault})")
                elif action == "apply_trade":
                    amount_kwh = float(payload.get("amount_kwh", 0.0))
                    is_buyer = bool(payload.get("is_buyer", False))
                    capacity_kwh = NODE_CONFIGS[node_id]["battery_capacity_wh"] / 1000.0
                    
                    # SoC change: (kWh / Capacity) * 100
                    delta_soc = (amount_kwh / capacity_kwh) * 100.0
                    if is_buyer:
                        self._node_state[node_id]["soc_pct"] = min(100.0, self._node_state[node_id]["soc_pct"] + delta_soc)
                        logger.info(f"[{node_id}] P2P APPLY: +{delta_soc:.2f}% SoC (Purchased {amount_kwh}kWh)")
                    else:
                        self._node_state[node_id]["soc_pct"] = max(0.0, self._node_state[node_id]["soc_pct"] - delta_soc)
                        logger.info(f"[{node_id}] P2P APPLY: -{delta_soc:.2f}% SoC (Sold {amount_kwh}kWh)")
            except Exception as e:
                logger.error(f"Failed to apply simulator command: {e}")

    # ------------------------------------------------------------------
    # Per-node reading generation
    # ------------------------------------------------------------------
    def _generate_reading(self, node_id: str, node_cfg: dict) -> TelemetryReading:
        """Produce one realistic TelemetryReading for the given node."""
        state = self._node_state[node_id]
        rng   = state["rng"]
        hour_dec = self._sim_time.hour + self._sim_time.minute / 60.0

        # Solar & load (kW)
        solar_peak_kw = float(node_cfg.get("solar_peak_kw", 3.0))
        load_scale = float(node_cfg.get("load_scale", 1.0))
        solar_kw = _simulate_solar_kw(hour_dec, peak_kw=solar_peak_kw, seed_noise=rng.uniform(0.88, 1.0))
        load_kw  = _simulate_load_kw(hour_dec, rng, load_scale=load_scale)

        # Battery kinetics: net = solar − load over this time step
        capacity_kwh = node_cfg["battery_capacity_wh"] / 1000.0
        step_h       = self.time_step_min / 60.0
        net_kwh      = (solar_kw - load_kw) * step_h

        soc_before = state["soc_pct"]
        delta_soc  = (net_kwh / capacity_kwh) * 100.0
        new_soc    = max(0.0, min(100.0, soc_before + delta_soc))
        state["soc_pct"] = new_soc

        battery_power_kw = solar_kw - load_kw         # +ve = charging
        grid_import_kw   = max(0.0, load_kw - solar_kw - max(0.0, battery_power_kw))
        grid_export_kw   = max(0.0, solar_kw - load_kw - max(0.0, -battery_power_kw))

        voltage_v = round(rng.uniform(225.0, 235.0), 1)
        current_a = round(load_kw * 1000.0 / voltage_v, 2) if voltage_v > 0 else 0.0

        return TelemetryReading(
            node_id          = node_id,
            timestamp        = self._sim_time.strftime("%Y-%m-%dT%H:%M:%S"),
            voltage_v        = voltage_v,
            current_a        = current_a,
            power_solar_kw   = solar_kw,
            power_load_kw    = round(load_kw, 3),
            soc_pct          = round(new_soc, 1),
            battery_power_kw = round(battery_power_kw, 3),
            grid_import_kw   = round(grid_import_kw, 3),
            grid_export_kw   = round(grid_export_kw, 3),
        )

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------
    def publish_all(self) -> None:
        """Generate and publish one reading for every node in NODE_CONFIGS."""
        active = self.active_city
        if not active and self.require_active_city:
            return

        for node_id, node_cfg in NODE_CONFIGS.items():
            if active and not node_id.lower().startswith(active):
                continue
            reading = self._generate_reading(node_id, node_cfg)
            topic   = config.telemetry_topic(node_id)
            payload = reading.to_json()
            # Telemetry is high-rate; QoS0 avoids PUBACK buildup on aMQTT under 75-node load.
            result  = self._client.publish(topic, payload, qos=0)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(
                    f"[{node_id}] {reading.timestamp} | "
                    f"solar={reading.power_solar_kw:.2f}kW  "
                    f"load={reading.power_load_kw:.2f}kW  "
                    f"SoC={reading.soc_pct:.1f}%"
                )
            else:
                logger.warning(f"[{node_id}] Publish failed (rc={result.rc})")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> bool:
        """Connect to broker. Returns True if successful."""
        try:
            self._client.connect(self.broker_host, self.broker_port, keepalive=60)
        except OSError as e:
            logger.error(f"Cannot connect to broker at {self.broker_host}:{self.broker_port} — {e}")
            return False
        self._client.loop_start()
        return True

    def run(self, interval: Optional[int] = None, ticks: Optional[int] = None) -> None:
        """
        Continuously publish telemetry for all nodes.

        Parameters
        ----------
        interval : Seconds between ticks (overrides constructor value if given)
        ticks    : If set, stop after this many publish cycles (useful for tests/demos)
        """
        tick_interval = interval or self.interval
        if not self.start():
            return

        self._running = True
        tick_count    = 0

        logger.info(
            f"Simulator running — {len(NODE_CONFIGS)} nodes, "
            f"{tick_interval}s real-time interval, "
            f"{self.time_step_min}min simulated step per tick."
        )

        try:
            while self._running:
                if not self._paused:
                    self.publish_all()
                    # Advance simulation clock
                    self._sim_time += timedelta(minutes=self.time_step_min)
                    tick_count += 1

                    if ticks is not None and tick_count >= ticks:
                        logger.info(f"Completed {ticks} ticks. Stopping.")
                        break
                    
                    # Sleep in small chunks to remain responsive to pause signals
                    for _ in range(int(tick_interval)):
                        if self._paused or not self._running:
                            break
                        time.sleep(1.0)
                else:
                    # When paused, just wait a bit and check again
                    time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Simulator interrupted.")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop publishing and disconnect cleanly."""
        self._running = False
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("Simulator stopped.")
