"""
# d:\Intelligent-Microgrid-main\Intelligent-Microgrid-main\mqtt\config.py

Configuration parameters for the MQTT Edge Data Layer.
Centralizes all variables so there are no hardcoded secrets or arbitrary values scattered.
"""
import os
import logging

# General node configuration
# We use environment variables with defaults to allow containerized overrides
HOME_ID = os.getenv("HOME_ID", "home_101")
SAFETY_BUFFER_SOC = float(os.getenv("SAFETY_BUFFER_SOC", "10.0"))

# MQTT Broker configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

# SQLite Database path for local ingestion
LOCAL_DB_DIR = os.getenv("LOCAL_DB_DIR", "data")
LOCAL_DB_PATH = os.path.join(LOCAL_DB_DIR, f"{HOME_ID}.db")

# MQTT Topics
# Defining standard topics to prevent typo errors during pub/sub operations
TOPIC_TELEMETRY = f"microgrid/{HOME_ID}/telemetry"
TOPIC_ALL_TELEMETRY = "microgrid/+/telemetry"
TOPIC_MARKET_SUMMARY = "microgrid/market/summary"
TOPIC_LLM_COMMANDS = f"microgrid/{HOME_ID}/llm_commands"
TOPIC_HANDSHAKE_REQUEST = f"microgrid/{HOME_ID}/handshake/request"
TOPIC_HANDSHAKE_RESPONSE_ALL = "microgrid/+/handshake/response"
TOPIC_SAFE_WINDOW = f"microgrid/{HOME_ID}/safe_window"
TOPIC_MARKETPLACE_SETTLE = "microgrid/marketplace/settle"

# Centralized logging setup to ensure consistent formats across all MQTT modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MQTT_Node")
