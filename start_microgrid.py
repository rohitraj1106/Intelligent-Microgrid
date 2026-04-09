import subprocess
import time
import sys
import signal
import os
from concurrent.futures import ThreadPoolExecutor

# ANSI Decor
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_PURPLE = "\033[95m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"

# Service Map with Metadata
SERVICES = [
    {
        "id": "BROKER",
        "name": "MQTT Hub",
        "cmd": [sys.executable, "-m", "edge.broker"],
        "color": C_BLUE,
        "note": "Central message exchange (Port 1883/9001)"
    },
    {
        "id": "MARKET",
        "name": "Energy Ex",
        "cmd": ["uvicorn", "marketplace.main:app", "--port", "8000"],
        "color": C_PURPLE,
        "note": "Double-auction trading floor (Port 8000)"
    },
    {
        "id": "INGEST",
        "name": "Edge Ingest",
        "cmd": [sys.executable, "-m", "edge.run_node"],
        "color": C_GREEN,
        "note": "Ingesting telemetry for 75 nodes"
    },
    {
        "id": "PHYSIC",
        "name": "Physics Sim",
        "cmd": [sys.executable, "-m", "edge.run_simulator", "--step", "15"],
        "color": C_YELLOW,
        "note": "15min simulated time per 10s tick"
    },
    {
        "id": "ORCH",
        "name": "Tactical Governor",
        "cmd": [sys.executable, "-m", "orchestrator.multi_orchestrator_runner"],
        "color": C_CYAN,
        "note": "Safety FSM for all 75 nodes (Multiplexed)"
    },
    {
        "id": "AI_AGENT",
        "name": "Strategic Agent",
        "cmd": [sys.executable, "-m", "strategic_agent.multi_agent_runner"],
        "color": C_BOLD + C_CYAN,
        "note": "Active-City LLM Intelligence (High Density)"
    }
]

def stream_logs(process, service):
    """Wait for child process to output logs and print them with color-coded prefix."""
    prefix = f"{service['color']}[{service['id']:^8}]{C_RESET}"
    for line in iter(process.stdout.readline, ""):
        if not line:
            break
        print(f"{prefix} {line.strip()}")


def purge_stale_databases():
    """Fix 4: Delete all old SQLite databases so new run starts completely fresh."""
    import glob
    project_root = os.path.dirname(os.path.abspath(__file__))
    patterns = [
        os.path.join(project_root, "data", "edge", "*.db"),
        os.path.join(project_root, "data", "edge", "*.db-shm"),
        os.path.join(project_root, "data", "edge", "*.db-wal"),
        os.path.join(project_root, "marketplace.db"),
        os.path.join(project_root, "marketplace.db-shm"),
        os.path.join(project_root, "marketplace.db-wal"),
    ]
    count = 0
    for pattern in patterns:
        for f in glob.glob(pattern):
            os.remove(f)
            count += 1
    print(f"{C_GREEN}[CLEAN]{C_RESET}   Purged {count} stale database files. Fresh start guaranteed.")


def register_demo_node_and_get_key(marketplace_url: str = "http://localhost:8000") -> str:
    """Fix 5: Register delhi_00 in marketplace and return its API key."""
    import requests
    from edge.config import NODE_CONFIGS
    demo_node = "delhi_00"
    if demo_node not in NODE_CONFIGS:
        return ""
    cfg = NODE_CONFIGS[demo_node]
    payload = {
        "id": demo_node,
        "city": cfg["city"],
        "battery_cap_kwh": cfg["battery_capacity_wh"] / 1000.0
    }
    try:
        resp = requests.post(f"{marketplace_url}/nodes", json=payload, timeout=5)
        if resp.status_code == 200:
            key = resp.json().get("api_key", "")
            print(f"{C_GREEN}[AUTH]{C_RESET}    delhi_00 registered. API key obtained.")
            return key
        elif resp.status_code == 400:  # Already registered from a previous run that had DB
            print(f"{C_YELLOW}[AUTH]{C_RESET}    delhi_00 already registered (stale DB?). Skipping.")
            return ""
        else:
            print(f"{C_RED}[AUTH]{C_RESET}    Registration failed: {resp.status_code}. Orders will use demo bypass.")
            return ""
    except Exception as e:
        print(f"{C_RED}[AUTH]{C_RESET}    Could not reach marketplace: {e}")
        return ""

def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    processes = []

    os.system('clear')
    print(f"\n{C_BOLD}⚡ INTELLIGENT MICROGRID COMMAND CENTER v2.2{C_RESET}")
    print(f"{C_BOLD}============================================{C_RESET}")

    # Fix 4: Purge stale databases FIRST — before any service starts
    purge_stale_databases()

    # Fix 5a: Set DEMO_MODE and API keys in THIS process's env BEFORE any Popen.
    # All subprocesses (uvicorn, python -m ...) inherit os.environ automatically.
    os.environ["DEMO_MODE"] = "true"
    from dotenv import load_dotenv
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        print(f"{C_GREEN}[ENV]{C_RESET}     GEMINI_API_KEY loaded. DEMO_MODE=true enabled.")
    else:
        print(f"{C_YELLOW}[ENV]{C_RESET}     WARNING: No GEMINI_API_KEY in .env. LLM will not work.")

    print(f"\nInitializing {len(SERVICES)} high-density microservices...\n")

    def launch(s):
        """Launch a service subprocess with staggered delay."""
        print(f" {s['color']}▶{C_RESET} {s['name']:<18} | {s['note']}")
        cwd = os.path.join(project_root, s.get("cwd", ""))
        p = subprocess.Popen(
            s["cmd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env=os.environ.copy(),   # Explicit copy so DEMO_MODE is always present
        )
        return p

    # Phase 1: Launch MQTT Broker first
    broker_svc = next(s for s in SERVICES if s["id"] == "BROKER")
    p_broker = launch(broker_svc)
    processes.append((p_broker, broker_svc))
    time.sleep(2.0)   # Give mosquitto time to bind ports

    # Phase 2: Launch Marketplace — it seeds the 75 nodes on startup
    market_svc = next(s for s in SERVICES if s["id"] == "MARKET")
    p_market = launch(market_svc)
    processes.append((p_market, market_svc))
    print(f"\n{C_CYAN}[SETUP]{C_RESET}   Waiting for Marketplace to seed 75 nodes...")
    time.sleep(4.0)   # Give uvicorn time to start + run _seed_demo_nodes()

    # Phase 3: Launch remaining services
    for s in SERVICES:
        if s["id"] in ("BROKER", "MARKET"):
            continue
        p = launch(s)
        processes.append((p, s))
        time.sleep(1.2)

    def shutdown(sig, frame):
        print(f"\n\n{C_RED}{C_BOLD}[SYSTEM TERMINATED]{C_RESET} Sweeping child processes...")
        for p, s in processes:
            p.terminate()
        print(f"{C_GREEN}Done!{C_RESET} All servers released cleanly.\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    print(f"\n{C_GREEN}{C_BOLD}STATUS:{C_RESET} ALL PYTHON MICROSERVICES OPERATIONAL.")
    print(f"{C_YELLOW}{C_BOLD}NEXT STEP:{C_RESET} Open a NEW terminal, run `cd dashboard && npm run dev` to start the UI.")
    print(f"{C_BOLD}--------------------------------------------{C_RESET}\n")

    # Launch log streams in background threads
    with ThreadPoolExecutor(max_workers=len(processes)) as executor:
        for p, s in processes:
            executor.submit(stream_logs, p, s)

if __name__ == "__main__":
    main()

