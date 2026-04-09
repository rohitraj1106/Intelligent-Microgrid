# ⚡ Strategic 8-Terminal Showcase Setup (Deep-and-Wide)

Use this runbook for a professional video showcase. This configuration runs the **75-node grid** at scale while isolating **ONE node (delhi_01)** for a deep-dive into real-time LLM reasoning.

---

## 🧹 Preparation: The Clean Slate
Ensure all previous session data is purged to avoid stale chart values.
```bash
source .venv/bin/activate && python reset_state.py
```

---

## 🖥 Terminal Tabs Configuration

Open 8 separate terminal tabs in VS Code and label them as follows.

### 1️⃣ 🟦 Hub: MQTT Broker [KEEP ALIVE]
The central nervous system. Routes all telemetry and commands.
```bash
source .venv/bin/activate && python -m edge.broker
```

### 2️⃣ 🟪 Exchange: Marketplace [KEEP ALIVE]
The energy trading floor. Processes trades for all 5 cities.
```bash
source .venv/bin/activate && uvicorn marketplace.main:app --host 0.0.0.0 --port 8000
```

### 3️⃣ 🟩 Data: Multi-Ingestion
Ingests telemetry for **all 75 nodes** into SQLite.
```bash
source .venv/bin/activate && python -m edge.run_node
```

### 4️⃣ 🟨 Physics: Cluster Simulator
Simulates the loads/solar for **all 75 nodes** simultaneously.
```bash
source .venv/bin/activate && python -m edge.run_simulator --interval 1 --step 1
```

### 5️⃣ 💠 Safety: Tactical Governor
Runs 75 Safety FSMs simultaneously. Prevents battery damage.
```bash
source .venv/bin/activate && python -m orchestrator.multi_orchestrator_runner
```

### 6️⃣ 🤖 Grid Intelligence: Mass Simulator (WIDE)
Runs the fast, heuristic AI for 74 nodes. Powers the main React Dashboard.
```bash
source .venv/bin/activate && python -m strategic_agent.multi_agent_runner
```

### 7️⃣ 🧠 Deep Brain: Real Gemini LLM (DEEP)
Runs the **actual Gemini LLM** for the showcase node (`delhi_01`). 
```bash
source .venv/bin/activate && python -m strategic_agent.run_agent --node-id delhi_01
```
*Note: This terminal shows the real "thinking" logs you can point to in your demo.*

### 8️⃣ 🖼 HUD: Dashboards
Start the React development server.
```bash
cd dashboard && npm run dev
```

---

## 🚦 Recommended Start Order
1. **Hub** → 2. **Exchange** → 3. **Data** → 4. **Physics** → 5. **Safety** → 6. **Grid Intelligence** → 7. **Deep Brain** → 8. **HUD**

---

## 🎥 Showcase Visuals Guide

### 🌟 The "Deep-and-Wide" Proof:
1.  **React Dashboard**: Select **delhi_01**. Look for the purple **"REAL-TIME LLM CORE"** badge. This proves the node is using the actual Gemini model.
2.  **Legacy Dashboard**: Open `dashboard_legacy/index.html`. It is hardcoded to `delhi_01`. Show this to explain the "Reasoning Chain" in detail.
3.  **Realism Check**: Select different nodes in the React UI. Notice how the **24h Load Vector** (red bars) has different peaks and nighttime baseloads—no more identical "zero" charts!

### 🕵️‍♂️ Troubleshooting:
- **No LLM Output on delhi_01?** Ensure Terminal 7 is running.
- **Charts look identical?** Run `python reset_state.py` and restart Terminal 4.
- **Trades not matching?** Ensure order prices offered by the LLM (Terminal 7) overlap with the market maker or other nodes.
