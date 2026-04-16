"""
routers.py
==========
FastAPI controllers for all marketplace endpoints.
Thin controller design: Logic delegated to services.
Dependency injection used to provide repositories and services.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from datetime import datetime, timezone

from .database import get_db
from .models import Order, Trade, Node, Wallet, OrderType, OrderStatus
from .schemas import (
    OrderCreate, OrderResponse, TradeResponse, 
    MarketSnapshot, MarketStats, NodeCreate, NodeResponse, 
    WalletResponse, SettlementResponse, SettlementRequest
)
from .repositories import (
    OrderRepository, TradeRepository, NodeRepository, 
    WalletRepository, SettlementRepository, MarketAnalyticsRepository
)
from .services import OrderService, SettlementService, WalletService
from .engine import CDAEngine
from .events import EventBus, SSENotifier
from .auth import authenticate_node, APIKeyAuthService

# ── Router Group Definitions ──
router = APIRouter()

# Global singletons
_event_bus = EventBus()
_sse_notifier = SSENotifier()

# Flag to ensure we only wire handlers once
_handlers_wired = False

def wire_event_handlers(services):
    """Wires standard observers to the event bus once."""
    global _handlers_wired
    if _handlers_wired:
        return
        
    _event_bus.subscribe("trade_executed", _sse_notifier.on_market_event)
    _event_bus.subscribe("order_placed",   _sse_notifier.on_market_event)
    
    _handlers_wired = True

# ── Dependency Provider for assembled Services ──

def get_services(db=Depends(get_db)):
    """Assembles all services for inclusion in routes."""
    order_repo    = OrderRepository(db)
    trade_repo    = TradeRepository(db)
    node_repo     = NodeRepository(db)
    wallet_repo   = WalletRepository(db)
    settlement_repo = SettlementRepository(db)
    
    # Matching Engine Strategy (CDA)
    engine        = CDAEngine()
    
    # Assembled Services
    order_service      = OrderService(order_repo, trade_repo, node_repo, engine, _event_bus)
    settlement_service = SettlementService(wallet_repo, settlement_repo, _event_bus)
    wallet_service     = WalletService(wallet_repo)
    analytics_repo     = MarketAnalyticsRepository(db)
    
    services = {
        "order": order_service,
        "settlement": settlement_service,
        "wallet": wallet_service,
        "analytics": analytics_repo,
        "nodes": node_repo,
        "db": db
    }

    # Wire handlers exactly once
    wire_event_handlers(services)
    
    return services


# ── Market Public Endpoints ──

@router.get("/orders", response_model=MarketSnapshot, tags=["Market"])
def get_order_book(
    city: Optional[str] = None, 
    services=Depends(get_services)
):
    """View current pending orders (Snapshot)."""
    db = services["db"]
    query = db.query(Order).filter(Order.status.in_([OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]))
    if city:
        query = query.filter(Order.city == city)
        
    orders = query.all()
    buys = [o for o in orders if o.order_type == OrderType.BUY]
    sells = [o for o in orders if o.order_type == OrderType.SELL]
    
    return {
        "pending_buy_orders": buys,
        "pending_sell_orders": sells,
        "total_buy_volume_kwh": sum(o.remaining_kwh for o in buys),
        "total_sell_volume_kwh": sum(o.remaining_kwh for o in sells),
        "best_buy_price": max((o.price_per_kwh for o in buys), default=None),
        "best_sell_price": min((o.price_per_kwh for o in sells), default=None),
        "spread": (
            round(
                max((o.price_per_kwh for o in buys), default=None)
                - min((o.price_per_kwh for o in sells), default=None),
                2,
            )
            if buys and sells
            else None
        ),
    }

@router.get("/stats", response_model=MarketStats, tags=["Market"])
def get_market_statistics(
    city: Optional[str] = Query(None, description="Filter by city"),
    services=Depends(get_services)
):
    """Aggregate marketplace performance statistics."""
    stats = services["analytics"].get_stats(city=city)
    stats["city"] = city
    return stats


@router.get("/metrics", response_model=MarketStats, tags=["Market"])
def get_market_metrics(
    city: Optional[str] = Query(None, description="Filter by city"),
    services=Depends(get_services)
):
    """Plan-compatible alias for market statistics."""
    stats = services["analytics"].get_stats(city=city)
    stats["city"] = city
    return stats

@router.get("/trades", response_model=List[TradeResponse], tags=["Market"])
def get_recent_trades(
    limit: int = 20,
    city: Optional[str] = None,
    node_id: Optional[str] = Query(None, description="Filter by node id"),
    services=Depends(get_services),
):
    """Audit trail of recent executions."""
    trade_repo = TradeRepository(services["db"])
    return trade_repo.get_recent(n=limit, city=city, node_id=node_id)


@router.post("/trades/settle", response_model=SettlementResponse, tags=["Finance"])
def settle_trade(
    payload: SettlementRequest,
    auth_node_id: str = Depends(authenticate_node),
    services=Depends(get_services),
):
    """Idempotently settle a confirmed trade by trade ID."""
    trade = TradeRepository(services["db"]).get_by_id(payload.trade_id)
    if not trade:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Trade not found")

    if auth_node_id not in (trade.buyer_node_id, trade.seller_node_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only buyer or seller of the trade can request settlement",
        )

    return services["settlement"].settle_trade(trade)


# ── Private Write Endpoints (Authenticated) ──

@router.post("/orders", response_model=dict, tags=["Trading"], status_code=status.HTTP_201_CREATED)
def place_order(
    payload: OrderCreate,
    auth_node_id: str = Depends(authenticate_node),
    services=Depends(get_services)
):
    """Authenticated endpoint to place a buy or sell order."""
    # Ensure node_id in request body matches authorized key
    if payload.node_id != auth_node_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot place order for node {payload.node_id}; authenticated as {auth_node_id}"
        )
        
    # Check if node has credit to place a BUY order (Phase 3)
    if payload.order_type == "buy":
        est_cost = payload.quantity_kwh * payload.price_per_kwh
        if not services["settlement"].can_afford(auth_node_id, est_cost):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient balance or credit limit reached"
            )

    result = services["order"].place_order(
        node_id       = auth_node_id,
        order_type    = payload.order_type,
        quantity_kwh  = payload.quantity_kwh,
        price_per_kwh = payload.price_per_kwh,
        city          = payload.city
    )

    # Settle trades using the current request-scoped DB session.
    for trade in result["trades"]:
        services["settlement"].settle_trade(trade)
    
    return {
        "order": OrderResponse.model_validate(result["order"]),
        "trades": [TradeResponse.model_validate(t) for t in result["trades"]],
        "matched": result["matched"]
    }

@router.delete("/orders/{order_id}", response_model=OrderResponse, tags=["Trading"])
def cancel_order(
    order_id: int,
    auth_node_id: str = Depends(authenticate_node),
    services=Depends(get_services)
):
    """Cancel a pending order."""
    order = services["order"].cancel_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found or already completed")
    if order.node_id != auth_node_id:
        raise HTTPException(403, "Cannot cancel someone else's order")
    return order


# ── Admin & Node Management ──

@router.post("/nodes", response_model=dict, tags=["Admin"])
def register_node(
    payload: NodeCreate,
    services=Depends(get_services)
):
    """On-boarding endpoint for new microgrid homes."""
    node_repo = services["nodes"]
    if node_repo.get_by_id(payload.id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Node already exists")

    plaintext_key, hashed_key = APIKeyAuthService.generate_api_key()
    
    new_node = Node(
        id              = payload.id,
        city            = payload.city,
        api_key_hash    = hashed_key,
        battery_cap_kwh = payload.battery_cap_kwh,
        is_active       = 1
    )
    node_repo.save(new_node)
    
    return {
        "node": NodeResponse.model_validate(new_node),
        "api_key": plaintext_key,
        "warning": "Copy this API key now; it will never be shown again!"
    }


@router.post("/nodes/{node_id}/rotate-key", response_model=dict, tags=["Admin"])
def rotate_node_api_key(
    node_id: str,
    services=Depends(get_services)
):
    """Rotate and return a fresh API key for an existing node (admin utility)."""
    node_repo = services["nodes"]
    node = node_repo.get_by_id(node_id)
    if not node:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Node not found")

    plaintext_key, hashed_key = APIKeyAuthService.generate_api_key()
    node.api_key_hash = hashed_key
    node_repo.save(node)

    return {
        "node_id": node.id,
        "api_key": plaintext_key,
        "warning": "API key rotated. Replace any previous key for this node."
    }

@router.get("/wallet/{node_id}", response_model=WalletResponse, tags=["Finance"])
def get_node_wallet(
    node_id: str, 
    services=Depends(get_services)
):
    """Check financial standing of a node."""
    return services["wallet"].get_wallet(node_id)


@router.get("/leaderboard", response_model=List[WalletResponse], tags=["Market"])
def get_leaderboard(
    limit: int = Query(15, ge=1, le=50),
    services=Depends(get_services)
):
    """Returns top nodes by wallet balance."""
    wallet_repo = WalletRepository(services["db"])
    return wallet_repo.get_top(limit=limit)


@router.get("/wallets", response_model=List[WalletResponse], tags=["Finance"])
def get_wallets(
    node_ids: str = Query(..., description="Comma-separated node IDs"),
    services=Depends(get_services),
):
    """Bulk wallet lookup for dashboard usage."""
    wallet_service = services["wallet"]
    ids = [nid.strip() for nid in node_ids.split(",") if nid.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="node_ids must include at least one id")

    wallets = [wallet_service.get_wallet(nid) for nid in ids]
    return wallets


# ── Live Market Feed (SSE) ──

@router.get("/market/feed", tags=["Real-time"])
async def market_event_feed():
    """SSE Stream providing real-time ticker data."""
    try:
        from importlib import import_module
        EventSourceResponse = import_module("sse_starlette.sse").EventSourceResponse
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSE support unavailable. Install sse-starlette to enable /market/feed.",
        ) from exc
    
    async def event_generator():
        queue = _sse_notifier.subscribe()
        try:
            while True:
                data = await queue.get()
                yield {"data": data}
        finally:
            _sse_notifier.unsubscribe(queue)

    return EventSourceResponse(event_generator())
