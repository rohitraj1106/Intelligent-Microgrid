# ⚡ 75-Node Intelligent Microgrid - Debugging Guide

Use this guide to launch each core service in a separate terminal. This isolation is highly recommended for debugging.

---

## 🛠️ Infrastructure Requirements

1.  **PostgreSQL**: Ensure Postgres is running and you have created the `microgrid_market` database.
2.  **Environment Variables**: Your `.env` must contain:
    ```env
    GEMINI_API_KEY=your_key_here
    MARKETPLACE_DATABASE_URL=postgresql://postgres:pass@localhost:5432/microgrid_market
    ```

---

## 🚀 The Launch Sequence (One Terminal Per Service)

### 1️⃣ Terminal 1: MQTT Broker (The Network)
Starts the central message exchange.
```powershell
.\.venv\Scripts\python.exe -m edge.broker
```

### 2️⃣ Terminal 2: Energy Marketplace (P2P Exchange)
Starts the Postgres-backed trading floor on Port 8000.
```powershell
.\.venv\Scripts\python.exe -m uvicorn marketplace.main:app --port 8000
```

### 3️⃣ Terminal 3: API Gateway (Frontend API Layer)
Starts the standalone gateway on Port 8100. The dashboard should call this service (not marketplace directly).
```powershell
$env:MARKETPLACE_BASE_URL="http://localhost:8000"
$env:GATEWAY_WRITE_API_KEY="demo-write-key"
.\.venv\Scripts\python.exe -m uvicorn api_gateway.main:app --port 8100
```

### 4️⃣ Terminal 4: Physics Simulator (The Sensors)
Starts the 75-node simulation engine. 
*Note: This will stay in "STANDBY" until you click a city on the dashboard.*
```powershell
.\.venv\Scripts\python.exe -m edge.run_simulator --step 15
```

### 5️⃣ Terminal 5: Multi-Orchestrator (Tactical Layer)
Starts the safety and database ingestion engine for all 75 nodes via 1 multiplexed connection.
```powershell
$env:API_GATEWAY_BASE_URL="http://localhost:8100"
$env:GATEWAY_WRITE_API_KEY="demo-write-key"
.\.venv\Scripts\python.exe -m orchestrator.multi_orchestrator_runner
```

### 6️⃣ Terminal 6: Strategic Multi-Agent (AI Layer)
Starts the Gemma 4 26B reasoning engine for city-wide intelligence.
```powershell
.\.venv\Scripts\python.exe -m strategic_agent.multi_agent_runner
```

### 7️⃣ Terminal 7: Dashboard (Frontend)
Run the Vite development server.
```powershell
cd dashboard
# Optional trace toggle. Keep true for deep-dive panel live traces.
$env:VITE_TRACE_MQTT_ENABLED="true"
$env:VITE_API_BASE_URL="http://localhost:8100"
npm run dev
```

---

## 🔍 Debugging Cheatsheet

| If you see... | Then check... |
| :--- | :--- |
| `0.0V / 0.0kW` on Dashboard | Click a city card to "wake up" Terminal 4 (Physics). |
| `Connection Refused (8000)` | Ensure Terminal 2 (Marketplace) is running and Postgres is up. |
| `Connection Refused (8100)` | Ensure Terminal 3 (API Gateway) is running and `VITE_API_BASE_URL` points to it. |
| `Rate Limit Exceeded` | Terminal 6 is limited to 14 requests/min per your Gemma key. |
| `Database is Locked` | This was fixed by Multiplexing. If it persists, restart Terminal 5. |

### API smoke tests
```powershell
Invoke-WebRequest http://localhost:8100/health
Invoke-WebRequest http://localhost:8100/api/system/health
Invoke-WebRequest "http://localhost:8100/api/market/stats?city=delhi"
Invoke-WebRequest "http://localhost:8100/api/nodes/health?city=delhi"
```

### Command API smoke tests
```powershell
$headers = @{ "X-API-Key" = "demo-write-key" }

# Pause/Resume tactical trading for one node
Invoke-RestMethod -Method Post -Uri "http://localhost:8100/api/orchestrator/commands" -Headers $headers -ContentType "application/json" -Body '{"node_id":"delhi_00","action":"stop_trading"}'
Invoke-RestMethod -Method Post -Uri "http://localhost:8100/api/orchestrator/commands" -Headers $headers -ContentType "application/json" -Body '{"node_id":"delhi_00","action":"start_trading"}'

# Reset simulator SoC to 55%
Invoke-RestMethod -Method Post -Uri "http://localhost:8100/api/orchestrator/commands" -Headers $headers -ContentType "application/json" -Body '{"node_id":"delhi_00","action":"reset_soc","target_soc_pct":55}'
```

---

## 🏁 How to Verify It's Working
1.  Launch all 6 terminals.
2.  Open the Dashboard URL from Terminal 6.
3.  **Click "DELHI"**.
4.  Terminal 3 should log: `>>> CITY ACTIVATED: DELHI <<<`.
5.  Terminal 5 should log: `--- Starting REALISTIC Reasoning Cycle for DELHI ---`.
6.  Live data should appear on the map cards.
