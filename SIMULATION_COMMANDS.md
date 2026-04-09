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
3.  **Marketplace DB Mode (Strict Stage Gate)**:
    - Preferred: dedicated PostgreSQL container via environment variable.
    - Fallback: SQLite (dev only).
    ```powershell
    # Dedicated container for this project (separate from other DB containers)
    docker start microgrid-db
    docker exec microgrid-db pg_isready -h localhost -p 5432

    # PowerShell env var for this terminal session
    $env:MARKETPLACE_DATABASE_URL = "postgresql+psycopg://microgrid:microgrid_pass@localhost:5433/microgrid_market"
    ```

---

## 🚀 Running the Simulation (Order Matters)

### 0️⃣ Terminal 0: Database (Dedicated PostgreSQL)
```powershell
docker start microgrid-db
docker exec microgrid-db pg_isready -h localhost -p 5432
```

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
# For aligned demo cadence (15 seconds real-time = 15 minutes simulation):
.\.venv\Scripts\python.exe -m edge.run_simulator --interval 15 --step 15
```

### 4️⃣ Terminal 4: The Marketplace (P2P Exchange)
Starts the FastAPI energy trading floor.
```powershell
$env:MARKETPLACE_DATABASE_URL = "postgresql+psycopg://microgrid:microgrid_pass@localhost:5433/microgrid_market"
.\.venv\Scripts\python.exe -m uvicorn marketplace.main:app --host 0.0.0.0 --port 8000
```

### 4A️⃣ Seed Marketplace Nodes (One-time per reset)
Registers marketplace nodes and writes API keys to `node_keys.json`.
```powershell
.\.venv\Scripts\python.exe -m marketplace.seed_nodes
```

### 4B️⃣ Run 7-10 Node Trading Pilot (Stage-Gate Check)
Runs randomized multi-round order placement for selected seeded nodes and prints summary KPIs.
```powershell
# Recommended demo gate: 10 nodes, 3 rounds each
$env:MARKETPLACE_DATABASE_URL = "postgresql+psycopg://microgrid:microgrid_pass@localhost:5433/microgrid_market"
.\.venv\Scripts\python.exe -m marketplace.pilot_runner --nodes 10 --rounds 3 --timeout 10
```

### 5️⃣ Terminal 5: The Safety Brain (Tactical Orchestrator)
Enforces industrial state-machine rules and safety buffers. Use a specific node ID.
```powershell
.\.venv\Scripts\python.exe -m orchestrator.run_orchestrator --node-id delhi_01
```

### 6️⃣ Terminal 6: The Strategic AI (Strategic Agent)
Launches the LLM-driven agent that makes energy trading and battery scheduling decisions.
```powershell
.\.venv\Scripts\python.exe -m strategic_agent.run_agent --node-id delhi_01 --interval 15
```

---

## 📊 Monitoring & Validation

### 🌐 Dashboard (Real-time View)
Serve the dashboard via HTTP (recommended) so browser API requests are not blocked:
```powershell
.\.venv\Scripts\python.exe -m http.server 8787 --directory dashboard
```

Keep this terminal running. Open a new terminal and launch pages with:

```powershell
Start-Process "http://localhost:8787/index.html"
Start-Process "http://localhost:8787/marketplace.html"
```

Then open these pages in your browser:
```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8787/index.html | Select-Object -ExpandProperty StatusCode
```

### ✅ Automated Tests
Run the unit test suite to verify the safety logic independently of the simulation:
```powershell
.\.venv\Scripts\python.exe -m pytest -v test/test_orchestrator.py
```

Run all project tests (including marketplace regression tests):
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Quick API checks for strict stage endpoints:
```powershell
curl http://localhost:8000/health
curl http://localhost:8000/stats
curl http://localhost:8000/metrics
curl http://localhost:8000/orders
```

---

## 🏁 When Does It End?

Different terminals have different completion behavior:

- **Long-running terminals (manual stop with Ctrl+C):**
    - Terminal 1 (broker)
    - Terminal 2 (edge.run_node)
    - Terminal 3 (edge.run_simulator)
    - Terminal 4 (marketplace API)
    - Terminal 5 (orchestrator)
    - Terminal 6 (strategic agent)

- **Finite terminals (auto-finish):**
    - Terminal 4A (`seed_nodes`) ends after node registration completes
    - Terminal 4B (`pilot_runner`) ends after configured rounds complete
    - Tests (`pytest`) end after test run
    - API checks (`curl`) end after response

### Recommended Demo End Condition (Clear Stop Rule)

Call the demo "complete" when all are true:

1. `GET /health` returns `200`.
2. `seed_nodes` finishes successfully.
3. `pilot_runner --nodes 10 --rounds 3 --timeout 10` completes with:
     - `Order placement failures : 0`
     - `Orders matched > 0`
     - `Trades generated > 0`
4. `GET /stats` shows non-zero `total_trades` and `total_volume_kwh`.

At that point, capture screenshots / terminal output and stop long-running terminals with `Ctrl+C`.

---

## 💡 Quick Summary of Node IDs
- `delhi_01` (Hot semi-arid)
- `noida_01` (Hot semi-arid)
- `gurugram_01` (Hot semi-arid)
- `chandigarh_01` (Humid subtropical)
- `dehradun_01` (Humid subtropical / Hilly)
