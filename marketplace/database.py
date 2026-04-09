"""
Database configuration for the P2P Energy Marketplace.
Supports PostgreSQL in strict-spec deployments with SQLite fallback for local runs.
"""

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv


# Load .env so MARKETPLACE_DATABASE_URL can be set once for all marketplace commands.
load_dotenv()

_default_sqlite_url = "sqlite:///./marketplace.db"

# Preferred for strict stage setup: export MARKETPLACE_DATABASE_URL with postgres URL.
DATABASE_URL = (
    os.getenv("MARKETPLACE_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or _default_sqlite_url
)

_is_sqlite = DATABASE_URL.startswith("sqlite")

# For SQLite, we need check_same_thread=False for FastAPI's async access
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
    echo=False,           # Set True for SQL debug logging
    pool_pre_ping=True,   # Reconnect on stale connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session, auto-closes after request."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist. Called on app startup."""
    Base.metadata.create_all(bind=engine)
    if _is_sqlite:
        _ensure_sqlite_compat_columns()


def _ensure_sqlite_compat_columns() -> None:
    """Backfills missing columns in older SQLite files used during local stage gating."""
    required_columns = {
        "orders": {
            "city": "TEXT",
        },
        "trades": {
            "city": "TEXT",
        },
    }

    with engine.begin() as conn:
        for table_name, cols in required_columns.items():
            existing = {
                row[1]
                for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            }
            for col_name, col_type in cols.items():
                if col_name not in existing:
                    conn.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                    )
