"""
seed_nodes.py
==========
Registers the 75 microgrid nodes in the marketplace and generates API keys.
Saves the API keys to a nodes_keys.json file for use by edge nodes and agents.
"""

import requests
import json
import os

BASE_URL = "http://localhost:8000"

CITIES = {
    "Delhi": 15,
    "Noida": 15,
    "Gurugram": 15,
    "Chandigarh": 15,
    "Dehradun": 15
}

def seed():
    print("Starting node registration for 75 nodes...")
    node_keys = {}

    # Preserve previously captured API keys; existing nodes cannot reveal keys again.
    if os.path.exists("node_keys.json"):
        try:
            with open("node_keys.json", "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    node_keys = loaded
        except Exception:
            # If malformed, proceed with fresh map and rebuild from successful registrations.
            node_keys = {}
    
    total_created = 0
    total_reused = 0
    missing_existing_keys = []
    for city, count in CITIES.items():
        for i in range(count):
            node_id = f"{city}_{i:02d}"
            payload = {
                "id": node_id,
                "city": city,
                "battery_cap_kwh": 10.0
            }
            
            try:
                response = requests.post(f"{BASE_URL}/nodes", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    node_keys[node_id] = {
                        "api_key": data["api_key"],
                        "city": city
                    }
                    total_created += 1
                    print(f"Registered {node_id}")
                elif response.status_code == 400 and "Node already exists" in response.text:
                    existing = node_keys.get(node_id, {})
                    if existing.get("api_key"):
                        total_reused += 1
                    else:
                        # Recover missing key by rotating key for existing node.
                        rotate = requests.post(f"{BASE_URL}/nodes/{node_id}/rotate-key")
                        if rotate.status_code == 200:
                            rot = rotate.json()
                            node_keys[node_id] = {
                                "api_key": rot["api_key"],
                                "city": city,
                            }
                            total_reused += 1
                            print(f"Recovered key for existing {node_id}")
                        else:
                            missing_existing_keys.append(node_id)
                    print(f"Skipped existing {node_id}")
                else:
                    print(f"Failed to register {node_id}: {response.text}")
            except Exception as e:
                print(f"Error registering {node_id}: {e}")
                
    # Save keys to a file for easy reference
    with open("node_keys.json", "w", encoding="utf-8") as f:
        json.dump(node_keys, f, indent=4)
        
    print(f"\nCreated new nodes: {total_created}")
    print(f"Reused existing keys: {total_reused}")
    print(f"Keys stored in node_keys.json: {len(node_keys)}")

    if missing_existing_keys:
        sample = ", ".join(missing_existing_keys[:5])
        print("\nWARNING: Some nodes already exist in DB but their API keys are unavailable locally.")
        print(f"Example missing keys: {sample}")
        print("Recovery: reset marketplace DB and run this seeder again to regenerate keys.")

    print("API keys preserved in node_keys.json")

if __name__ == "__main__":
    # Ensure the server is running before seeding
    # This script assumes the marketplace is up at localhost:8000
    seed()
