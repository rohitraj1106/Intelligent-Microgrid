"""
Quick one-shot test: runs the market summarizer once to verify it works.
"""
import sys
import os

# Ensure mqtt/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mqtt'))

import config
import paho.mqtt.client as mqtt

# We need to construct the engine and table independently here
# to avoid any marketplace ORM import issues
from sqlalchemy import create_engine, MetaData, Table, Column, String, Float, inspect
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MARKETPLACE_DB_URL = f"sqlite:///{os.path.join(PROJECT_ROOT, 'marketplace.db')}"

engine = create_engine(
    MARKETPLACE_DB_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False,
)

meta = MetaData()
market_intents = Table(
    'market_intents', meta,
    Column('home_id', String),
    Column('timestamp', String),
    Column('intent', String),
    Column('surplus_w', Float),
    Column('deficit_w', Float),
)
meta.create_all(engine)

# Connect to MQTT broker
client = mqtt.Client("TestSummarizer")
client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
client.loop_start()

# Scan data/ for all home DBs
from datetime import datetime
import json

data_dir = config.LOCAL_DB_DIR
db_files = [f for f in os.listdir(data_dir) if f.endswith('.db')]
print(f"Found {len(db_files)} home database(s): {db_files}")

summaries = []
for db_file in db_files:
    home_id = db_file.replace('.db', '')
    db_path = os.path.join(data_dir, db_file)
    
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT AVG(solar_w) as avg_solar, AVG(load_w) as avg_load "
        "FROM (SELECT solar_w, load_w FROM telemetry ORDER BY timestamp DESC LIMIT 15)"
    )
    row = cur.fetchone()
    avg_solar = row['avg_solar'] or 0.0
    avg_load = row['avg_load'] or 0.0
    conn.close()
    
    diff = avg_solar - avg_load
    intent = "balanced"
    surplus_w = 0.0
    deficit_w = 0.0
    
    if diff > 200:
        intent = f"{home_id} has {round(diff/1000,2)}kw surplus"
        surplus_w = diff
    elif diff < -200:
        deficit_diff = avg_load - avg_solar
        intent = f"{home_id} needs {round(deficit_diff/1000,2)}kw"
        deficit_w = deficit_diff
    
    now_str = datetime.now().isoformat()
    summary = {
        "home_id": home_id,
        "timestamp": now_str,
        "intent": intent,
        "surplus_w": round(surplus_w, 2),
        "deficit_w": round(deficit_w, 2),
    }
    summaries.append(summary)
    
    # Persist to marketplace DB
    with engine.begin() as db_conn:
        db_conn.execute(
            market_intents.insert().values(**summary)
        )
    
    print(f"  [{home_id}] avg_solar={avg_solar:.1f}W, avg_load={avg_load:.1f}W => {intent}")

# Publish to MQTT
payload = json.dumps({"summaries": summaries})
client.publish(config.TOPIC_MARKET_SUMMARY, payload, qos=1)
print(f"\nPublished market summary to MQTT topic: {config.TOPIC_MARKET_SUMMARY}")

# Verify persistence
with engine.connect() as db_conn:
    from sqlalchemy import text
    result = db_conn.execute(text("SELECT COUNT(*) FROM market_intents"))
    count = result.scalar()
    print(f"market_intents table now has {count} row(s)")

client.loop_stop()
client.disconnect()
print("\n✅ Market summarizer test complete!")
