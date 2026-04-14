import os


class Settings:
    APP_NAME = "Microgrid Frontend API Gateway"
    APP_VERSION = "1.0.0"

    HOST = os.getenv("API_GATEWAY_HOST", "0.0.0.0")
    PORT = int(os.getenv("API_GATEWAY_PORT", "8100"))

    MARKETPLACE_BASE_URL = os.getenv("MARKETPLACE_BASE_URL", "http://localhost:8000")
    MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

    # Writes/internal endpoints are protected by this shared key.
    GATEWAY_WRITE_API_KEY = os.getenv("GATEWAY_WRITE_API_KEY", "demo-write-key")

    NODE_STATE_TTL_SEC = int(os.getenv("NODE_STATE_TTL_SEC", "120"))
    REQUEST_TIMEOUT_SEC = float(os.getenv("API_GATEWAY_TIMEOUT_SEC", "5"))


settings = Settings()
