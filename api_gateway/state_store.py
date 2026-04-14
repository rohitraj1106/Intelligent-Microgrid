import threading
import time
from typing import Dict, List, Optional

from .schemas import NodeStateIngestRequest


class NodeStateStore:
    def __init__(self, ttl_sec: int):
        self._ttl_sec = ttl_sec
        self._lock = threading.Lock()
        self._states: Dict[str, dict] = {}

    def upsert(self, payload: NodeStateIngestRequest) -> dict:
        now = time.time()
        record = {
            "node_id": payload.node_id,
            "city": payload.city,
            "timestamp": payload.timestamp,
            "telemetry": payload.telemetry.model_dump(),
            "orchestrator": payload.orchestrator.model_dump(),
            "ingested_at": now,
        }
        with self._lock:
            self._states[payload.node_id] = record
        return record

    def get(self, node_id: str) -> Optional[dict]:
        with self._lock:
            record = self._states.get(node_id)
        if not record:
            return None
        return self._apply_stale(record)

    def list(self, city: Optional[str] = None, node_ids: Optional[List[str]] = None) -> List[dict]:
        with self._lock:
            values = list(self._states.values())

        if city:
            city_normalized = city.lower()
            values = [v for v in values if v.get("city", "").lower() == city_normalized]
        if node_ids:
            lookup = {n.strip() for n in node_ids if n.strip()}
            values = [v for v in values if v.get("node_id") in lookup]

        return [self._apply_stale(v) for v in values]

    def _apply_stale(self, record: dict) -> dict:
        copy = dict(record)
        copy["stale"] = (time.time() - copy.get("ingested_at", 0)) > self._ttl_sec
        return copy
