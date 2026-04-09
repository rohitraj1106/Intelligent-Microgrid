import json
import time
import requests
import paho.mqtt.client as mqtt
from datetime import datetime

# --- CONFIGURATION ---
MQTT_BROKER = "localhost"
MQTT_PORT = 9001  # WebSocket port
MARKETPLACE_URL = "http://localhost:8000"
CAPTURE_DURATION_SECONDS = 180  # 3 minutes of data
POLL_INTERVAL_SECONDS = 15     # Match simulation cadence
OUTPUT_FILE = "demo_site/demo_data.json"

demo_data = {
    "mqtt_messages": [],
    "marketplace_snapshots": []
}

def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode())
        topic = message.topic
        print(f"Captured MQTT: {topic}")
        demo_data["mqtt_messages"].append({
            "timestamp": time.time(),
            "topic": topic,
            "payload": payload
        })
    except Exception as e:
        print(f"Error parsing MQTT message: {e}")

def capture_marketplace():
    try:
        print("Capturing Marketplace Snapshot...")
        stats = requests.get(f"{MARKETPLACE_URL}/stats").json()
        orders = requests.get(f"{MARKETPLACE_URL}/orders").json()
        trades = requests.get(f"{MARKETPLACE_URL}/trades?limit=20").json()
        
        demo_data["marketplace_snapshots"].append({
            "timestamp": time.time(),
            "stats": stats,
            "orders": orders,
            "trades": trades
        })
    except Exception as e:
        print(f"Error capturing marketplace: {e}")

def main():
    # Setup MQTT
    client = mqtt.Client(transport="websockets")
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.subscribe("dashboard/trace/#")
    client.loop_start()

    print(f"Starting data capture for {CAPTURE_DURATION_SECONDS} seconds...")
    start_time = time.time()
    last_poll = 0

    try:
        while time.time() - start_time < CAPTURE_DURATION_SECONDS:
            now = time.time()
            if now - last_poll >= POLL_INTERVAL_SECONDS:
                capture_marketplace()
                last_poll = now
            
            remaining = int(CAPTURE_DURATION_SECONDS - (now - start_time))
            if remaining % 10 == 0:
                print(f"Capturing... {remaining}s remaining. Messages: {len(demo_data['mqtt_messages'])}")
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("Capture interrupted by user.")
    finally:
        client.loop_stop()
        client.disconnect()

    # Normalize timestamps to relative time from start
    if demo_data["mqtt_messages"]:
        base_time = demo_data["mqtt_messages"][0]["timestamp"]
        for msg in demo_data["mqtt_messages"]:
            msg["relative_time"] = msg["timestamp"] - base_time
        for snap in demo_data["marketplace_snapshots"]:
            snap["relative_time"] = snap["timestamp"] - base_time

    print(f"Saving data to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(demo_data, f, indent=2)
    print("Done!")

if __name__ == "__main__":
    main()
