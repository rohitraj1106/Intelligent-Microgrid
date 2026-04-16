"""
strategic_agent/multi_agent_runner.py
====================================
The NEW Strategic Core: Only runs LLM reasoning for nodes in the ACTIVE city.
Activated by dashboard/active_city MQTT signal.
"""
import json
import logging
import signal
import sys
import os
import time
import threading
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor  # kept for potential future use

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from edge import config
from edge.node import EdgeNode
from strategic_agent.llm_client import GeminiClient
from strategic_agent.negotiation import MarketplaceClient
from strategic_agent.rate_limiter import RateLimiter
from strategic_agent.batch_builder import BatchPromptBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("MultiNodeAgent")

class MultiNodeAgent:
    def __init__(self, cycle_interval: int = 30):
        self.cycle_interval = cycle_interval
        self.active_city: Optional[str] = None
        self.selected_node: Optional[str] = None
        self.is_running = False
        self._city_lock = threading.Lock()
        
        self._request_counter = 0
        self._request_lock = threading.Lock()
        self._llm_semaphore = threading.Semaphore(max(1, int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", "2"))))
        
        # 1. Core Modules
        self.llm = GeminiClient()
        self.limiter = RateLimiter(max_rpm=max(1, int(os.getenv("LLM_MAX_RPM", "120"))))
        self.builder = BatchPromptBuilder()
        self.marketplace = MarketplaceClient() # Shared across all nodes
        self.safe_windows: Dict[str, Dict] = {} # Cache for real-time safety constraints
        self.last_decisions: Dict[str, str] = {} # Track strategic goals for consistency
        self.city_stats: Dict[str, Dict] = {} # CACHE for city-wide aggregates
        
        # 2. Warm up EdgeNodes (Lazy Mode)
        self.nodes: Dict[str, EdgeNode] = {}
        logger.info("Initializing Strategic Agent (Unified Batch Mode)...")

        # 3. MQTT Client
        self._mqtt = mqtt.Client(client_id="MultiNodeAgent")
        self._mqtt.on_connect = self._on_connect
        self._mqtt.on_message = self._on_message
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe([
                ("dashboard/active_city", 0), 
                ("dashboard/selected_node", 0),
                ("microgrid/+/safe_window", 0)
            ])
            logger.info("Subscribed to dashboard signals and all safe windows (QoS 0)")
        else:
            logger.error(f"MQTT connect failed (rc={rc})")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            logger.info(f"MQTT SIGNAL [Topic: {msg.topic}]: {payload}")
            
            if msg.topic == "dashboard/active_city":
                new_city = payload.get("city")
                with self._city_lock:
                    if new_city != self.active_city:
                        self.active_city = new_city.lower() if new_city else None
                        logger.info(f"CITY SWITCH: {self.active_city or 'NONE (Paused)'}")
            elif msg.topic == "dashboard/selected_node":
                node_id = payload.get("node_id")
                if node_id:
                     city_name = node_id.split('_')[0]
                     with self._city_lock:
                         self.active_city = city_name
                     logger.info(f"SELECTED NODE: {node_id} (Active City: {self.active_city})")
                     
                     # Warmup pulse for the new city
                     city_nodes = [nid for nid in config.NODE_CONFIGS if nid.startswith(city_name.lower())]
                     for nid in city_nodes[:15]:
                         try:
                             f_data = self.generate_24h_profile(nid, 12)
                             self._mqtt.publish(
                                 f"dashboard/trace/{nid}/forecast",
                                 json.dumps({"node_id": nid, "data": f_data, "ts": datetime.utcnow().isoformat()}),
                                 qos=0
                             )
                         except: pass
            elif msg.topic.endswith("/safe_window"):
                node_id = msg.topic.split('/')[1]
                self.safe_windows[node_id] = payload

        except Exception as e:
            logger.error(f"Error handling MQTT signal: {e}")

    def _next_request_id(self) -> int:
        with self._request_lock:
            self._request_counter += 1
            return self._request_counter

    def _infer_with_limits(self, prompt: str, schema: Optional[Dict[str, Any]], call_type: str, city: str, node_id: Optional[str]) -> Any:
        req_id = self._next_request_id()
        logger.info(f"[{city}] LLM dispatch req={req_id} type={call_type} node={node_id or '-'}")
        t0 = time.monotonic()

        # Acquire rate limit token right before an actual API call.
        self.limiter.await_permit()

        with self._llm_semaphore:
            queue_wait = time.monotonic() - t0
            logger.info(f"[{city}] LLM request started req={req_id} queue_wait={queue_wait:.2f}s")
            response = self.llm.infer_json(prompt, schema=schema)

        elapsed = time.monotonic() - t0
        logger.info(f"[{city}] LLM request finished req={req_id} elapsed={elapsed:.2f}s")
        return response

    def generate_24h_profile(self, node_id: str, start_hour: int):
        """Seasonal Intelligence: March-April Delhi NCR Profile."""
        import random
        node_rng = random.Random(hash(node_id) + start_hour)
        hash_val = hash(node_id) % 10
        if hash_val < 3: archetype = "AC_HEAVY"
        elif hash_val < 6: archetype = "COOLER"
        elif hash_val < 8: archetype = "WFH"
        elif hash_val < 9: archetype = "EV"
        else: archetype = "EFFICIENT"

        time_shift = node_rng.randint(-2, 3) 
        mock_load, mock_solar = [], []
        panel_efficiency = node_rng.uniform(0.75, 1.0)
        cloud_hour = node_rng.randint(11, 14) if node_rng.random() < 0.2 else -1

        for h_offset in range(24):
            abs_h = (start_hour + h_offset + time_shift) % 24
            real_h = (start_hour + h_offset) % 24
            sol = 0.0
            if 6 <= real_h <= 18:
                x = (real_h - 6) / 12.5 * math.pi
                sol = 7.0 * panel_efficiency * math.sin(x)
                if real_h == cloud_hour: sol *= 0.4
                sol *= node_rng.uniform(0.95, 1.05)
            mock_solar.append(round(max(0, sol), 2))
            base = node_rng.uniform(0.4, 0.8) 
            load = base
            if archetype == "AC_HEAVY":
                if 12 <= abs_h <= 18: load += node_rng.uniform(2.5, 4.0)
                elif 21 <= abs_h or abs_h <= 5: load += node_rng.uniform(1.8, 3.0)
            elif archetype == "COOLER":
                if 10 <= abs_h <= 20: load += node_rng.uniform(0.7, 1.2)
            elif archetype == "WFH":
                if 9 <= abs_h <= 18: load += node_rng.uniform(1.5, 2.8)
            elif archetype == "EV":
                if 22 <= abs_h or abs_h <= 4: load += node_rng.uniform(3.5, 5.0)
                else: load += 0.3
            else:
                if 19 <= abs_h <= 22: load += node_rng.uniform(0.5, 1.0)
            if node_rng.random() < 0.08:
                load += node_rng.uniform(0.5, 1.5)
            mock_load.append(round(max(0.2, load), 2))
        return mock_load, mock_solar, archetype

    def publish_forecast(self, node_id: str, status_dict: Dict):
        """Published detailed 24h forecast to dashboard."""
        as_of = status_dict.get('as_of', '')
        try: hour = int(as_of.split('T')[1].split(':')[0])
        except: hour = 12
        mock_load, mock_solar, archetype = self.generate_24h_profile(node_id, hour)
        self._mqtt.publish(f"dashboard/trace/{node_id}/forecast", json.dumps({
            "output": {
                "load": mock_load,
                "solar": mock_solar,
                "start_hour": hour,
                "archetype": archetype
            }
        }), qos=0)

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _normalize_node_decision(self, node_id: str, raw: Any) -> Optional[Dict[str, Any]]:
        """Coerce varied LLM output shapes into one decision dict for a single node."""
        decision: Optional[Dict[str, Any]] = None

        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                if item.get("node_id") == node_id:
                    decision = item
                    break
            if decision is None:
                decision = next((item for item in raw if isinstance(item, dict)), None)
        elif isinstance(raw, dict):
            if "action" in raw:
                decision = raw
            else:
                inner = raw.get(node_id)
                if isinstance(inner, dict):
                    decision = inner

        if not isinstance(decision, dict):
            return None

        action = str(decision.get("action", "HOLD") or "HOLD").upper()
        if action not in {"BUY", "SELL", "HOLD", "CHARGE", "DISCHARGE"}:
            action = "HOLD"

        target = decision.get("target")
        if target is None or str(target).strip().lower() in {"", "none", "null"}:
            target = "grid"

        normalized = {
            "node_id": node_id,
            "action": action,
            "amount_kwh": max(0.0, min(0.5, self._to_float(decision.get("amount_kwh"), 0.0))),
            "price_per_kwh": max(0.0, self._to_float(decision.get("price_per_kwh"), 0.0)),
            "target": target,
            "reasoning": str(decision.get("reasoning") or "No reasoning provided."),
            "is_real": True,
        }
        return normalized

    def _fallback_hold_decision(self, node_id: str, reason_code: str) -> Dict[str, Any]:
        return {
            "node_id": node_id,
            "action": "HOLD",
            "amount_kwh": 0.0,
            "price_per_kwh": 0.0,
            "target": "grid",
            "reasoning": f"LLM_{reason_code}",
            "is_real": True,
        }

    def _extract_batch_decisions(self, batch_nodes: List[str], raw: Any) -> List[Dict[str, Any]]:
        """
        Parse one batch LLM response into one decision per node without cloning.
        Supported formats:
        - list[dict] (preferred)
        - dict[node_id] -> dict
        - malformed/single-object fallback => HOLD for missing nodes
        """
        decisions_by_node: Dict[str, Dict[str, Any]] = {}
        unnamed_items: List[Dict[str, Any]] = []

        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                nid = item.get("node_id")
                if isinstance(nid, str) and nid in batch_nodes and nid not in decisions_by_node:
                    parsed = self._normalize_node_decision(nid, item)
                    if parsed:
                        decisions_by_node[nid] = parsed
                else:
                    unnamed_items.append(item)

            # Positional fallback for items missing node_id.
            unnamed_index = 0
            for nid in batch_nodes:
                if nid in decisions_by_node:
                    continue
                while unnamed_index < len(unnamed_items):
                    parsed = self._normalize_node_decision(nid, unnamed_items[unnamed_index])
                    unnamed_index += 1
                    if parsed:
                        decisions_by_node[nid] = parsed
                        break

        elif isinstance(raw, dict):
            if "action" in raw:
                logger.warning("Batch response returned a single decision object; skipping clone-to-all behavior.")
            else:
                for nid in batch_nodes:
                    node_raw = raw.get(nid)
                    if isinstance(node_raw, dict):
                        parsed = self._normalize_node_decision(nid, node_raw)
                        if parsed:
                            decisions_by_node[nid] = parsed

        final: List[Dict[str, Any]] = []
        for nid in batch_nodes:
            if nid in decisions_by_node:
                final.append(decisions_by_node[nid])
            else:
                final.append(self._fallback_hold_decision(nid, "BATCH_PARSE_MISS"))
        return final

    def _process_batch(self, city: str, batch_nodes: list, market_data, grid_prices):
        """Processes a single batch of 5 nodes through the LLM and handles telemetry-to-dashboard bridging."""
        nodes_status = {}
        for nid in batch_nodes:
            if nid not in self.nodes:
                self.nodes[nid] = EdgeNode(nid)
            status = self.nodes[nid].get_status(hours=1)
            
            if status:
                s_dict = status.to_dict()
                
                # FAST UI UPDATE: Publish forecast immediately
                self.publish_forecast(nid, s_dict)
                
                try: hour = int(s_dict.get('as_of', '').split('T')[1].split(':')[0])
                except: hour = 12
                m_load, m_solar, _ = self.generate_24h_profile(nid, hour)
                outlook_4h = sum(m_solar[j] - m_load[j] for j in range(4))
                s_dict['outlook_4h'] = round(outlook_4h, 2)
                s_dict['intent'] = self.last_decisions.get(nid, "BALANCED")
                nodes_status[nid] = s_dict
            else:
                logger.warning(f"No telemetry for {nid} yet.")

        if not nodes_status: return

        # 1. Refresh situational awareness (neighbor discovery)
        ref_nid = next(iter(nodes_status))
        best_neighbor = self.marketplace.discover_best_peer(
            "BUY" if nodes_status[ref_nid].get('current_soc_pct', 50) < 50 else "SELL"
        )
        
        # 2. One batch LLM call for this group, then split decisions per node.
        logger.info(f"[{city}] Dispatching Batch LLM Reasoning...")
        # Sort nodes to provide a stable order for the LLM prompt
        llm_nodes = sorted(list(nodes_status.keys()))
        ordered_status = {nid: nodes_status[nid] for nid in llm_nodes}
        
        batch_prompt = self.builder.build(
            city_name=city,
            nodes_status=ordered_status,
            market_snapshot=market_data,
            grid_prices=grid_prices,
            cycle_id=1,
        )

        final_decisions: List[Dict[str, Any]] = []
        batch_schema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "node_id": {"type": "STRING"},
                    "action": {"type": "STRING", "enum": ["BUY", "SELL", "HOLD"]},
                    "amount_kwh": {"type": "NUMBER"},
                    "price_per_kwh": {"type": "NUMBER"},
                    "target": {"type": "STRING"},
                    "reasoning": {"type": "STRING"},
                },
                "required": ["node_id", "action", "amount_kwh", "price_per_kwh", "target", "reasoning"],
            },
        }
        try:
            raw_batch_result = self._infer_with_limits(
                prompt=batch_prompt,
                schema=batch_schema,
                call_type="batch",
                city=city,
                node_id=None,
            )
            final_decisions = self._extract_batch_decisions(llm_nodes, raw_batch_result)

            missing_count = sum(
                1 for d in final_decisions if str(d.get("reasoning", "")).startswith("LLM_BATCH_PARSE_MISS")
            )
            if missing_count > 0:
                logger.warning(
                    f"[{city}] Batch parse incomplete ({missing_count}/{len(llm_nodes)} missing). Retrying once with corrective prompt."
                )
                corrective_prompt = (
                    batch_prompt
                    + "\n\nCORRECTION: Your previous output was invalid. "
                    + f"Return EXACTLY {len(llm_nodes)} JSON array items with node_id in this order: "
                    + ", ".join(llm_nodes)
                    + ". No extra text."
                )
                retry_raw = self._infer_with_limits(
                    prompt=corrective_prompt,
                    schema=batch_schema,
                    call_type="batch_retry",
                    city=city,
                    node_id=None,
                )
                retry_decisions = self._extract_batch_decisions(llm_nodes, retry_raw)
                retry_missing_count = sum(
                    1 for d in retry_decisions if str(d.get("reasoning", "")).startswith("LLM_BATCH_PARSE_MISS")
                )
                if retry_missing_count < missing_count:
                    final_decisions = retry_decisions
        except Exception as e:
            logger.error(f"Batch LLM call failed for {city}: {e}")
            final_decisions = [self._fallback_hold_decision(nid, "BATCH_CALL_FAILED") for nid in llm_nodes]

        # Execute & Publish Trace
        for decision in final_decisions:
            nid = decision.get("node_id")
            if not nid: continue
            
            action = decision.get("action")
            self.last_decisions[nid] = action # Update memory
            
            # 1. LIVE MARKET ORDER
            if action in ["BUY", "SELL"]:
                try:
                    self.marketplace.place_order(
                        node_id=nid,
                        order_type=action,
                        quantity_kwh=decision.get("amount_kwh", 0.0),
                        price_per_kwh=decision.get("price_per_kwh", 0.0),
                        city=city
                    )
                except Exception as e:
                    logger.error(f"[{nid}] Failed to place simulation order: {e}")

            # 2. Publish to dashboard trace
            trace_topic = f"dashboard/trace/{nid}/agent"
            self._mqtt.publish(trace_topic, json.dumps({
                "input": f"Mass City Context: {city}",
                "reasoning": decision.get("reasoning", "Portfolio decision."),
                "output": decision,
                "ts": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), qos=0)
            
            # 3. Publish to orchestrator command topic
            cmd_topic = config.llm_commands_topic(nid)
            self._mqtt.publish(cmd_topic, json.dumps(decision), qos=0)
            
            # 4. Update forecast visual
            self.publish_forecast(nid, nodes_status.get(nid, {}))

    def run_city_cycle(self, city: str):
        """Processes all 15 nodes in 3 parallel batches."""
        logger.info(f"--- Starting UNIFIED Reasoning Cycle for {city.upper()} ---")
        
        city_nodes = [nid for nid in config.NODE_CONFIGS if nid.startswith(city)]
        if not city_nodes: return

        # 0. Thinking state broadcast
        for nid in city_nodes:
            self._mqtt.publish(f"dashboard/trace/{nid}/agent", json.dumps({
                "input": f"System initializing for {city.upper()} cycle...",
                "reasoning": f"Analyzing real-time load profile and grid voltage for {nid}. Evaluating P2P trade opportunities...",
                "output": {"action": "WAITING", "amount_kwh": 0, "price_per_kwh": 0},
                "ts": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), qos=0)

        batch_size = 5
        batches = [city_nodes[i:i + batch_size] for i in range(0, len(city_nodes), batch_size)]
        
        try: market_data = self.marketplace.get_market_snapshot()
        except: market_data = {"pending_buy_orders": [], "pending_sell_orders": [], "recent_trades": []}
            
        grid_prices = {"buy": 8.50, "sell": 3.00}

        # Update cache
        city_total_load, city_total_solar = 0.0, 0.0
        for nid in city_nodes:
            if nid not in self.nodes: self.nodes[nid] = EdgeNode(nid)
            st = self.nodes[nid].get_status(hours=1)
            if st:
                city_total_load += st.avg_load_kw
                city_total_solar += st.avg_solar_kw
        
        self.city_stats[city] = {
            "name": city.capitalize(),
            "total_load": round(city_total_load, 2),
            "total_solar": round(city_total_solar, 2),
            "best_peer": self.marketplace.discover_best_peer("BUY" if city_total_load > city_total_solar else "SELL")
        }

        for i, batch in enumerate(batches):
            with self._city_lock:
                if self.active_city != city: break
            if i > 0: time.sleep(0.5) 
            self._process_batch(city, batch, market_data, grid_prices)

    def start(self):
        self.is_running = True
        logger.info(f"Connecting to MQTT Broker at {config.MQTT_BROKER}...")
        try:
            self._mqtt.connect(config.MQTT_BROKER, config.MQTT_PORT)
            self._mqtt.loop_start()
            logger.info("Multi-Node Strategic Agent ACTIVE (Unified Mode).")
        except Exception as e:
            logger.error(f"FATAL: Agent failed to connect to MQTT: {e}")
            self.is_running = False
            return
        
        while self.is_running:
            with self._city_lock:
                current_city = self.active_city
            
            if current_city:
                logger.info(f"[{current_city}] Triggering reasoning cycle...")
                try: 
                    self.run_city_cycle(current_city)
                except Exception as e: 
                    logger.error(f"Error in city cycle {current_city}: {e}")
                
                # Wait for the next cycle after successful processing
                logger.info(f"Cycle complete. Waiting {self.cycle_interval}s for next cycle...")
                for _ in range(self.cycle_interval):
                    if not self.is_running: break
                    with self._city_lock:
                        if self.active_city != current_city: break # Respond to city switch immediately
                    time.sleep(1)
            else:
                # Idle state: fast poll for city activation
                time.sleep(1)

    def stop(self):
        self.is_running = False
        self._mqtt.loop_stop()
        self._mqtt.disconnect()
        self.llm.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Node Strategic Agent")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between full reasoning cycles")
    args = parser.parse_args()
    agent = MultiNodeAgent(cycle_interval=args.interval)
    def shutdown(sig, frame):
        logger.info("Shutting down MultiNodeAgent...")
        agent.stop()
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)
    agent.start()
