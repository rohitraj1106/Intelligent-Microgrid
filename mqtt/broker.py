"""
Lightweight MQTT broker using amqtt for local development.
Runs on localhost:1883 (default MQTT port).
"""
import asyncio
import logging
from amqtt.broker import Broker

logging.basicConfig(level=logging.INFO)

BROKER_CONFIG = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
        }
    },
    "sys_interval": 10,
    "topic-check": {
        "enabled": False
    }
}

async def run_broker():
    broker = Broker(BROKER_CONFIG)
    await broker.start()
    print("=" * 50)
    print("  MQTT Broker running on localhost:1883")
    print("=" * 50)
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_broker())
