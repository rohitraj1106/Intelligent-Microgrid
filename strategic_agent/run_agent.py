"""
strategic_agent/run_agent.py
==========================
CLI entry point to launch the Strategic LLM Agent for a specific node.
"""
import argparse
import logging
import signal
import sys
import os
from time import sleep

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge import config
from edge.node import EdgeNode
from strategic_agent.agent import StrategicAgent
from strategic_agent.llm_client import GeminiClient
from strategic_agent.negotiation import MarketplaceClient

def main():
    parser = argparse.ArgumentParser(description="Microgrid Strategic LLM Agent")
    parser.add_argument("--node-id", default=config.HOME_ID, help="ID of the home node")
    parser.add_argument("--interval", type=int, default=config.AGENT_CYCLE_INTERVAL, help="Reasoning interval in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Perform one cycle and exit")
    parser.add_argument("--gemini-key", help="Gemini API Key (overrides env)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-20s  %(levelname)-8s  %(message)s",
    )
    logger = logging.getLogger("StrategicAgent.Runner")

    # 1. Initialize Components
    edge_node = EdgeNode(args.node_id)
    llm_client = GeminiClient(api_key=args.gemini_key)
    marketplace = MarketplaceClient(config.MARKETPLACE_URL)
    
    agent = StrategicAgent(
        node_id=args.node_id,
        edge_node=edge_node,
        llm_client=llm_client,
        marketplace=marketplace
    )

    # 2. Start Logic
    logger.info(f"Launching Strategic Agent for node: {args.node_id}")
    # edge_node.start() is NOT called here because the primary run_node 
    # process is already filling the database. We just need to READ.
    
    if args.dry_run:
        logger.info("Performing DRY RUN...")
        # Need to wait a moment for MQTT safely window to arrive (if running)
        # In a real dry run without other nodes, it will just use empty safe window.
        sleep(2)
        try:
            agent._mqtt.connect(config.MQTT_BROKER, config.MQTT_PORT)
            agent._mqtt.loop_start() 
            sleep(1)
        except Exception as e:
            logger.warning(f"Could not connect to MQTT broker ({e}). Proceeding with empty safe window.")
            
        agent.run_cycle()
        
        if agent._mqtt.is_connected():
            agent._mqtt.loop_stop()
        edge_node.stop()
        sys.exit(0)

    # Handle graceful shutdown
    def shutdown(sig, frame):
        logger.info("Shutting down...")
        agent.stop()
        edge_node.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    agent.start(interval_seconds=args.interval)
    
    # Keep main thread alive
    while True:
        sleep(1)

if __name__ == "__main__":
    main()
