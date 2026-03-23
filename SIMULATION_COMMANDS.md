# ⚡ Microgrid Simulation - Execution Guide

Follow these steps to run the full end-to-end microgrid simulation. Each component should be run in its own separate terminal.

---

## 🛠️ Prerequisites

1.  **Python Environment**: Ensure you are in your virtual environment.
    ```powershell
    # Windows (if using .venv)
    .\.venv\Scripts\activate
    ```
2.  **API Keys**: Ensure your `.env` file contains a valid `GEMINI_API_KEY`.
    ```bash
    # Verify API connectivity
    python test_gemini_api.py
    ```

---

## 🚀 Running the Simulation (Order Matters)

### 1️⃣ Terminal 1: The Communication Hub (Broker)
Starts the MQTT Broker (Central Post Office) with WebSocket support (Port 9001).
```powershell
.\.venv\Scripts\python.exe -m edge.broker
```

### 2️⃣ Terminal 2: The Librarian (Edge Node)
Starts the data ingestion layer. Subscribes to telemetry and saves it to local SQLite databases.
```powershell
# Start all 5 home nodes (delhi_01, noida_01, etc.)
.\.venv\Scripts\python.exe -m edge.run_node
```

### 3️⃣ Terminal 3: The Sensors (Simulator)
Generates synthetic solar, load, and battery telemetry for all 5 homes.
```powershell
# For a fast demo (1 second real-time = 15 minutes simulation):
.\.venv\Scripts\python.exe -m edge.run_simulator --interval 10 --step 15
```

### 4️⃣ Terminal 4: The Marketplace (P2P Exchange)
Starts the FastAPI energy trading floor.
```powershell
.\.venv\Scripts\uvicorn.exe marketplace.main:app --host 0.0.0.0 --port 8000
```

### 5️⃣ Terminal 5: The Safety Brain (Tactical Orchestrator)
Enforces industrial state-machine rules and safety buffers. Use a specific node ID.
```powershell
.\.venv\Scripts\python.exe -m orchestrator.run_orchestrator --node-id delhi_01
```

### 6️⃣ Terminal 6: The Strategic AI (Strategic Agent)
Launches the LLM-driven agent that makes energy trading and battery scheduling decisions.
```powershell
.\.venv\Scripts\python.exe -m strategic_agent.run_agent --node-id delhi_01
```

---

## 📊 Monitoring & Validation

### 🌐 Dashboard (Real-time View)
Run this command to open the live telemetry, AI reasoning, and safety state in your default browser:
```powershell
start dashboard\index.html
```

### ✅ Automated Tests
Run the unit test suite to verify the safety logic independently of the simulation:
```powershell
.\.venv\Scripts\python.exe -m pytest -v test/test_orchestrator.py
```

---

## 💡 Quick Summary of Node IDs
- `delhi_01` (Hot semi-arid)
- `noida_01` (Hot semi-arid)
- `gurugram_01` (Hot semi-arid)
- `chandigarh_01` (Humid subtropical)
- `dehradun_01` (Humid subtropical / Hilly)
