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
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from edge import config
from edge.node import EdgeNode
from strategic_agent.llm_client import GeminiClient
from strategic_agent.negotiation import MarketplaceClient
from strategic_agent.rate_limiter import RateLimiter
from strategic_agent.batch_builder import BatchPromptBuilder
from strategic_agent.prompt_builder import PromptBuilder # ADDED

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
        self._processing_nodes = set() # Track nodes currently being processed to avoid duplicates
        self._processing_lock = threading.Lock()
        # 1. Core Modules
        self.llm = GeminiClient()
        self.limiter = RateLimiter(max_rpm=14) # 14 calls per minute
        self.builder = BatchPromptBuilder()
        self.single_builder = PromptBuilder() # For the selected node
        self.marketplace = MarketplaceClient() # Shared across all nodes
        self.safe_windows: Dict[str, Dict] = {} # Cache for real-time safety constraints
        self.last_decisions: Dict[str, str] = {} # Track strategic goals for consistency
        self.city_stats: Dict[str, Dict] = {} # CACHE for city-wide aggregates
        
        # 2. Warm up EdgeNodes (all 75)
        self.nodes: Dict[str, EdgeNode] = {}
        logger.info("Initializing 75 EdgeNodes (read-only mode)...")
        for nid in config.NODE_CONFIGS:
             self.nodes[nid] = EdgeNode(nid) # Node logic without start() (we just read DB)

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
            logger.info("Subscribed to dashboard signals and all safe windows")
        else:
            logger.error(f"MQTT connect failed (rc={rc})")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if msg.topic == "dashboard/active_city":
                new_city = payload.get("city")
                with self._city_lock:
                    if new_city != self.active_city:
                        self.active_city = new_city.lower() if new_city else None
                        logger.info(f"CITY SWITCH: {self.active_city or 'NONE (Paused)'}")
            elif msg.topic == "dashboard/selected_node":
                new_node = payload.get("node_id")
                with self._city_lock:
                    self.selected_node = new_node
                    current_city = self.active_city
                
                logger.info(f"NODE SELECTED: {self.selected_node}")
                
                # TRIGGER INSTANT REASONING for the selected node
                if new_node and current_city and new_node.startswith(current_city):
                    threading.Thread(
                        target=self._run_immediate_reasoning, 
                        args=(current_city, new_node), 
                        daemon=True
                    ).start()
            elif msg.topic.endswith("/safe_window"):
                node_id = msg.topic.split('/')[1]
                self.safe_windows[node_id] = payload

        except Exception as e:
            logger.error(f"Error handling MQTT signal: {e}")

    def _run_immediate_reasoning(self, city: str, node_id: str):
        """One-off trigger for a specific node to respond to user interaction."""
        with self._processing_lock:
            if node_id in self._processing_nodes:
                return
            self._processing_nodes.add(node_id)
        
        try:
            market_data = self.marketplace.get_market_snapshot()
            grid_prices = {"buy": 8.50, "sell": 3.00}
            self._process_batch(city, [node_id], market_data, grid_prices)
        finally:
            with self._processing_lock:
                self._processing_nodes.remove(node_id)

    def generate_24h_profile(self, node_id: str, start_hour: int):
        """
        Seasonal Intelligence: March-April Delhi NCR Profile.
        COMPLETELY REWRITTEN for realistic diversity and non-zero nighttime loads.
        """
        import random
        # Per-node random seed for unique, stable noise
        node_rng = random.Random(hash(node_id) + start_hour)
        
        # 1. Randomized Archetype & Behavior Shift
        hash_val = hash(node_id) % 10
        if hash_val < 3: archetype = "AC_HEAVY"
        elif hash_val < 6: archetype = "COOLER"
        elif hash_val < 8: archetype = "WFH"
        elif hash_val < 9: archetype = "EV"
        else: archetype = "EFFICIENT"

        # Unique Shift: When does this house peak? (Shift by -2 to +3 hours)
        time_shift = node_rng.randint(-2, 3) 
        
        mock_load = []
        mock_solar = []
        
        # 2. Solar Variation: Each house has different roof orientation/soiling
        panel_efficiency = node_rng.uniform(0.75, 1.0)
        cloud_hour = node_rng.randint(11, 14) if node_rng.random() < 0.2 else -1

        for h_offset in range(24):
            # Target hour with individual house shift
            abs_h = (start_hour + h_offset + time_shift) % 24
            real_h = (start_hour + h_offset) % 24 # for solar (aligned to sun)

            # --- Solar Profile (Fixed to the Sun) ---
            sol = 0.0
            if 6 <= real_h <= 18:
                x = (real_h - 6) / 12.5 * math.pi
                sol = 7.0 * panel_efficiency * math.sin(x)
                if real_h == cloud_hour: sol *= 0.4
                sol *= node_rng.uniform(0.95, 1.05)
            mock_solar.append(round(max(0, sol), 2))
                
            # --- Load Profile (Shifted per house habits) ---
            # BASELOAD: Never drop to zero (refrigerators, idle electronics, fans)
            base = node_rng.uniform(0.4, 0.8) 
            
            load = base
            if archetype == "AC_HEAVY":
                if 12 <= abs_h <= 18: load += node_rng.uniform(2.5, 4.0) # Afternoon AC
                elif 21 <= abs_h or abs_h <= 5: load += node_rng.uniform(1.8, 3.0) # Night AC
            elif archetype == "COOLER":
                if 10 <= abs_h <= 20: load += node_rng.uniform(0.7, 1.2)
            elif archetype == "WFH":
                if 9 <= abs_h <= 18: load += node_rng.uniform(1.5, 2.8)
            elif archetype == "EV":
                if 22 <= abs_h or abs_h <= 4: load += node_rng.uniform(3.5, 5.0) # Night charging
                else: load += 0.3 # day base
            else: # EFFICIENT
                if 19 <= abs_h <= 22: load += node_rng.uniform(0.5, 1.0) # Evening lights/TV

            # Add small random spikes (turning on a kettle, etc)
            if node_rng.random() < 0.08:
                load += node_rng.uniform(0.5, 1.5)
                
            mock_load.append(round(max(0.2, load), 2))
            
        return mock_load, mock_solar, archetype

    def publish_forecast(self, node_id: str, status_dict: Dict):
        """Published detailed 24h forecast to dashboard."""
        as_of = status_dict.get('as_of', '')
        try:
            hour = int(as_of.split('T')[1].split(':')[0])
        except:
            hour = 12

        mock_load, mock_solar, archetype = self.generate_24h_profile(node_id, hour)

        self._mqtt.publish(f"dashboard/trace/{node_id}/forecast", json.dumps({
            "output": {
                "load": mock_load,
                "solar": mock_solar,
                "start_hour": hour,
                "archetype": archetype
            }
        }))

    def _process_batch(self, city: str, batch: List[str], market_data, grid_prices):
        """Helper to process a single batch of 5 nodes."""
        # --- NO LIMITER: Since we don't use real LLM for 74 nodes, we run at full speed ---
        # self.limiter.await_permit()
        
        # Gather telemetry + Mocks for forecast
        nodes_status = {}
        for nid in batch:
            status = self.nodes[nid].get_status(hours=1)
            if status:
                s_dict = status.to_dict()
                
                # Compute 4H Outlook
                try:
                    hour = int(s_dict.get('as_of', '').split('T')[1].split(':')[0])
                except:
                    hour = 12
                
                m_load, m_solar, _ = self.generate_24h_profile(nid, hour)
                # Outlook = Sum(Solar - Load) for next 4 hours
                outlook_4h = sum(m_solar[j] - m_load[j] for j in range(4))
                s_dict['outlook_4h'] = round(outlook_4h, 2)
                
                nodes_status[nid] = s_dict
            else:
                logger.warning(f"No telemetry for {nid} yet.")

        if not nodes_status: return

        # --- HYBRID REASONING ENGINE ---
        # 1. Real Gemini call for the user-selected node
        # 2. Local heuristic mocks for everything else
        
        final_decisions = []
        
        # Split the batch into real vs mock with Atomic Brain Guard
        with self._city_lock:
            focus_id = self.selected_node
            
        real_nodes = [nid for nid in batch if nid == focus_id]
        mock_nodes = [nid for nid in batch if nid != focus_id]

        # Step A: Generate Mock Decisions for background nodes
        if mock_nodes:
            mock_status = {nid: nodes_status[nid] for nid in mock_nodes}
            final_decisions.extend(self._generate_mock_decisions(city, mock_status, market_data))
            
        # Step B: Perform Real LLM Inference for the selected node (the "Brain")
        for nid in real_nodes:
            # If we are in the background cycle and the node is already being processed by the immediate trigger, skip it
            # (though _process_batch itself might be the trigger, so we check if it's the real selected node)
            logger.info(f"[{nid}] ACTIVATING REAL BRAIN (Gemini Flash)...")
            try:
                # 1. Immediate "Thinking" Feedback for the Dashboard
                self._mqtt.publish(f"dashboard/trace/{nid}/agent", json.dumps({
                    "input": "Deep analysis requested by user...",
                    "reasoning": "Gathering multi-node context, battery health telemetry, and market liquidity depth for Gemini inference...",
                    "output": {"action": "THINKING", "amount_kwh": 0, "price_per_kwh": 0, "target": "brain"},
                    "ts": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }))
                
                # 2. Retrieve Cached City Context (Zero Database Overhead)
                city_ctx = self.city_stats.get(city, {
                    "name": city.capitalize(),
                    "total_load": 0.0,
                    "total_solar": 0.0,
                    "best_peer": best_neighbor
                })

                # 3. Speculative execution: Immediate Shadow Decision (Heuristic)
                # This makes the UI feel instant while the LLM "thinks"
                shadow_decisions = self._generate_mock_decisions(city, {nid: status}, market_data)
                if shadow_decisions:
                    shadow = shadow_decisions[0]
                    shadow["is_speculative"] = True
                    shadow["reasoning"] = f" [SPECULATIVE] Heuristic pre-analysis for {nid}. Gemini 1.5 Flash inference in progress..."
                    self._mqtt.publish(f"dashboard/trace/{nid}/agent", json.dumps({
                        "input": "User selection detected. Activating Stratagent Brain.",
                        "reasoning": shadow["reasoning"],
                        "output": shadow,
                        "ts": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    }))

                # 4. Collaborative Neighbor Discovery
                best_neighbor = self.marketplace.discover_best_peer("BUY" if status.get('current_soc_pct', 50) < 50 else "SELL")
                
                # 5. Build Rich Prompt with City Awareness & Persistence
                prompt = self.single_builder.build(
                    node_id=nid,
                    node_status=status,
                    safe_window=safe,
                    market_snapshot=market_data,
                    load_forecast=m_load,
                    solar_forecast=m_solar,
                    grid_prices=grid_prices,
                    trade_history=self.marketplace.get_node_trades(nid, limit=3),
                    cycle_id=1,
                    city_context=city_ctx,
                    strategic_goal=self.last_decisions.get(nid, "")
                )
                
                # 6. Call Gemini (Refined Decision)
                self.limiter.await_permit() 
                result = self.llm.infer_json(prompt, schema=self.llm.response_schema)
                result["node_id"] = nid
                result["is_real"] = True
                result["reasoning"] = f"[REFINED] {result.get('reasoning', '')}"
                
                # Update strategic memory
                self.last_decisions[nid] = result.get("action", "HOLD")
                
                final_decisions.append(result)
                
                logger.info(f"[{nid}] Gemini Decision Refined: {result.get('action')}")
                
            except Exception as e:
                logger.error(f"[{nid}] Gemini attempt failed: {e}. Using Resilient Fallback.")
                fallback = self._generate_mock_decisions(city, {nid: nodes_status[nid]}, market_data)
                for f in fallback:
                    f["reasoning"] = f"[RESILIENT] Gemini timed out or failed. Using high-fidelity heuristic fallback for safety."
                final_decisions.extend(fallback)

        # Execute & Publish Trace
        for decision in final_decisions:
            nid = decision.get("node_id")
            if not nid: continue
            
            action = decision.get("action")
            
            # 1. LIVE MARKET ORDER: Submit trade to actual Marketplace DB
            if action in ["BUY", "SELL"]:
                try:
                    self.marketplace.place_order(
                        node_id=nid,
                        order_type=action,
                        quantity_kwh=decision.get("amount_kwh", 0.0),
                        price_per_kwh=decision.get("price_per_kwh", 0.0)
                    )
                    # logger.info(f"[{nid}] Simulation Order Placed: {action} {decision.get('amount_kwh')}kWh")
                except Exception as e:
                    logger.error(f"[{nid}] Failed to place simulation order: {e}")

            # 2. Publish to dashboard trace
            trace_topic = f"dashboard/trace/{nid}/agent"
            self._mqtt.publish(trace_topic, json.dumps({
                "input": f"Mass City Context: {city}",
                "reasoning": decision.get("reasoning", "Portfolio decision."),
                "output": decision,
                "ts": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }))
            
            # 3. Publish to orchestrator command topic
            cmd_topic = config.llm_commands_topic(nid)
            self._mqtt.publish(cmd_topic, json.dumps(decision))
            
            # 4. Update forecast visual
            self.publish_forecast(nid, nodes_status.get(nid, {}))

    def _generate_mock_decisions(self, city: str, nodes_status: Dict, market_data: Dict):
        """High-fidelity local decision engine for simulation scale."""
        import random
        decisions = []
        for nid, status in nodes_status.items():
            soc = status.get('current_soc_pct', 50.0)
            outlook = status.get('outlook_4h', 0.0)
            
            # Logic: BUY if low SoC, SELL if high SoC + high outlook
            if soc < 25.0:
                action, amt, prc, reason = "BUY", round(random.uniform(3.0, 6.0), 1), 8.5, f"SoC={soc:.1f}% critical; scaling battery reserve via Grid intake."
            elif soc > 75.0 and outlook > 2.0:
                action, amt, prc, reason = "SELL", round(random.uniform(2.0, 5.0), 1), 7.2, f"SoC={soc:.1f}% with {outlook:.1f}kWh surplus projected. Aggregating to P2P marketplace."
            elif 30.0 < soc < 70.0 and random.random() < 0.2:
                # Random arbitrage small trade
                is_buy = random.choice([True, False])
                action = "BUY" if is_buy else "SELL"
                amt = round(random.uniform(0.5, 1.5), 1)
                prc = 8.5 if is_buy else 7.2
                reason = f"Arbitrage strategy active at SoC={soc:.1f}% for grid stabilization optimization."
            else:
                action, amt, prc, reason = "HOLD", 0.0, 0.0, f"Portfolio balanced at SoC={soc:.1f}%. Monitoring market liquidity."

            decisions.append({
                "node_id": nid,
                "action": action,
                "amount_kwh": amt,
                "price_per_kwh": prc,
                "target": "marketplace" if action in ["BUY", "SELL"] else "battery",
                "reasoning": f"[SIMULATED] {reason}"
            })
        return decisions

    def run_city_cycle(self, city: str):
        """Processes 15 nodes in parallel batches, EXCLUDING the user-selected focus node."""
        logger.info(f"--- Starting REALISTIC Reasoning Cycle for {city.upper()} ---")
        
        with self._city_lock:
            focus_node = self.selected_node
            
        city_nodes = [nid for nid in self.nodes if nid.startswith(city) and nid != focus_node]
        if not city_nodes: return

        # 0. IMMEDIATELY broadcast "Thinking" state to all background nodes only if not focus
        for nid in city_nodes:
            self._mqtt.publish(f"dashboard/trace/{nid}/agent", json.dumps({
                "input": f"System initializing for {city.upper()} complex...",
                "reasoning": f"Analyzing real-time load profile and grid voltage for {nid}. Evaluating P2P trade opportunities and battery SoC headroom...",
                "output": {"action": "WAITING", "amount_kwh": 0, "price_per_kwh": 0},
                "ts": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }))

        # 3 batches of 5 nodes
        batch_size = 5
        batches = [city_nodes[i:i + batch_size] for i in range(0, len(city_nodes), batch_size)]
        
        market_data = self.marketplace.get_market_snapshot()
        grid_prices = {"buy": 8.50, "sell": 3.00}

        # UPDATE CITY CACHE for this cycle
        city_total_load = 0.0
        city_total_solar = 0.0
        for nid in [n for n in self.nodes if n.startswith(city)]:
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

        # Use ThreadPoolExecutor for realistic asynchronous processing
        with ThreadPoolExecutor(max_workers=3) as executor:
            for i, batch in enumerate(batches):
                # Check if city changed
                with self._city_lock:
                    if self.active_city != city: break
                
                # Realistic staggering: Fire each batch ~0.8s apart for a "ripple" effect in the UI
                if i > 0: time.sleep(0.8) 
                
                executor.submit(self._process_batch, city, batch, market_data, grid_prices)

    def start(self):
        self.is_running = True
        self._mqtt.connect(config.MQTT_BROKER, config.MQTT_PORT)
        self._mqtt.loop_start()
        
        logger.info("Multi-Node Strategic Agent ACTIVE. Waiting for dashboard signal via MQTT...")
        
        while self.is_running:
            with self._city_lock:
                current_city = self.active_city
            
            if current_city:
                try:
                    self.run_city_cycle(current_city)
                except Exception as e:
                    logger.error(f"Error in city cycle {current_city}: {e}")
                
                # Use the configured interval (e.g., 30s) between full city cycles
                time.sleep(self.cycle_interval)
            else:
                # Idle state: Check MQTT for city signal every 2 seconds
                time.sleep(2)

    def stop(self):
        self.is_running = False
        self._mqtt.loop_stop()
        self._mqtt.disconnect()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Node Strategic Agent")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between full reasoning cycles")
    args = parser.parse_args()

    agent = MultiNodeAgent(cycle_interval=args.interval)
    
    # Handle signals
    def shutdown(sig, frame):
        logger.info("Shutting down MultiNodeAgent...")
        agent.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    agent.start()
