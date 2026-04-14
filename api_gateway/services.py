import json
import threading
from typing import Dict, Iterable, Optional

import paho.mqtt.client as mqtt
import requests

from .settings import settings


class MarketplaceProxy:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_json(self, path: str, params: Optional[Dict] = None):
        response = requests.get(
            f"{self.base_url}{path}",
            params=params,
            timeout=settings.REQUEST_TIMEOUT_SEC,
        )
        response.raise_for_status()
        return response.json()

    def stream_market_feed(self) -> Iterable[bytes]:
        with requests.get(
            f"{self.base_url}/market/feed",
            stream=True,
            timeout=(settings.REQUEST_TIMEOUT_SEC, None),
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines():
                if raw_line is None:
                    continue
                yield raw_line

    def get_health(self) -> Dict:
        response = requests.get(
            f"{self.base_url}/health",
            timeout=settings.REQUEST_TIMEOUT_SEC,
        )
        response.raise_for_status()
        return response.json()


class MQTTPublisher:
    def __init__(self, broker: str, port: int):
        self._client = mqtt.Client(client_id="api_gateway_publisher")
        self._connected = False
        self._lock = threading.Lock()
        self._client.on_connect = self._on_connect
        self._client.connect(broker, port, keepalive=30)
        self._client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        self._connected = rc == 0

    @property
    def connected(self) -> bool:
        return self._connected

    def publish_json(self, topic: str, payload: Dict, qos: int = 1) -> None:
        with self._lock:
            info = self._client.publish(topic, json.dumps(payload), qos=qos)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed (rc={info.rc})")

    def stop(self):
        self._client.loop_stop()
        self._client.disconnect()
