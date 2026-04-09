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

from .database import SessionLocal
from .models import Order, OrderType, OrderStatus

logger = logging.getLogger("Marketplace.MarketMaker")

MARKET_MAKER_NODE_ID = "grid_reserve_node"
DEFAULT_SELL_PRICE = 5.50
DEFAULT_TARGET_ORDERS = 3
DEFAULT_INTERVAL_SEC = 15


def _seed_sell_orders(db, target_orders: int) -> int:
    pending = (
        db.query(Order)
        .filter(
            Order.node_id == MARKET_MAKER_NODE_ID,
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
            city="grid",
            status=OrderStatus.PENDING
        )
        db.add(order)
    if to_create:
        db.commit()
    return to_create


def start_market_maker(stop_event: threading.Event) -> threading.Thread:
    interval_sec = int(os.getenv("MARKET_MAKER_INTERVAL_SEC", str(DEFAULT_INTERVAL_SEC)))
    target_orders = int(os.getenv("MARKET_MAKER_TARGET_ORDERS", str(DEFAULT_TARGET_ORDERS)))

    def loop() -> None:
        logger.info("Market maker started.")
        while not stop_event.is_set():
            db = SessionLocal()
            try:
                created = _seed_sell_orders(db, target_orders)
                if created:
                    logger.info(f"Seeded {created} market maker SELL orders.")
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
