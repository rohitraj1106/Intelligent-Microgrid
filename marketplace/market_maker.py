"""
market_maker.py
===============
Background market maker that seeds synthetic SELL orders so BUYs can match.
"""
import logging
import os
import random
import threading
import time
from typing import Optional
from sqlalchemy import distinct

from .database import SessionLocal
from .models import Node, Order, OrderType, OrderStatus

logger = logging.getLogger("Marketplace.MarketMaker")

MARKET_MAKER_NODE_ID = "grid_reserve_node"
DEFAULT_SELL_PRICE = 5.50
DEFAULT_TARGET_ORDERS = 3
DEFAULT_INTERVAL_SEC = 15
DEFAULT_ACTIVE_CITIES = ["delhi", "noida", "gurugram", "chandigarh", "dehradun"]
MARKET_MAKER_API_HASH = "0" * 64


def _ensure_market_maker_node(db) -> None:
    existing = db.query(Node).filter(Node.id == MARKET_MAKER_NODE_ID).first()
    if existing:
        if existing.is_active != 1:
            existing.is_active = 1
            db.add(existing)
        return

    db.add(
        Node(
            id=MARKET_MAKER_NODE_ID,
            city="grid",
            api_key_hash=MARKET_MAKER_API_HASH,
            battery_cap_kwh=1000.0,
            is_active=1,
        )
    )


def _active_cities(db) -> list[str]:
    rows = (
        db.query(distinct(Node.city))
        .filter(Node.is_active == 1)
        .all()
    )
    cities = [str(row[0]).strip().lower() for row in rows if row and row[0]]
    return cities or DEFAULT_ACTIVE_CITIES


def _seed_sell_orders_for_city(db, city: str, target_orders: int) -> int:
    pending = (
        db.query(Order)
        .filter(
            Order.node_id == MARKET_MAKER_NODE_ID,
            Order.city == city,
            Order.order_type == OrderType.SELL,
            Order.status.in_([OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED])
        )
        .count()
    )

    to_create = max(0, target_orders - pending)
    for _ in range(to_create):
        quantity_kwh = round(random.uniform(4.0, 6.0), 3)
        order = Order(
            node_id=MARKET_MAKER_NODE_ID,
            order_type=OrderType.SELL,
            quantity_kwh=quantity_kwh,
            remaining_kwh=quantity_kwh,
            price_per_kwh=DEFAULT_SELL_PRICE,
            city=city,
            status=OrderStatus.PENDING
        )
        db.add(order)
    return to_create


def start_market_maker(stop_event: threading.Event) -> threading.Thread:
    interval_sec = int(os.getenv("MARKET_MAKER_INTERVAL_SEC", str(DEFAULT_INTERVAL_SEC)))
    target_orders = int(os.getenv("MARKET_MAKER_TARGET_ORDERS", str(DEFAULT_TARGET_ORDERS)))

    def loop() -> None:
        logger.info("Market maker started.")
        while not stop_event.is_set():
            db = SessionLocal()
            try:
                _ensure_market_maker_node(db)
                created_total = 0
                for city in _active_cities(db):
                    created_total += _seed_sell_orders_for_city(db, city, target_orders)
                if created_total:
                    db.commit()
                    logger.info(f"Seeded {created_total} market maker SELL orders across active cities.")
                else:
                    db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Market maker error: {e}")
            finally:
                db.close()
            stop_event.wait(interval_sec)
        logger.info("Market maker stopped.")

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread
