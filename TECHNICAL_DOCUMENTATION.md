# 🐝 Honeybee: The Absolute Technical Masterfile

This document is the definitive technical specification for the Honeybee Distributed Intelligent Microgrid. It covers every component, dependency, protocol, and mathematical model in the repository.

---

## 1. 📂 Dependency & Tooling Logic
The project uses a curated stack of Python and JavaScript tools, each selected for specific performance benchmarks.

### Backend (Python 3.9+)
*   **XGBoost**: Selected for its efficiency with tabular time-series data vs. LSTMs. Used for the 2.84% MAPE solar engine.
*   **amqtt / paho-mqtt**: Enables the sub-second "Hub-and-Spoke" telemetry system. QoS 0 is used for high-frequency telemetry to avoid network backpressure.
*   **FastAPI / SQLAlchemy**: Powers the P2P Marketplace. Selected for asynchronous performance during simultaneous matching of 75 nodes.
*   **PVLib**: A professional-grade physics library used to calibrate the NASA POWER weather data into actual kW outputs during data curation.
*   **Uvicorn**: Lighting-fast ASGI server for the FastAPI marketplace and API Gateway.

### Frontend (React + Vite)
*   **Vite**: Next-generation builder for instant Hot Module Replacement (HMR) during HUD development.
*   **TailwindCSS**: Utility-first CSS for the high-density "Dark Mode" dashboard.
*   **Lucide Icons**: Lightweight iconography for system status indicators.

---

## 2. ⚡ Physics Simulation (The Math)
Located in `edge/simulator.py`, the physics engine models the real-world behavior of 75 homes.

### ☀️ Solar Generation Model
Uses a Bell Curve approximation based on its latitude/longitude position:
*   **Equation**: `P(t) = sin((t - 6) / 12 * π) * Peak_kW * Cloud_Factor`
*   **Operational window**: 06:00 to 18:00 (Simulation Time).

### 🔌 Load Consumption Model
Uses a stochastic double-peak model to simulate residential behavior:
*   **Morning Peak (07:00 - 09:00)**: Rapid ramp-up for breakfast and pumps.
*   **Evening Peak (18:00 - 21:00)**: Maximum load for lighting and air conditioning.
*   **Stochasticity**: Adds random noise `(0.2 - 0.4 kW)` to prevent perfectly synchronous peaks across all 75 nodes.

### 🔋 Battery Kinetics
*   **Capacity**: Standardized 10.0 kWh per home.
*   **Safety Buffer**: FSM inhibits all P2P exports if `SoC < 20%`.

---

## 3. 🧠 Intelligence Layer (The Reasoning)
Honeybee uses a "Deep-and-Wide" architecture to manage 75 agents simultaneously.

### 📉 Wide Processing (Batching)
Handled by `strategic_agent.batch_builder`.
*   **Logic**: Groups 5 nodes into one LLM context.
*   **Decision Thresholds**:
    *   **MANDATORY BUY**: If SoC ≤ 35%.
    *   **MANDATORY SELL**: If SoC ≥ 65%.
    *   **HOLD**: SoC 36% - 64% with a stable 4h outlook.
*   **Outlook calculation**: Forecasted (Supply - Demand) integrated over 4 hours.

### 🧠 Deep Reasoning (Dedicated)
Handled by `strategic_agent/agent.py`.
*   **Chain-of-Thought (CoT)**: Every decision includes a `reasoning` field explainability.
*   **Circuit Breaker**: If the LLM returns 3 malformed JSONs or network errors, it trips and forces the node into a tactical `HOLD` state for 60 seconds.

---

## 4. 🏛️ P2P Market Microstructure
The marketplace (`marketplace/engine.py`) is a Continuous Double Auction (CDA).

### ⚖️ Midpoint Clearing Algorithm
Instead of a fixed price, trades execute at the midpoint to benefit both parties:
*   `Final_Price = (Bid_Price + Ask_Price) / 2`
*   **Region Rule**: If `Node A` (Delhi) matches with `Node B` (Delhi), the priority multiplier is `1.0`. If it matches with `Node C` (Dehradun), the multiplier is `0.1`, effectively deprioritizing long-distance trades to simulate transmission losses.

---

## 5. 🛰️ Networking & Ports
The system relies on 6 core ports for inter-process communication.

| Port | Service | Description |
| :--- | :--- | :--- |
| **1883** | MQTT TCP | Main telemetry and command bus. |
| **9001** | MQTT WS | Bridge for the React HUD to "listen" to the grid. |
| **8000** | Marketplace | Financial ledger and P2P matching engine. |
| **8100** | API Gateway | Security layer between frontend and backend databases. |
| **5173** | HUD (Vite) | The user-facing dashboard interface. |
| **59673** | Lock Port | Prevents starting duplicate microgrid supervisors. |

---

## 🔗 Technical Code Map (Everything Used)

### Core Logic
*   `edge/config.py`: Port mappings, node counts, and city lat/lon.
*   `orchestrator/fsm.py`: The logic gates for the 4 physical states.
*   `strategic_agent/llm_client.py`: The wrapper for Google Gemini API.

### Data Pipelines
*   `forecasting/solar/data_curator.py`: NASA POWER API → PVLib → XGBoost Training CSV.
*   `forecasting/load/data_curator.py`: NASA POWER API → Synthesis → XGBoost Training CSV.

### Execution Scripts
*   `launch_microgrid.bat`: Unified launcher (Windows).
*   `start_microgrid.py`: Python-based multi-process supervisor.

---

<p align="center">
  <b>This document constitutes the final technical authority for the Honeybee Repository.</b>
</p>
