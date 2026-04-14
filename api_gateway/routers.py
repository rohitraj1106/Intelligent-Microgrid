import asyncio
import json
import queue
import threading
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from .auth import require_write_api_key
from .schemas import (
    CommandRequest,
    CommandResponse,
    NodeHealthResponse,
    NodeStateIngestRequest,
    NodeStateResponse,
)

router = APIRouter(prefix="/api", tags=["API Gateway"])


def _to_health(row: dict) -> NodeHealthResponse:
    telemetry = row.get("telemetry", {})
    orchestrator = row.get("orchestrator", {})
    return NodeHealthResponse(
        node_id=row["node_id"],
        city=row.get("city", "unknown"),
        soc_pct=float(telemetry.get("soc_pct", 0.0)),
        solar_kw=float(telemetry.get("power_solar_kw", 0.0)),
        load_kw=float(telemetry.get("power_load_kw", 0.0)),
        fsm_state=orchestrator.get("fsm_state"),
        strategy_status=orchestrator.get("strategy_status"),
        stale=bool(row.get("stale", False)),
        timestamp=row.get("timestamp", ""),
    )


def _resolve_command_topic(node_id: str, action: str) -> str:
    upper_action = action.upper()
    if upper_action in {"BUY", "SELL", "CHARGE", "DISCHARGE", "HOLD"}:
        return f"microgrid/{node_id}/llm_commands"
    if action in {"inject_fault", "reset_soc"}:
        return f"microgrid/{node_id}/simulator_commands"
    return f"microgrid/{node_id}/control"


@router.get("/system/health")
def get_system_health(request: Request):
    gateway = request.app.state.gateway

    marketplace_ok = False
    marketplace_error = None
    try:
        gateway.marketplace.get_health()
        marketplace_ok = True
    except Exception as exc:
        marketplace_error = str(exc)

    return {
        "api": {
            "status": "up",
        },
        "marketplace_upstream": {
            "status": "up" if marketplace_ok else "down",
            "error": marketplace_error,
        },
        "mqtt_bridge": {
            "status": "up" if gateway.mqtt_publisher.connected else "down",
        },
    }


@router.get("/market/orders")
def market_orders(request: Request, city: Optional[str] = Query(None)):
    marketplace = request.app.state.gateway.marketplace
    params = {"city": city} if city else None
    return marketplace.get_json("/orders", params=params)


@router.get("/market/stats")
def market_stats(request: Request, city: Optional[str] = Query(None)):
    marketplace = request.app.state.gateway.marketplace
    params = {"city": city} if city else None
    return marketplace.get_json("/stats", params=params)


@router.get("/market/trades")
def market_trades(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    city: Optional[str] = Query(None),
):
    marketplace = request.app.state.gateway.marketplace
    params = {"limit": limit}
    if city:
        params["city"] = city
    return marketplace.get_json("/trades", params=params)


@router.get("/market/wallets")
def market_wallets(request: Request, node_ids: str = Query(...)):
    marketplace = request.app.state.gateway.marketplace
    return marketplace.get_json("/wallets", params={"node_ids": node_ids})


@router.get("/nodes/{node_id}/state", response_model=NodeStateResponse)
def get_node_state(request: Request, node_id: str):
    row = request.app.state.gateway.state_store.get(node_id)
    if not row:
        raise HTTPException(status_code=404, detail="Node state not found")
    return row


@router.get("/nodes/health", response_model=list[NodeHealthResponse])
def get_nodes_health(
    request: Request,
    city: Optional[str] = Query(None),
    node_ids: Optional[str] = Query(None, description="Comma-separated list of node ids"),
):
    parsed_node_ids = node_ids.split(",") if node_ids else None
    rows = request.app.state.gateway.state_store.list(city=city, node_ids=parsed_node_ids)
    return [_to_health(row) for row in rows]


@router.post("/internal/orchestrator/state", status_code=status.HTTP_202_ACCEPTED)
def ingest_node_state(
    request: Request,
    payload: NodeStateIngestRequest,
    _api_key: str = Depends(require_write_api_key),
):
    row = request.app.state.gateway.state_store.upsert(payload)
    request.app.state.gateway.notifier.publish({"type": "node_state", "data": row})
    return {"status": "accepted", "node_id": payload.node_id}


@router.post("/orchestrator/commands", response_model=CommandResponse)
def send_command(
    request: Request,
    payload: CommandRequest,
    _api_key: str = Depends(require_write_api_key),
):
    topic = _resolve_command_topic(payload.node_id, payload.action)
    cmd_payload = payload.model_dump(exclude_none=True)
    request.app.state.gateway.mqtt_publisher.publish_json(topic, cmd_payload)
    return CommandResponse(
        status="published",
        node_id=payload.node_id,
        action=payload.action,
        published_topic=topic,
        note="Published to MQTT and consumed by runtime command handlers.",
    )


@router.get("/market/feed")
async def gateway_market_feed(request: Request):
    try:
        from importlib import import_module
        EventSourceResponse = import_module("sse_starlette.sse").EventSourceResponse
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSE support unavailable. Install sse-starlette.",
        ) from exc

    marketplace = request.app.state.gateway.marketplace
    notifier = request.app.state.gateway.notifier

    q: "queue.Queue[str]" = queue.Queue()
    stop_event = threading.Event()

    def _proxy_market_feed():
        try:
            for line in marketplace.stream_market_feed():
                if stop_event.is_set():
                    break
                if not line:
                    continue
                text = line.decode("utf-8", errors="ignore")
                if text.startswith("data:"):
                    q.put(text[5:].strip())
        except Exception:
            pass

    thread = threading.Thread(target=_proxy_market_feed, daemon=True)
    thread.start()

    async def _event_generator() -> AsyncGenerator[dict, None]:
        try:
            while True:
                while not q.empty():
                    item = q.get_nowait()
                    yield {"data": item}

                local = notifier.poll_nowait()
                if local is not None:
                    yield {
                        "event": local.get("type", "event"),
                        "data": json.dumps(local.get("data", {})),
                    }

                await asyncio.sleep(0.15)
        finally:
            stop_event.set()

    return EventSourceResponse(_event_generator())
