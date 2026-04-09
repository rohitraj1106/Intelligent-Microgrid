# Intelligent Microgrid — Full System Audit & Fix Plan

## Summary

A complete code audit of all 7 services was performed. The core problem is a **chain of data pipeline failures** where issues compound: the Simulator sends static 0% SoC data → the Edge Node stores it → the Agent reads 0% → the LLM makes illogical "BUY when bankrupt" decisions. This plan fixes the root causes in dependency-first order.

---

## 🔴 Critical Bugs Found (will crash or produce nonsense)

### BUG 1: Simulator SoC Resets to 0% on Every Restart
**File:** `edge/simulator.py` → `_generate_reading()`  
**Root Cause:** The initial SoC is correctly set in `__init__` (e.g., 85%), but when `reset_state.py` is run, the SQLite databases are deleted but the **Python process restarts fresh**. The opening SoC ranges (12–95%) only take effect on the very first tick. The old database values no longer exist to feed back into the running simulation so the physics calculation always starts from whatever the initial random SoC was. **After one full drain cycle, if you restart without a fresh sim process, SoC gets stuck at 0 permanently.**  
**Fix:** Add a simulated "BUY" energy injection after the battery drains below 5% so it auto-recovers, making the simulation loop perpetually.

---

### BUG 2: Prompt Builder Sends 0% SoC When Data is Not Yet Ingested
**File:** `edge/database.py` → `get_summary()`, `strategic_agent/agent.py`  
**Root Cause:**  `get_summary()` returns `None` if no data exists → `agent.py` skips the cycle with "Waiting for telemetry" and publishes `snapshot_soc: None`. The orchestrator then defaults `current_soc = 0.0` in `_handle_llm_command`. Even after data arrives, the **very first cycle** uses stale (or None) SoC.  
**Fix:** Add a `time.sleep(10)` startup delay in `run_agent.py` before the first cycle, and log a clear `[WAITING FOR DATA]` message. The Agent is currently started in Terminal 6 immediately after Terminal 5, but the EdgeNode inside it needs time to ingest its first telemetry batch from the Simulator.

---

### BUG 3: Marketplace `get_market_snapshot()` Returns Wrong Schema
**File:** `strategic_agent/negotiation.py` → `get_market_snapshot()`  
**Root Cause:** Calls `GET /orders` but the `prompt_builder.py` expects keys `best_buy_price` and `best_sell_price` in the response. The `/orders` endpoint likely returns a list of order objects `[{...}, {...}]`, not a stats dict. So `market_snapshot.get('best_buy_price', 'N/A')` always returns `'N/A'`.  
**Fix:** Change `get_market_snapshot()` to call the correct `/stats` endpoint which returns aggregate pricing, OR add a local price extractor that iterates the order list and finds the best bid/ask.

---

### BUG 4: LLM Buys Energy But SoC Never Increases (Trade is Fake)
**Files:** `orchestrator/orchestrator.py` → `_handle_llm_command()`, `edge/simulator.py`  
**Root Cause:** When the LLM issues a BUY command, the orchestrator confirms the trade but **the `simulator.py` independently calculates SoC physics from solar/load alone**. There is no feedback channel from the orchestrator back to the simulator. So after a BUY of 6kWh, the SoC on the dashboard stays at 2% instead of going to ~10%. The trade is cosmetically logged but physically has zero effect.  
**Fix:** Add a `trade_injection` queue to the simulator. When the Orchestrator completes a BUY, it publishes a special MQTT message to `microgrid/{node_id}/trade_inject`. The Simulator listens to this topic and adds the purchased kWh to the node's SoC immediately in the next tick.

---

### BUG 5: Agent Reasoning Cycle Starts Before Safe Window Arrives
**File:** `strategic_agent/agent.py` → `run_cycle()` line 195  
**Root Cause:** `self._last_safe_window` is an empty `{}` on the very first cycle because the MQTT subscription to `safe_window_topic` hasn't received any data yet (the Orchestrator publishes on each telemetry tick, and the Agent just started). So the prompt builder sends `max_buy_p2p_kw: 0.0` and `can_trade: False` (defaults) to the LLM for the first 1–2 cycles. The LLM correctly reads "can_trade=False" and outputs HOLD, but does so for the wrong reason.  
**Fix:** Add a 15-second pre-flight wait in `run_agent.py` before `agent.start()`, and ensure `_last_safe_window` has sensible defaults with `can_trade=True`.

---

## 🟠 Logic Flaws Found (will produce bad decisions)

### FLAW 1: LLM BUYs Energy From a Market That Has No SELL Orders
**Files:** `strategic_agent/negotiation.py`, `orchestrator/orchestrator.py`  
**Root Cause:** When a node wants to BUY P2P energy, there must be a Seller. But the system only runs the Agent for `delhi_01` — not for all 75 nodes. So there are 0 sell orders on the marketplace at any given time. The Agent places a BUY order but it never matches because there's no counterparty.  
**Fix:** Add a **Market Maker** module. On a fixed interval, it automatically seeds 2–3 synthetic SELL orders at fair market price (₹5.50/kWh) from a `grid_reserve_node`. This means the delhi_01 BUY will always match immediately, making the simulation feel real.

