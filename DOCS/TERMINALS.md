# ⚡ Intelligent Microgrid 7-Terminal Debugging Setup

When debugging the 75-node system, run each component in its own terminal window. This prevents log tangling, avoids port conflicts, and makes issues easier to isolate.

For the realistic pacing runbook, see:
[TERMINALS_REALISTIC.md](TERMINALS_REALISTIC.md)

## 🧹 Preparation (Run First)

Start from a clean slate so battery states and market wallets are consistent.

```bash
source .venv/bin/activate && python reset_state.py
```

---

## 🖥 The 7 Terminals

Open 7 separate terminal tabs in VS Code.

### 1️⃣ Terminal 1: The Broker
The backbone of the system. Routes MQTT traffic between all simulated sensors, nodes, and orchestrators.
```bash
source .venv/bin/activate && python -m edge.broker
```

### 2️⃣ Terminal 2: The Marketplace
The FastAPI double-auction energy trading floor. Provides API routes for nodes to buy and sell energy.
```bash
source .venv/bin/activate && uvicorn marketplace.main:app --host 0.0.0.0 --port 8000
```

### 3️⃣ Terminal 3: Edge Ingestion Data Layer
Handles incoming MQTT payloads from all 75 nodes and logs them locally to data/edge/ SQLite DBs.
```bash
source .venv/bin/activate && python -m edge.run_node
```

### 4️⃣ Terminal 4: The Physics Simulator
Realistic pacing: 1s real-time = 1m simulation step.
```bash
source .venv/bin/activate && python -m edge.run_simulator --interval 1 --step 1
```

### 5️⃣ Terminal 5: The Tactical Orchestrator
The industrial safety governor. Watch FSM transitions (GRID_CONNECTED → EMERGENCY → P2P_TRADING).
```bash
source .venv/bin/activate && python -m orchestrator.run_orchestrator --node-id delhi_01
```

### 6️⃣ Terminal 6: The AI Agent
The Strategic LLM brain. Watch live reasoning decisions (BUY X kWh at Y price).
```bash
source .venv/bin/activate && python -m strategic_agent.run_agent --node-id delhi_01
```

### 7️⃣ Terminal 7: The Dashboard
The frontend React command center. Must be run independently (Node.js does not use Python venv).
```bash
cd dashboard && npm run dev
```

Visit: http://localhost:5173
