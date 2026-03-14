"""
# mqtt/market_summarizer.py

Reads from local SQLite every 15 minutes, computes anonymized market intent,
publishes to the central marketplace database (using SQLAlchemy Core), and
emits MQTT market summary payload.
"""
import time
import json
import sqlite3
import os
import paho.mqtt.client as mqtt
from datetime import datetime

from sqlalchemy import create_engine, MetaData, Table, Column, String, Float, DateTime, text

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# Build our own engine pointing at the same marketplace SQLite DB
# This avoids importing marketplace.database which pulls in ORM models
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKETPLACE_DB_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(PROJECT_ROOT, 'marketplace.db')}"
)
pg_engine = create_engine(
    MARKETPLACE_DB_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if "sqlite" in MARKETPLACE_DB_URL else {},
    echo=False,
    pool_pre_ping=True,
)

# Define the market_intents table using SQLAlchemy Core (no ORM dependency)
metadata = MetaData()
market_intents = Table(
    'market_intents', metadata,
    Column('home_id', String),
    Column('timestamp', String),
    Column('intent', String),
    Column('surplus_w', Float),
    Column('deficit_w', Float),
)
metadata.create_all(pg_engine)


def get_average_data(home_id, minutes=15):
    """
    Queries the per-home local SQLite DB for the most recent telemetry rows
    and returns (avg_solar_w, avg_load_w).
    """
    db_path = os.path.join(config.LOCAL_DB_DIR, f"{home_id}.db")
    if not os.path.exists(db_path):
        return 0.0, 0.0

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Use the last 15 rows (= last ~15 intervals) as the averaging window
        cursor.execute(
            "SELECT AVG(solar_w) as avg_solar, AVG(load_w) as avg_load "
            "FROM (SELECT solar_w, load_w FROM telemetry ORDER BY timestamp DESC LIMIT 15)"
        )
        row = cursor.fetchone()
        avg_solar = row['avg_solar'] if row['avg_solar'] is not None else 0.0
        avg_load  = row['avg_load']  if row['avg_load']  is not None else 0.0
        conn.close()
        return avg_solar, avg_load
    except sqlite3.Error as e:
        config.logger.error(f"SQLite read error for {db_path}: {e}")
        return 0.0, 0.0


def process_and_summarize(mqtt_client):
    """
    Scans all home DBs in the data/ directory, classifies each as
    surplus / deficit / balanced, persists to the marketplace DB,
    and publishes a summary to MQTT.
    """
    if not os.path.exists(config.LOCAL_DB_DIR):
        config.logger.warning("No data directory found. Nothing to summarize.")
        return

    db_files = [f for f in os.listdir(config.LOCAL_DB_DIR) if f.endswith(".db")]
    summaries = []

    for db_file in db_files:
        home_id = db_file.replace(".db", "")
        avg_solar, avg_load = get_average_data(home_id)

        # Classify intent: 200W threshold separates surplus/deficit/balanced
        intent = "balanced"
        surplus_w = 0.0
        deficit_w = 0.0
        diff = avg_solar - avg_load

        if diff > 200:
            intent_kw = round(diff / 1000, 2)
            intent = f"{home_id} has {intent_kw}kw surplus"
            surplus_w = diff
        elif diff < -200:
            deficit_diff = avg_load - avg_solar
            intent_kw = round(deficit_diff / 1000, 2)
            intent = f"{home_id} needs {intent_kw}kw"
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

        # Persist to marketplace database
        try:
            with pg_engine.begin() as conn:
                conn.execute(
                    market_intents.insert().values(
                        home_id=summary['home_id'],
                        timestamp=now_str,
                        intent=summary['intent'],
                        surplus_w=summary['surplus_w'],
                        deficit_w=summary['deficit_w'],
                    )
                )
            config.logger.info(f"Saved market intent for {home_id}: {intent}")
        except Exception as e:
            config.logger.error(f"Failed to persist market intent for {home_id}: {e}")

    # Publish aggregated summary to MQTT
    if summaries:
        payload = json.dumps({"summaries": summaries})
        mqtt_client.publish(config.TOPIC_MARKET_SUMMARY, payload, qos=1)
        config.logger.info(f"Published market summary to {config.TOPIC_MARKET_SUMMARY}")


def run_summarizer():
    """Main loop: connects to broker, then summarizes every 15 seconds (demo speed)."""
    client = mqtt.Client("MarketSummarizer")

    try:
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
    except Exception as e:
        config.logger.error(f"Failed to connect to broker: {e}")
        return

    client.loop_start()

    try:
        while True:
            config.logger.info("Running 15-minute market summarizer cycle...")
            process_and_summarize(client)
            time.sleep(15)  # 15s in demo mode; would be 900s (15min) in production
    except KeyboardInterrupt:
        config.logger.info("Market summarizer stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    run_summarizer()
