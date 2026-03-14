"""
# d:\Intelligent-Microgrid-main\Intelligent-Microgrid-main\mqtt\sensor_simulator.py

Simulates a home node's energy profile, publishing telemetry every 15 minutes.
"""
import time
import json
import math
import random
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt

# We import config to avoid hardcoded secrets/values and reuse logging
try:
    import config
except ImportError:
    from . import config

def on_connect(client, userdata, flags, rc):
    """Callback for when the client receives a CONNACK response from the server."""
    if rc == 0:
        config.logger.info(f"Connected to MQTT Broker at {config.MQTT_BROKER}:{config.MQTT_PORT}")
    else:
        config.logger.error(f"Failed to connect, return code {rc}")

def simulate_solar(hour_of_day):
    """
    Simulates a daylight sine curve peaking at solar noon.
    Ensures zero generation at night (before hour 6 and after hour 18).
    """
    if 6 <= hour_of_day <= 18:
        # Shift hour to map 6-18 to 0-pi for sin function
        x = (hour_of_day - 6) / 12.0 * math.pi
        peak_w = 3000.0  # Assumed max 3kW solar panel setup
        # Add a tiny bit of cloud variability (noise)
        noise = random.uniform(0.9, 1.0)
        return round(math.sin(x) * peak_w * noise, 1)
    return 0.0

def simulate_load(hour_of_day):
    """
    Simulates residential load with morning (7-9am) and evening (6-9pm) peaks.
    Applies baseline load outside of those peaks.
    """
    base_load = random.uniform(200, 400)
    if 7 <= hour_of_day < 9: # Morning peak period
        return base_load + random.uniform(1000, 2500)
    elif 18 <= hour_of_day < 21: # Evening peak period
        return base_load + random.uniform(1500, 3500)
    return round(base_load, 1)

def run_simulator():
    """Main loop generating telemetry mimicking a 15-minute interval."""
    # Initialize the paho mqtt client
    client = mqtt.Client(f"SimClient_{config.HOME_ID}")
    client.on_connect = on_connect
    
    # Connect and handle broker disconnect gracefully
    try:
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
    except Exception as e:
        config.logger.error(f"Failed to connect to broker: {e}")
        return

    # Run network loop in the background
    client.loop_start()

    # Define initial battery configuration
    battery_soc = 50.0  
    battery_capacity_wh = 10000.0  # Example 10 kWh home battery

    # Using absolute mock datetime to simulate sequential data flow
    current_time = datetime(2024, 1, 15, 0, 0, 0)
    
    try:
        while True:
            # Advance time by 15 minutes for simulation purposes per loop tick
            current_time += timedelta(minutes=15)
            hour_dec = current_time.hour + current_time.minute / 60.0
            
            solar_w = simulate_solar(hour_dec)
            load_w = simulate_load(hour_dec)
            
            # Simple battery kinematic logic: SOC depletes when load > solar, charges when solar > load
            # Watt-hours change computed for a 15-minute interval (= 0.25 hours)
            net_energy_wh = (solar_w - load_w) * 0.25 
            battery_soc += (net_energy_wh / battery_capacity_wh) * 100.0
            
            # Constrain SOC geometrically bounds between 0 and 100 limit
            battery_soc = max(0.0, min(100.0, battery_soc))
            
            # Construct JSON schema exactly corresponding to integration constraints
            telemetry = {
                "home_id": config.HOME_ID,
                "timestamp": current_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "voltage_v": round(random.uniform(225.0, 235.0), 1),
                "current_a": round(load_w / 230.0, 2),
                "load_w": load_w,
                "solar_w": solar_w,
                "battery_soc": round(battery_soc, 1),
                "grid_connected": True
            }
            
            payload = json.dumps(telemetry)
            
            # Publish to specific dynamic topic via QoS 1 for ensured delivery tracking
            client.publish(config.TOPIC_TELEMETRY, payload, qos=1)
            config.logger.info(f"Published telemetry to {config.TOPIC_TELEMETRY}: {payload}")
            
            # Sleep briefly representing 15 mins wall-time (e.g. 1 second per tick for visual simulation observability)
            time.sleep(1)
            
    except KeyboardInterrupt:
        config.logger.info("Simulator interrupted by user. Stopping.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    run_simulator()