---

### FLAW 2: Reasoning Prompt Gives "MIDDAY_SOLAR_SURPLUS" Context But Agent Running at 7PM
**File:** `strategic_agent/prompt_builder.py`, `edge/simulator.py`  
**Root Cause:** The simulator was changed to start at 1PM sim time. But real UTC time (which the agent uses for `as_of`) vs sim time (what the database stores) diverge. The `node_data.get('as_of')` returns the **simulator's internal time string**, but there's no guarantee this is actually being stored properly in the SQLite DB. If it falls back to UTC, the "hour" calculation in `prompt_builder` will be wrong for your 5:30PM IST timezone.  
**Fix:** Ensure the `as_of` field in `NodeSummary` always reflects the **simulation timestamp** (from the simulator clock), not UTC wall-clock time.

---

### FLAW 3: EV Charging Spike (5% chance every tick) Causes Instant EMERGENCY
**File:** `edge/simulator.py` → `_simulate_load_kw()`  
**Root Cause:** There is a 5% random chance every tick of adding 6–8.5 kW EV load. With 75 nodes and ticks every 3 seconds, this fires ~3–4 times per minute across the cluster. A node at 25% SoC that suddenly gets a +8kW spike will drain faster than the safety buffer can handle and jump directly to EMERGENCY before the LLM can react.  
**Fix:** Reduce EV spike probability from 5% to 1%, and cap the spike magnitude at 3.5kW to be more realistic.

---

### FLAW 4: Prompt Instruction Says "BUY if SoC < 30%" but Safety Buffer Blocks BUY at SoC < 10%
**File:** `strategic_agent/prompt_builder.py`, `orchestrator/safety_buffer.py`  
**Root Cause:** Safety buffer blocks SELL/DISCHARGE below 10% SoC but does NOT block BUY below 10%. Actually this is fine for BUY. But the prompt says "BUY if EVENING_PEAK_DRAIN and SoC < 30%" — this creates a conflict: if SoC is between 10–30%, the prompt forcibly triggers BUY on every single cycle. With a 15-second interval, the LLM will place 4 BUY orders per minute all saying "critical SoC". Economically illogical.  
**Fix:** Update the prompt instructions to only suggest BUY when SoC < 20% AND net_energy is negative.

---

## 🟡 Presentation Polish Issues

### POLISH 1: Dashboard Footer Says "Gemini 3.1 Pro" (Incorrect)
**File:** `dashboard/src/App.jsx` line 58  
**Fix:** Update to "Dual-AI: Gemini Flash + Llama-3.3-70B" to match the actual implementation.

### POLISH 2: All 75 Nodes Show 0% Until First Telemetry Arrives
**File:** `dashboard/src/components/CityMap.jsx`  
**Fix:** Show a loading skeleton/shimmer instead of "0%" for nodes that haven't received data yet.

### POLISH 3: "Reasoning Chain" Types Even When LLM Says "Waiting for Signal"
**File:** `dashboard/src/components/DeepDivePanel.jsx`  
**Fix:** Only start the typing animation when `traceData.agent.reasoning` is a real, non-null decision (not empty or "Waiting").

---

## Implementation Order (Dependency-First)

| Priority | Fix | File(s) | Impact |
|----------|-----|---------|--------|
| 🔴 1 | Add 15s startup delay to Agent | `strategic_agent/run_agent.py` | Fixes 0% SoC on first cycle |
| 🔴 2 | Fix market snapshot endpoint | `strategic_agent/negotiation.py` | Fixes N/A prices in prompt |
| 🔴 3 | Add Trade Injection feedback loop | `edge/simulator.py` + `orchestrator/orchestrator.py` | Makes BUY physically meaningful |
| 🔴 4 | Add Market Maker seeder | `marketplace/main.py` (or new `market_maker.py`) | Allows BUY orders to actually match |
| 🟠 5 | Fix EV spike probability/magnitude | `edge/simulator.py` | Stops random EMERGENCY cascades |
| 🟠 6 | Fix prompt BUY condition threshold | `strategic_agent/prompt_builder.py` | Stops repetitive illogical BUYs |
| 🟡 7 | Fix dashboard footer text | `dashboard/src/App.jsx` | Presentation quality |
| 🟡 8 | Fix node loading skeleton | `dashboard/src/components/CityMap.jsx` | Presentation quality |

---

## Verification Plan

After fixes are applied:
1. Run `python reset_state.py` for a clean slate.
2. Start all 7 terminals in order, wait for each `✅ [READY]` message.
3. Open dashboard at `http://localhost:5173`.
4. **Expected:** Within 30 seconds, city cards show mixed SoC levels (not all 0%). Within 60 seconds, AI Verdict shows `BUY` or `SELL` with a real number (not 0kWh). Within 90 seconds, a node SoC should increase slightly after a BUY trade.
5. Let it run for 5 minutes — verify no EMERGENCY cascade, no black screen, and at least 3 different reasoning sentences.
