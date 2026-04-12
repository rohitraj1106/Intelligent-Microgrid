"""
edge/config.py
==============
Central configuration for the Edge Data Layer.
All values can be overridden via environment variables for containerised deployments.
No secrets or arbitrary hardcoded values anywhere else in the package.
"""
import os
import logging
from dotenv import load_dotenv

# Load .env file at the earliest opportunity
load_dotenv()

# ---------------------------------------------------------------------------
# Multi-node configuration — Dynamic 75-Node Factory
# ---------------------------------------------------------------------------
def generate_node_configs():
    import random
    configs = {}
    cities = {
        "Delhi":      {"lat": 28.6139, "lon": 77.2090},
        "Noida":      {"lat": 28.5355, "lon": 77.3910},
        "Gurugram":   {"lat": 28.4595, "lon": 77.0266},
        "Chandigarh": {"lat": 30.7333, "lon": 76.7794},
        "Dehradun":   {"lat": 30.3165, "lon": 78.0322},
    }
    
    for city_name, coords in cities.items():
        # Per-city random seed for stable randomization
        city_rng = random.Random(city_name)
        for i in range(15):
            node_id = f"{city_name.lower()}_{i:02d}"
            # Randomized battery capacity between 8kWh and 15kWh
            cap_wh = city_rng.randint(8, 15) * 1000
            configs[node_id] = {
                "city": city_name,
                "lat": coords["lat"] + city_rng.uniform(-0.02, 0.02),
                "lon": coords["lon"] + city_rng.uniform(-0.02, 0.02),
                "battery_capacity_wh": cap_wh
            }
    return configs

NODE_CONFIGS = generate_node_configs()

# ---------------------------------------------------------------------------
# MQTT Broker — override via env vars for Docker / cloud deployments
# ---------------------------------------------------------------------------
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.getenv("MQTT_PORT", 1883))

# Active node id for single-node processes (simulator / orchestrator).
# When running all nodes, each subprocess sets its own HOME_ID env var.
HOME_ID = os.getenv("HOME_ID", "delhi_01")

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------
# Mandatory 10 % SoC reserve (N-1 resiliency, matches project spec)
SAFETY_BUFFER_SOC = float(os.getenv("SAFETY_BUFFER_SOC", "10.0"))

# Orchestrator safety thresholds
VOLTAGE_UNSTABLE_V  = float(os.getenv("VOLTAGE_UNSTABLE_V", "200.0"))
VOLTAGE_FAILED_V    = float(os.getenv("VOLTAGE_FAILED_V", "180.0"))
GRID_FAILURE_DEBOUNCE = int(os.getenv("GRID_FAILURE_DEBOUNCE", "3"))
SOC_DRIFT_TOLERANCE   = float(os.getenv("SOC_DRIFT_TOLERANCE", "25.0"))  # % SoC drift allowed during LLM call

# ---------------------------------------------------------------------------
# Storage — each node writes to its own isolated SQLite file
# ---------------------------------------------------------------------------
DB_DIR                = os.getenv("DB_DIR", os.path.join("data", "edge"))
DATA_RETENTION_HOURS  = int(os.getenv("DATA_RETENTION_HOURS", "168"))   # 7 days

# ---------------------------------------------------------------------------
# MQTT topic map  (teammate's topic design was correct — reused here)
# ---------------------------------------------------------------------------
def telemetry_topic(node_id: str) -> str:
    return f"microgrid/{node_id}/telemetry"

def llm_commands_topic(node_id: str) -> str:
    return f"microgrid/{node_id}/llm_commands"

def safe_window_topic(node_id: str) -> str:
    return f"microgrid/{node_id}/safe_window"

def handshake_request_topic(node_id: str) -> str:
    return f"microgrid/{node_id}/handshake/request"

def handshake_response_topic(node_id: str) -> str:
    return f"microgrid/{node_id}/handshake/response"

# Wildcard topics (used by ingestion services that listen to all nodes)
TOPIC_ALL_TELEMETRY        = "microgrid/+/telemetry"
TOPIC_HANDSHAKE_RESPONSE_ALL = "microgrid/+/handshake/response"
TOPIC_MARKET_SUMMARY       = "microgrid/market/summary"
TOPIC_MARKETPLACE_SETTLE   = "microgrid/marketplace/settle"

# Convenience shortcuts for single-node processes (reads HOME_ID at import time)
TOPIC_TELEMETRY            = telemetry_topic(HOME_ID)
TOPIC_LLM_COMMANDS         = llm_commands_topic(HOME_ID)
TOPIC_SAFE_WINDOW          = safe_window_topic(HOME_ID)
TOPIC_HANDSHAKE_REQUEST    = handshake_request_topic(HOME_ID)

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
TELEMETRY_INTERVAL = int(os.getenv("TELEMETRY_INTERVAL", "15"))   # seconds per publish tick

# ---------------------------------------------------------------------------
# Strategic Agent
# ---------------------------------------------------------------------------
AGENT_CYCLE_INTERVAL = int(os.getenv("AGENT_CYCLE_INTERVAL", "15"))  # seconds (default for fast demo)
MARKETPLACE_URL      = os.getenv("MARKETPLACE_URL", "http://localhost:8000")
GEMINI_MODEL         = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
LLM_REQUEST_TIMEOUT_SEC = int(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "20"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_INITIAL_BACKOFF_SEC = float(os.getenv("LLM_INITIAL_BACKOFF_SEC", "1.5"))
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "220"))
LLM_CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("LLM_CIRCUIT_BREAKER_THRESHOLD", "4"))
LLM_CIRCUIT_BREAKER_COOLDOWN_SEC = int(os.getenv("LLM_CIRCUIT_BREAKER_COOLDOWN_SEC", "60"))

# ---------------------------------------------------------------------------
# Logging  (consistent format across all edge modules)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("Edge")
