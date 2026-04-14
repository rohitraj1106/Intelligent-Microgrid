from contextlib import asynccontextmanager
from dataclasses import dataclass
import queue

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import router
from .services import MarketplaceProxy, MQTTPublisher
from .settings import settings
from .state_store import NodeStateStore


class LocalEventNotifier:
    def __init__(self):
        self._queue: "queue.Queue[dict]" = queue.Queue()

    def publish(self, event: dict) -> None:
        self._queue.put(event)

    def poll_nowait(self):
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None


@dataclass
class AppState:
    marketplace: MarketplaceProxy
    mqtt_publisher: MQTTPublisher
    state_store: NodeStateStore
    notifier: LocalEventNotifier


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.gateway = AppState(
        marketplace=MarketplaceProxy(settings.MARKETPLACE_BASE_URL),
        mqtt_publisher=MQTTPublisher(settings.MQTT_BROKER, settings.MQTT_PORT),
        state_store=NodeStateStore(settings.NODE_STATE_TTL_SEC),
        notifier=LocalEventNotifier(),
    )

    yield

    app.state.gateway.mqtt_publisher.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["Gateway"])
def health():
    return {
        "status": "healthy",
        "service": "microgrid-api-gateway",
        "version": settings.APP_VERSION,
        "marketplace_base_url": settings.MARKETPLACE_BASE_URL,
    }
