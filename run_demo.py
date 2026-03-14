"""
Quick demo runner — runs the sensor simulator for a fixed number of ticks 
to demonstrate end-to-end data flow without needing a long-running process.
"""
import sys
import os
import time
import json
import math
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mqtt'))
import config
import paho.mqtt.client as mqtt

def simulate_solar(hour_of_day):
    if 6 <= hour_of_day <= 18:
        x = (hour_of_day - 6) / 12.0 * math.pi
        peak_w = 3000.0
        noise = random.uniform(0.9, 1.0)
        return round(math.sin(x) * peak_w * noise, 1)
    return 0.0

def simulate_load(hour_of_day):
    base_load = random.uniform(200, 400)
    if 7 <= hour_of_day < 9:
        return round(base_load + random.uniform(1000, 2500), 1)
    elif 18 <= hour_of_day < 21:
        return round(base_load + random.uniform(1500, 3500), 1)
    return round(base_load, 1)

def main():
    client = mqtt.Client(f"DemoSim_{config.HOME_ID}")
    client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
    client.loop_start()
    
    battery_soc = 50.0
    battery_capacity_wh = 10000.0
    current_time = datetime(2024, 1, 15, 5, 0, 0)  # Start at 5 AM to see sunrise
    
    NUM_TICKS = 96  # 96 x 15min = 24 hours of simulated data
    
    print("=" * 60)
    print("  Sensor Simulator Demo — 24 hours of data (96 ticks)")
    print("=" * 60)
    
    for i in range(NUM_TICKS):
        current_time += timedelta(minutes=15)
        hour_dec = current_time.hour + current_time.minute / 60.0
        
        solar_w = simulate_solar(hour_dec)
        load_w = simulate_load(hour_dec)
        
        net_energy_wh = (solar_w - load_w) * 0.25
        battery_soc += (net_energy_wh / battery_capacity_wh) * 100.0
        battery_soc = max(0.0, min(100.0, battery_soc))
        
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
        
        client.publish(config.TOPIC_TELEMETRY, json.dumps(telemetry), qos=1)
        
        marker = ""
        if solar_w > 0:
            marker += " ☀️"
        if load_w > 1000:
            marker += " ⚡PEAK"
        if battery_soc < 15:
            marker += " ⚠️LOW_BAT"
            
        print(f"[{i+1:3d}/96] {current_time.strftime('%H:%M')} | Solar: {solar_w:7.1f}W | Load: {load_w:7.1f}W | SoC: {battery_soc:5.1f}%{marker}")
        
        time.sleep(0.15)  # Fast enough for demo, slow enough to see output
    
    print("=" * 60)
    print("  ✅ 24-hour simulation complete!")
    print("=" * 60)
    
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()
