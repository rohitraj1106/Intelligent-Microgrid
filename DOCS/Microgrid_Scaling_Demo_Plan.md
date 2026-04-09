# 75-Node Microgrid Scaling & Demo Plan

> **Purpose:** Architectural and visual upgrades to scale the simulation from 5 → 75 nodes (15 per city × 5 cities) and ensure demo-day stability.

| Field | Details |
|-------|---------|
| **Scope** | 5 → 75 nodes |
| **Cities** | Delhi, Noida, Gurugram, Chandigarh, Dehradun |
| **Purpose** | Video demonstration |
| **Status** | In Progress |

---

## Table of Contents

1. [Decision Required: Storage Architecture](#1-decision-required-storage-architecture)
2. [Dashboard Changes](#2-dashboard-changes)
3. [Edge Simulation Changes](#3-edge-simulation-changes)
4. [Expanded Test Coverage](#4-expanded-test-coverage)
5. [Open Questions](#5-open-questions)
6. [Demo Run-Through & Verification Checklist](#6-demo-run-through--verification-checklist)
7. [Summary of Changes](#7-summary-of-changes)

---

## 1. Decision Required: Storage Architecture

> ⚠️ **ACTION REQUIRED — Confirm before implementation begins.**

Scaling to 75 nodes and logging all telemetry to a local SQLite database risks **filesystem locking** on slower disks due to concurrent writers. Choose one of the two approaches below:

### Option A — In-Memory / MQTT Broadcast Mode ✅ Recommended for Demo

All telemetry is broadcast via MQTT and held in-memory on the dashboard. No disk writes occur during the recording session, eliminating SQLite locking risk entirely. Ideal for a clean, performant video demo.

### Option B — Optimised SQLite Ingestion

Retain disk-based logging but enable **WAL (Write-Ahead Logging)** mode and batch writes to safely handle 75 concurrent writers. More complex to configure but preserves a full audit trail post-demo.

> 💡 **Recommendation:** Option A is strongly preferred for the recording session. Option B can be activated in production after the demo.

---

## 2. Dashboard Changes

The dashboard is redesigned as a two-panel **Command Centre** — displaying all 75 nodes at a glance while retaining deep-dive telemetry for individual node inspection.

---

### 2.1 `dashboard/index.html` — MODIFY

**New two-panel layout:**

- **Overview Map Panel** — 5 city clusters, each showing 15 animated SVG Battery Rings representing real-time State-of-Charge (SoC).
- **Deep Dive Node Panel** — the existing Phase 1–4 trace pipeline, now activated by clicking any node in the overview.

**Node state colour coding:**

| State | Ring Colour | Meaning |
|-------|-------------|---------|
| Charging | 🟢 Green | Battery actively receiving charge |
| Emergency | 🔴 Red | Node below critical SoC threshold |
| Islanded | 🟣 Purple | Disconnected from grid, self-sustaining |
| P2P Trading | 🟡 Gold | Active peer-to-peer energy trade in progress |

---

### 2.2 `dashboard/script.js` — MODIFY

- **Remove** the hardcoded single-node filter: `if (msgNodeId !== targetNodeId) return`
- **Add** a global state object mapping all 75 node IDs to their latest SoC and Trading State
- **Throttle** macro-grid DOM updates to a **1-second interval** to prevent rendering bottlenecks
- **Route** the selected node's telemetry stream exclusively into the Phase 1–4 deep-dive pipeline

---

### 2.3 `dashboard/styles.css` — MODIFY

- CSS Grid layout for the 5-city cluster overview map
- Glassmorphic card styles for each city panel (`backdrop-filter: blur`)
- `@keyframes` animated SoC ring pulses with state-specific colour transitions
- Smooth click-transition animation when switching the Deep Dive view between nodes

---

## 3. Edge Simulation Changes

---

### 3.1 `edge/config.py` — MODIFY

Replace the five hardcoded `NODE_CONFIGS` entries with a **procedural generator**:

- Loop across all 5 cities, spawning 15 nodes each (e.g. `delhi_01` → `delhi_15`)
- Apply **randomised battery capacity jitter** per node: **8 kWh – 12 kWh**
- Jitter ensures heterogeneous behaviour across the grid, producing richer and more realistic P2P trading scenarios organically during the demo

---

### 3.2 `edge/simulator.py` — MODIFY

Optimise `publish_all()` to prevent MQTT broker saturation during local recording:

- Send telemetry in **bursts of 15 nodes** per batch rather than all 75 in a tight synchronous loop
- Introduce **micro-sleeps between batches** (e.g. ~20 ms) to smooth broker ingestion
- No loss of data fidelity — purely a pacing improvement to avoid network hiccups during screen capture

---

## 4. Expanded Test Coverage

Three test files are added or modified to validate the system under 75-node load and guard against demo-breaking failures.

---

### 4.1 `test/test_marketplace.py` — NEW 🆕

High-frequency order matching tests under concurrent 75-node bid submissions.

- Use **FastAPI TestClient** to simulate concurrent `Buy` and `Sell` bids from all 75 nodes
- Verify `engine.py` processes the full bid queue without **SQLite deadlocks**
- Assert correct order matching outcomes under peak throughput conditions

---

### 4.2 `test/test_edge_simulator.py` — NEW 🆕

Physics boundary and MQTT format integrity tests for all 75 node instances.

- Verify **SoC never exceeds 100% or drops below 0%** across all nodes under rapid simulation ticks
- Mock the MQTT client and assert **message format integrity** over sequential high-frequency loops
- Confirm capacity jitter produces varied but physically valid SoC trajectories across nodes

---

### 4.3 `test/test_orchestrator.py` — MODIFY

Expand FSM coverage to multi-node failure and recovery scenarios.

- Simulate **grid failure events affecting multiple nodes simultaneously**
- Validate recovery sequencing: confirm the orchestrator correctly re-integrates islanded nodes
- Ensure FSM transitions remain **deterministic** under concurrent state changes

---

## 5. Open Questions

> ⚠️ **Both decisions below must be confirmed before development starts** to avoid mid-sprint rework.

---

### 5.1 AI Agent Compute for Demo

> 🔴 **Risk:** Running 75 instances of `strategic_agent` with live Gemini API calls will likely hit **rate limits** and incur significant cost during a recording session.

**Proposed mitigation — Stubbed / Cached Agent Mode:**

- A configurable subset of nodes (e.g. **5 nodes**) make real LLM calls
- The remaining 70 nodes replay **cached agent responses** to simulate realistic decision output
- Mode is toggled via an environment variable — no code changes required between demo and production runs

> **→ Decision needed:** How many nodes should make real LLM calls during the video recording?

---

### 5.2 Dashboard Visual Theme

Select one theme before CSS implementation begins:

| | Option A: Dark Mode | Option B: Clean Light Mode |
|-|---------------------|---------------------------|
| **Palette** | Neon green & blue on deep black | White background, soft shadows, accent colours |
| **Mood** | High visual drama, tech-forward | Professional, presentation-ready |
| **Best for** | Dim recording environments | Bright recording environments |

> **→ Decision needed:** Dark Mode or Light Mode?

---

## 6. Demo Run-Through & Verification Checklist

Follow these steps in sequence on the day of recording.

### 6.1 Automated Tests

Run the full test suite **before** any manual steps. Do not begin recording with any failing tests.

```bash
pytest test/ -v --tb=short
```

All tests must pass before proceeding.

---

### 6.2 Manual Verification Steps

| # | Step | Action | Pass Criterion |
|---|------|--------|---------------|
| 1 | **Startup** | Launch the MQTT broker and Marketplace backend. Confirm both report healthy status. | No errors in logs |
| 2 | **Simulator** | Run `python -m edge.run_simulator --step 15`. Monitor broker ingestion. | 75 payloads per tick visible in broker logs |
| 3 | **Dashboard Load** | Open `dashboard/index.html` in browser. Inspect all 5 city clusters. | 75 nodes visible, each pulsing with distinct telemetry |
| 4 | **Node Selection** | Click node `delhi_07` on the overview map. | Phase 1–4 pipeline populates instantly with `delhi_07` data |
| 5 | **Record** | Start screen capture. Run a full 60-second simulation cycle. | Smooth animation throughout; no dropped frames or console errors |

---

## 7. Summary of Changes

| File | Type | Description |
|------|------|-------------|
| `dashboard/index.html` | MODIFY | Two-panel Command Centre layout with SVG Battery Rings |
| `dashboard/script.js` | MODIFY | Global 75-node state management and selective deep-dive routing |
| `dashboard/styles.css` | MODIFY | CSS Grid city map, glassmorphic animations, state-colour system |
| `edge/config.py` | MODIFY | Procedural 75-node generator with randomised capacity jitter |
| `edge/simulator.py` | MODIFY | Batched MQTT publish with micro-sleep throttling |
| `test/test_marketplace.py` | **NEW** | Concurrent bid load tests, SQLite deadlock validation |
| `test/test_edge_simulator.py` | **NEW** | Physics boundary and MQTT format integrity tests |
| `test/test_orchestrator.py` | MODIFY | Multi-node FSM failure and recovery tests |

---

*Internal Engineering Document — 75-Node Microgrid Scaling & Demo Plan*
