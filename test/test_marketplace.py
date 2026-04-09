"""
Focused regression tests for marketplace stage-gate fixes.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marketplace.database import Base
from marketplace.models import Node, Order, OrderStatus, OrderType, Settlement, Trade
from marketplace.repositories import (
    NodeRepository,
    OrderRepository,
    SettlementRepository,
    TradeRepository,
    WalletRepository,
)
from marketplace.services import OrderService, SettlementService
from marketplace.engine import CDAEngine
from marketplace.events import EventBus


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_node(db, node_id: str, city: str):
    db.add(
        Node(
            id=node_id,
            city=city,
            api_key_hash=f"hash_{node_id}",
            battery_cap_kwh=10.0,
            is_active=1,
        )
    )
    db.flush()


def test_settlement_is_persisted_and_idempotent(db_session):
    _add_node(db_session, "Delhi_01", "Delhi")
    _add_node(db_session, "Noida_01", "Noida")

    buy_order = Order(
        node_id="Delhi_01",
        order_type=OrderType.BUY,
        quantity_kwh=2.0,
        remaining_kwh=0.0,
        price_per_kwh=7.0,
        status=OrderStatus.FILLED,
        city="Delhi",
    )
    sell_order = Order(
        node_id="Noida_01",
        order_type=OrderType.SELL,
        quantity_kwh=2.0,
        remaining_kwh=0.0,
        price_per_kwh=6.0,
        status=OrderStatus.FILLED,
        city="Noida",
    )
    db_session.add(buy_order)
    db_session.add(sell_order)
    db_session.flush()

    trade = Trade(
        buyer_node_id="Delhi_01",
        seller_node_id="Noida_01",
        buyer_order_id=buy_order.id,
        seller_order_id=sell_order.id,
        quantity_kwh=2.0,
        price_per_kwh=6.5,
        total_cost=13.0,
        city="Delhi",
        executed_at=datetime.now(timezone.utc),
    )
    db_session.add(trade)
    db_session.flush()

    service = SettlementService(
        wallet_repo=WalletRepository(db_session),
        settlement_repo=SettlementRepository(db_session),
        event_bus=EventBus(),
    )

    first = service.settle_trade(trade)
    second = service.settle_trade(trade)

    assert first.id == second.id
    assert db_session.query(Settlement).count() == 1

    buyer_wallet = WalletRepository(db_session).get_or_create("Delhi_01")
    seller_wallet = WalletRepository(db_session).get_or_create("Noida_01")
    assert buyer_wallet.balance_inr == pytest.approx(-13.0)
    assert seller_wallet.balance_inr == pytest.approx(13.0)


def test_order_service_derives_city_from_node_profile(db_session):
    _add_node(db_session, "Delhi_02", "Delhi")

    service = OrderService(
        order_repo=OrderRepository(db_session),
        trade_repo=TradeRepository(db_session),
        node_repo=NodeRepository(db_session),
        engine=CDAEngine(),
        event_bus=EventBus(),
    )

    result = service.place_order(
        node_id="Delhi_02",
        order_type="buy",
        quantity_kwh=1.0,
        price_per_kwh=7.5,
        city=None,
    )

    assert result["order"].city == "Delhi"


def test_counterparty_matching_is_local_city_only(db_session):
    _add_node(db_session, "Delhi_03", "Delhi")
    _add_node(db_session, "Delhi_seller", "Delhi")
    _add_node(db_session, "Noida_seller", "Noida")
    _add_node(db_session, "Dehradun_seller", "Dehradun")

    repo = OrderRepository(db_session)

    db_session.add_all(
        [
            Order(
                node_id="Delhi_seller",
                order_type=OrderType.SELL,
                quantity_kwh=1.0,
                remaining_kwh=1.0,
                price_per_kwh=6.8,
                status=OrderStatus.PENDING,
                city="Delhi",
            ),
            Order(
                node_id="Noida_seller",
                order_type=OrderType.SELL,
                quantity_kwh=1.0,
                remaining_kwh=1.0,
                price_per_kwh=6.2,
                status=OrderStatus.PENDING,
                city="Noida",
            ),
            Order(
                node_id="Dehradun_seller",
                order_type=OrderType.SELL,
                quantity_kwh=1.0,
                remaining_kwh=1.0,
                price_per_kwh=5.9,
                status=OrderStatus.PENDING,
                city="Dehradun",
            ),
        ]
    )
    db_session.flush()

    counterparties = repo.get_pending_counterparties(
        order_type=OrderType.BUY,
        exclude_node_id="Delhi_03",
        reference_city="Delhi",
    )

    assert len(counterparties) == 1
    assert counterparties[0].node_id == "Delhi_seller"
