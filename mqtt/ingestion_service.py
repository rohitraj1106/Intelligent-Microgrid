"""
# d:\Intelligent-Microgrid-main\Intelligent-Microgrid-main\mqtt\ingestion_service.py

Subscribes to all home telemetry topics and persists to a local SQLite database.
Handles automatic reconnection, payload validation, and ensures table setup.
"""
import os
import json
import sqlite3
import paho.mqtt.client as mqtt

try:
    import config
except ImportError:
    from . import config

def get_db_connection(home_id):
    """
    Creates/connects to a local database on-demand bound to a specific home_id.
    Ensures that the directory hierarchy exists and initializes 4 required tables schemas.
    """
    os.makedirs(config.LOCAL_DB_DIR, exist_ok=True)
    db_path = os.path.join(config.LOCAL_DB_DIR, f"{home_id}.db")
    
    # Establish SQLite connection (timeout for managing concurent locks)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    
    # Initialize 4 requested normalized tables ensuring schema validity dynamically:
    # We use context managers `with conn` to guarantee changes are committed.
    with conn:
        # Table 1: Raw unified telemetry
        conn.execute('''
            CREATE TABLE IF NOT EXISTS telemetry (
                home_id TEXT,
                timestamp TEXT,
                voltage_v REAL,
                current_a REAL,
                load_w REAL,
                solar_w REAL,
                battery_soc REAL,
                grid_connected INTEGER
            )
        ''')
        # Table 2: Battery derived states
        conn.execute('''
            CREATE TABLE IF NOT EXISTS battery_state (
                home_id TEXT,
                timestamp TEXT,
                soc REAL,
                status TEXT
            )
        ''')
        # Table 3: Solar dimension
        conn.execute('''
            CREATE TABLE IF NOT EXISTS solar_generation (
                home_id TEXT,
                timestamp TEXT,
                solar_w REAL
            )
        ''')
        # Table 4: Load dimension
        conn.execute('''
            CREATE TABLE IF NOT EXISTS load_history (
                home_id TEXT,
                timestamp TEXT,
                load_w REAL
            )
        ''')
    return conn

def on_connect(client, userdata, flags, rc):
    """Callback triggered on successful broker connection setup."""
    if rc == 0:
        config.logger.info(f"Ingestion service connected to broker {config.MQTT_BROKER}")
        # Subscribe to wildcard topic (+) for aggregating all homes seamlessly
        client.subscribe(config.TOPIC_ALL_TELEMETRY, qos=1)
        config.logger.info(f"Subscribed to wildcard topic: {config.TOPIC_ALL_TELEMETRY}")
    else:
        config.logger.error(f"Failed to connect, return code: {rc}")

def on_disconnect(client, userdata, rc):
    """Callback when disconnected from broker dynamically."""
    if rc != 0:
        config.logger.warning("Unexpected disconnection. The Paho client auto-reconnect flag drives reconnection.")

def on_message(client, userdata, msg):
    """Callback triggered contextually when a PUBLISH message is validated from the network."""
    try:
        # Parse incoming JSON payload uniformly
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        
        home_id = data.get("home_id")
        timestamp = data.get("timestamp")
        
        if not home_id or not timestamp:
            config.logger.warning(f"Malformed JSON payload, missing core routing identifiers (home_id/timestamp): {payload_str}")
            return
            
        voltage_v = data.get("voltage_v", 0.0)
        current_a = data.get("current_a", 0.0)
        load_w = data.get("load_w", 0.0)
        solar_w = data.get("solar_w", 0.0)
        battery_soc = data.get("battery_soc", 0.0)
        grid_connected = 1 if data.get("grid_connected") else 0
        
        # Decide battery status string heuristically checking flux deltas 
        bat_status = "STABLE"
        if solar_w > load_w:
            bat_status = "CHARGING"
        elif load_w > solar_w:
            bat_status = "DISCHARGING"
            
        # Connect to DB dynamically segregating writes per home_id file architecture strategy.
        conn = get_db_connection(home_id)
        
        # Atomically write structured dimensions into multiple localized tables
        with conn:
            # Insert telemetry base vector
            conn.execute(
                "INSERT INTO telemetry (home_id, timestamp, voltage_v, current_a, load_w, solar_w, battery_soc, grid_connected) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (home_id, timestamp, voltage_v, current_a, load_w, solar_w, battery_soc, grid_connected)
            )
            # Extracted state representations per domain semantics
            conn.execute(
                "INSERT INTO battery_state (home_id, timestamp, soc, status) VALUES (?, ?, ?, ?)",
                (home_id, timestamp, battery_soc, bat_status)
            )
            conn.execute(
                "INSERT INTO solar_generation (home_id, timestamp, solar_w) VALUES (?, ?, ?)",
                (home_id, timestamp, solar_w)
            )
            conn.execute(
                "INSERT INTO load_history (home_id, timestamp, load_w) VALUES (?, ?, ?)",
                (home_id, timestamp, load_w)
            )
            
        config.logger.info(f"Persisted localized telemetry for {home_id} at {timestamp}")
        # Explicit disconnect handles SQLite locks cleanly per write routine scale.
        conn.close()
        
    except json.JSONDecodeError:
        config.logger.error(f"Failed to decode JSON payload natively: {msg.payload}")
    except sqlite3.Error as e:
        config.logger.error(f"Local SQLite DB persistence sequence error: {e}")
    except Exception as e:
        config.logger.error(f"General processing error in on_message: {e}")

def run_ingestion():
    """Starts the MQTT loop execution persistently."""
    client = mqtt.Client("IngestionService")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Built-in robust reconnection semantics mapping the network interface explicitly
    client.reconnect_delay_set(min_delay=1, max_delay=120)

    try:
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
    except Exception as e:
        config.logger.error(f"Initial connection to broker resolution failed systematically: {e}")
        return

    # Loop forever effectively prevents premature exit for daemon-like behavior.
    try:
        config.logger.info("Ingestion service executing. Waiting on telemetry ingress streams...")
        client.loop_forever()
    except KeyboardInterrupt:
        config.logger.info("Ingestion service terminated deliberately by execution root operator.")
    finally:
        client.disconnect()

if __name__ == "__main__":
    run_ingestion()
