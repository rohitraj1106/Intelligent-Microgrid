# 🍯 Honeybee: The Comprehensive Project Technical Manual

This manual provides an exhaustive, file-by-file breakdown of the entire Distributed Intelligent Microgrid project. It documents the approach, internal working, and critical technicalities of every source file in the repository.

---

## 📂 1. Core Execution & Supervision (Root)

These files orchestrate the entire multi-process ecosystem.

*   **`start_microgrid.py`**:
    *   **Approach**: Uses a `ThreadPoolExecutor` and `subprocess.Popen` to manage 7 microservices concurrently.
    *   **Working**: It staggered-launches the Broker, Marketplace, API Gateway, Ingestor, Simulator, Orchestrator, and AI Agents with specific delays (2s-10s) to satisfy dependency health checks.
    *   **Technicality**: Implements a `_SINGLE_INSTANCE_LOCK` on Port 59673 to prevent recursive process forks.
*   **`launch_microgrid.bat`**:
    *   **Approach**: Windows-native batch script for one-click deployment.
    *   **Working**: Detects `.venv`, starts the Python supervisor (`start_microgrid.py`), and spawns a separate window for the Vite/React frontend.
*   **`reset_state.py`**:
    *   **Approach**: Cold-start utility.
    *   **Working**: Deletes all SQLite databases and WAL files to ensure a zero-state simulation.

---

## 📂 2. Edge Data Layer (`edge/`)

The physical boundary of the microgrid.

*   **`simulator.py`**:
    *   **Approach**: High-fidelity mathematical modeling of distributed energy resources (DER).
    *   **Working**: Generates telemetry using Sine-wave models for solar and double-peak stochastic models for load.
    *   **Technicality**: Implements a real-time battery SoC integrator where `SoC(t) = SoC(t-1) + (PowerIn - PowerOut) * duration`.
*   **`node.py`**:
    *   **Approach**: Local data persistence wrapper.
    *   **Working**: Manages the life-cycle of node-local SQLite databases. It ensures that raw telemetry is stored locally and never sent over the network (Privacy-by-Design).
*   **`models.py`**:
    *   **Approach**: Normalization of telemetry packets.
    *   **Working**: Defines the `TelemetryReading` dataclass and the `NodeSummary` aggregator.
*   **`broker.py`**:
    *   **Approach**: MQTT Hub using the `amqtt` library.
    *   **Working**: Operates a TCP listener on 1883 and a WebSocket listener on 9001 for the dashboard.
*   **`config.py`**:
    *   **Approach**: Centralized configuration management.
    *   **Working**: Stores City Lat/Lon, MQTT Topics, and 75-node battery capacity profiles.

---

## 📂 3. Intelligence Layer (`strategic_agent/`)

The LLM-driven reasoning core.

*   **`multi_agent_runner.py`**:
    *   **Approach**: Portfolio-style batch reasoning ("Wide Layer").
    *   **Working**: Groups 5 nodes into a single prompt. It focuses AI resources on the "Active City" selected by the user in the dashboard.
*   **`agent.py`**:
    *   **Approach**: Deep, single-node strategic reasoning.
    *   **Working**: Performs a full sensor-to-action loop: Ingest local DB → Fetch Market Book → Infer via Gemini → Execute Trade.
*   **`batch_builder.py`**:
    *   **Approach**: Structured prompt engineering.
    *   **Working**: Transforms raw numbers into a narrative context (e.g., "AFTERNOON_TRANSITION") to help the LLM understand situational urgency.
*   **`llm_client.py`**:
    *   **Approach**: API Abstraction for Google Gemini.
    *   **Working**: Includes built-in JSON repair and retry logic for brittle LLM outputs.
*   **`rate_limiter.py`**:
    *   **Approach**: Adaptive token management.
    *   **Working**: Prevents 429 errors by pacing API calls across the 75 simulated nodes.

---

## 📂 4. Tactical Safety Layer (`orchestrator/`)

The local sub-second governor.

*   **`orchestrator.py`**:
    *   **Approach**: Real-time FSM (Finite State Machine).
    *   **Working**: The "Traffic Cop" that validates LLM commands against live physical limits.
*   **`fsm.py`**:
    *   **Approach**: Deterministic state logic.
    *   **Working**: Defines legal transitions between `GRID_CONNECTED`, `ISLANDED`, and `TRADING`.
*   **`safety_buffer.py`**:
    *   **Approach**: Mathematical guardrails.
    *   **Working**: Rejects discharge commands if current SoC is below the `BUFFER_%` regardless of what the AI says.
*   **`mqtt_handshake.py`**:
    *   **Approach**: Distributed consensus for P2P trading.
    *   **Working**: Implements bit-level handshake sequence (`REQUEST`/`ACCEPT`/`REJECT`) between two disparate MQTT clients.

---

## 📂 5. Financial Layer (`marketplace/`)

The decentralized energy exchange.

*   **`engine.py`**:
    *   **Approach**: Continuous Double Auction (CDA).
    *   **Working**: Matches the best Buy/Sell orders using Midpoint Clearing pricing math.
*   **`repositories.py`**:
    *   **Approach**: Persistence layer for the market ledger.
    *   **Working**: Optimized for high-frequency queries to the Order Book and Recent Trades.
    *   **Technicality**: Implements proximity sorting (Delhi nodes see Delhi sellers first).
*   **`models.py`**:
    *   **Approach**: Financial data schemas.
    *   **Working**: Defines `Wallet`, `Settlement`, and `Trade` tables in the central SQL database.

---

## 📂 6. API & Presentation (`api_gateway/` & `dashboard/`)

The visibility layer.

*   **`api_gateway/main.py`**:
    *   **Approach**: High-performance REST wrapper.
    *   **Working**: Bridges internal system states to the React frontend via standardized JSON endpoints.
*   **`dashboard/src/App.jsx`**:
    *   **Approach**: Event-driven HUD (Heads-Up Display).
    *   **Working**: Uses `useMQTT` custom hooks to update 75 UI cards in real-time without refreshing the page.
*   **`dashboard/src/components/`**:
    *   **Approach**: Modular UI architecture.
    *   **Working**: Components like `NodeCard.jsx` and `TracePanel.jsx` reactively display the internal "Chain-of-Thought" from the AI agents.

---

## 📂 7. Predictive Engines (`forecasting/`)

The foundation of the project's foresight.

*   **`solar/forecaster.py`**:
    *   **Approach**: XGBoost Regressor for generation prediction.
    *   **Working**: Trained on 5 years of GHI/Temp data to predict power with 2.84% error.
*   **`load/forecaster.py`**:
    *   **Approach**: XGBoost Regressor for behavior prediction.
    *   **Working**: Models 15 unique residential profiles using weather and temporal-lag features.

---

## 📂 8. Test Suite (`test/`)

Validation of the system's rigor.

*   **`test_marketplace.py`**: High-volume unit tests for order overlapping cases.
*   **`test_strategic_agent.py`**: Mocking the LLM responses to ensure guardrails work as intended.
*   **`test_edge_simulator.py`**: Verifying that battery kinetics follow conservation of energy laws.

---

<p align="center">
  <b>Honeybee Complete Documentation: Final Release.</b>
</p>
