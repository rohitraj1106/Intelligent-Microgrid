"""
End-to-end test for the Tactical Orchestrator.
Starts the orchestrator, sends test telemetry and LLM commands,
verifies FSM state transitions and safety overrides.
"""
import sys
import os
import time
import json
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mqtt'))
import config
import paho.mqtt.client as mqtt

# We import the orchestrator class directly
from tactical_orchestrator import TacticalOrchestrator, STATE_GRID_CONNECTED, STATE_EMERGENCY, STATE_P2P_TRADING

def test_orchestrator():
    print("=" * 60)
    print("  Tactical Orchestrator — FSM Integration Test")
    print("=" * 60)
    
    # 1. Create orchestrator
    orch = TacticalOrchestrator()
    time.sleep(2)  # Let it connect and subscribe
    
    # 2. Create a test publisher client
    pub = mqtt.Client("TestPublisher")
    pub.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
    pub.loop_start()
    time.sleep(1)
    
    # --- TEST 1: Normal telemetry → stays in GRID_CONNECTED ---
    print("\n[TEST 1] Sending normal telemetry (SoC=67%)...")
    pub.publish(config.TOPIC_TELEMETRY, json.dumps({
        "home_id": config.HOME_ID,
        "timestamp": "2024-01-15T14:30:00",
        "voltage_v": 231.0,
        "current_a": 3.0,
        "load_w": 700,
        "solar_w": 1800,
        "battery_soc": 67.0,
        "grid_connected": True
    }), qos=1)
    time.sleep(1)
    assert orch.state == STATE_GRID_CONNECTED, f"Expected GRID_CONNECTED, got {orch.state}"
    assert orch.battery_soc == 67.0
    print(f"  ✅ State: {orch.state} | SoC: {orch.battery_soc}%")
    
    # --- TEST 2: Low SoC telemetry → EMERGENCY ---
    print("\n[TEST 2] Sending low SoC telemetry (SoC=8%)...")
    pub.publish(config.TOPIC_TELEMETRY, json.dumps({
        "home_id": config.HOME_ID,
        "timestamp": "2024-01-15T23:00:00",
        "voltage_v": 228.0,
        "current_a": 2.0,
        "load_w": 400,
        "solar_w": 0,
        "battery_soc": 8.0,
        "grid_connected": True
    }), qos=1)
    time.sleep(1)
    assert orch.state == STATE_EMERGENCY, f"Expected EMERGENCY, got {orch.state}"
    print(f"  ✅ State: {orch.state} | SoC: {orch.battery_soc}%")
    
    # --- TEST 3: SELL command during EMERGENCY → BLOCKED by safety override ---
    print("\n[TEST 3] Sending SELL command during EMERGENCY (should be blocked)...")
    pub.publish(config.TOPIC_LLM_COMMANDS, json.dumps({
        "action": "SELL",
        "target": "home_202",
        "amount": "1.5kWh",
        "min_price": "5"
    }), qos=1)
    time.sleep(1)
    # Should still be EMERGENCY, not P2P_TRADING
    assert orch.state == STATE_EMERGENCY, f"Expected EMERGENCY (sell blocked), got {orch.state}"
    print(f"  ✅ SELL blocked! State remains: {orch.state}")
    
    # --- TEST 4: SoC recovers → back to GRID_CONNECTED ---
    print("\n[TEST 4] SoC recovers to 20% (above safety + hysteresis)...")
    pub.publish(config.TOPIC_TELEMETRY, json.dumps({
        "home_id": config.HOME_ID,
        "timestamp": "2024-01-16T08:00:00",
        "voltage_v": 232.0,
        "current_a": 3.5,
        "load_w": 800,
        "solar_w": 2000,
        "battery_soc": 20.0,
        "grid_connected": True
    }), qos=1)
    time.sleep(1)
    assert orch.state == STATE_GRID_CONNECTED, f"Expected GRID_CONNECTED, got {orch.state}"
    print(f"  ✅ State recovered: {orch.state} | SoC: {orch.battery_soc}%")
    
    # --- TEST 5: SELL command when healthy → enters P2P_TRADING ---
    print("\n[TEST 5] Sending SELL command when healthy...")
    pub.publish(config.TOPIC_LLM_COMMANDS, json.dumps({
        "action": "SELL",
        "target": "home_202",
        "amount": "1.0kWh",
        "min_price": "4"
    }), qos=1)
    time.sleep(1)
    assert orch.state == STATE_P2P_TRADING, f"Expected P2P_TRADING, got {orch.state}"
    print(f"  ✅ State: {orch.state} (trading with home_202)")
    
    # --- Cleanup ---
    pub.loop_stop()
    pub.disconnect()
    orch.stop()
    
    print("\n" + "=" * 60)
    print("  ✅ ALL 5 TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_orchestrator()
