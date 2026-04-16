# ⚡ Distributed Intelligent Microgrid: Grand Technical Repository Guide

This document is a high-depth technical exploration of the Honeybee ecosystem. It details the internal logic, mathematical models, data schemas, and synchronization protocols that enable a 75-node autonomous energy grid.

---

## 1. The Data Foundation (Edge Layer)
Honeybee uses a "Split-Data" architecture to ensure privacy and low-latency local processing.

### 🗄️ Node-Local SQLite Schema
Each node maintains a private SQLite database (`edge/models.py`) to store granular sensor telemetry.
*   **Table**: `telemetry`
*   **Fields**: `timestamp (TEXT)`, `voltage_v (REAL)`, `current_a (REAL)`, `power_solar_kw (REAL)`, `power_load_kw (REAL)`, `soc_pct (REAL)`, `battery_power_kw (REAL)`.
*   **Indexing**: Uses a composite index `idx_telemetry_node_ts` on `(node_id, timestamp DESC)` for rapid historical windowing.

### 🛡️ Privacy Gate: `NodeSummary`
Granular data *never* leaves the node. The system only exports a `NodeSummary` object to the AI layers:
*   **Average Metrics**: Computed over a 1-hour rolling window.
*   **Net Energy**: `(AVG Solar - AVG Load)`.
*   **Intent Flag**: Derived logic stating `SURPLUS`, `DEFICIT`, or `BALANCED`.

---

## 2. Intelligence: The "Deep-and-Wide" Architecture
To balance computational cost with local intelligence, Honeybee employs a hybrid reasoning model.

### 📉 Wide Layer (Multi-Agent Heuristics)
*   **Process**: `strategic_agent.multi_agent_runner`
*   **Scale**: Processes 74 nodes.
*   **Logic**: Uses **Batch Reasoning**. Grouping 5 nodes into a single LLM prompt drastically reduces API latency and cost while maintaining situational awareness of the "local cluster."

### 🧠 Deep Layer (Dedicated Gemini Core)
*   **Process**: `strategic_agent.run_agent --node-id delhi_01`
*   **Scale**: Isolated "Showcase" node.
*   **Logic**: Dedicated per-cycle reasoning. Features a **Circuit Breaker** pattern: if the LLM fails 3 times consecutively, it "trips" and enters a 60s cooldown, falling back to safe `HOLD` actions.

---

## 3. Tactical Synchronization (Protocol Handshake)
Trading energy isn't just a database update; it's a multi-step protocol handshake between physical nodes.

### 🤝 P2P Handshake Sequence
When a trade is initiated between two nodes (`Node A` and `Node B`):
1.  **Request**: `Node A` publishes to `microgrid/NodeB/handshake/request`.
2.  **Validate**: `Node B`'s Tactical Orchestrator checks its `SafetyBuffer` and Current FSM State.
3.  **Response**: `Node B` replies with `ACCEPTED` or `REJECTED` via `microgrid/NodeA/handshake/response`.
4.  **Execute**: If accepted, both nodes publish `apply_trade` commands to their respective simulators simultaneously.

---

## 4. Market Microstructure (Engine Details)
The marketplace runs a **Continuous Double Auction (CDA)** with specific regional rules.

### 🏛️ Clearing & Matching Logic
*   **MIDPOINT_CLEARING**: If a Buyer bids ₹7.00 and a Seller offers ₹5.00, the trade executes at ₹6.00.
*   **PROXIMITY_BIAS**: The matching engine (`OrderRepository.get_pending_counterparties`) calculates a `distance_tier`. A seller will always match with a same-city buyer before an out-of-city buyer, even if the latter bids slightly higher, to minimize simulated transmission loss.

### 📊 Leaderboard & Wallets
The system tracks simulated currency (`balance_inr`) in a `Wallet` table. Settlements are generated immediately after a trade execution, updating the `total_earned` and `total_spent` fields for each node.

---

## 5. Safety FSM & Guardrails
The Orchestrator's `MicrogridFSM` is a rigid state machine that prevents physical equipment damage.

| State | Transition Signal | Action |
| :--- | :--- | :--- |
| **GRID_CONNECTED** | `grid_failed` | Isolate circuits, enter ISLANDED. |
| **ISLANDED** | `soc_pct < 15%` | Shut down non-essential loads, enter EMERGENCY. |
| **EMERGENCY** | `soc_pct > 25%` | Recover to ISLANDED or GRID_CONNECTED. |
| **P2P_TRADING** | `handshake_accepted` | Lock state to prevent competing trades. |

### 🔒 Strategic Guardrails
A pre-actuation layer in the code (`StrategicAgent._apply_guardrails`) checks:
*   **Overcharge Prevention**: Rejects `BUY` commands if SoC > 98%.
*   **Deep Discharge Prevention**: Rejects `SELL` commands if SoC < 20%.

---

## 6. Communications Hierarchy (MQTT Matrix)
Sub-second reliability is achieved through a multi-topic hierarchy.

| Prefix | Sub-Topic | Payload Type | QoS |
| :--- | :--- | :--- | :--- |
| `microgrid/{id}/` | `telemetry` | `TelemetryReading` JSON | 0 |
| `microgrid/{id}/` | `llm_commands` | `AgentCommand` JSON | 1 |
| `microgrid/{id}/` | `safe_window` | `SafeWindow` JSON | 0 |
| `dashboard/` | `trace/{id}/{L}` | Full Trace JSON | 0 |

**Multiplexing**: The `MultiOrchestrator` uses a single MQTT client to subscribe to all 75 node topics, routing messages internally to lightweight `TacticalOrchestrator` instances to maintain a low CPU footprint.

---

## 🔗 Technical Code Map

*   **Simulation Core**: `edge/simulator.py` (Math-heavy solar/load/battery simulation).
*   **Data Persistence**: `edge/node.py` (SQLite management).
*   **Trading Engine**: `marketplace/engine.py` (CDA Logic).
*   **AI Reasoning**: `strategic_agent/agent.py` (Circuit breakers, Guardrails).
*   **Safety Layer**: `orchestrator/orchestrator.py` (FSM, Handshakes).
*   **UI/Frontend**: `dashboard/src/App.jsx` (Vite, MQTT bridge).

---

<p align="center">
  <b>Built for Reliability. Designed for Autonomy.</b>
</p>
