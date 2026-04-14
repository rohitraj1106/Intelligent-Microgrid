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

# Enforce Postgres for production-grade concurrency across 75 nodes
DATABASE_URL = os.getenv("MARKETPLACE_DATABASE_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("MARKETPLACE_DATABASE_URL not set to a postgresql:// connection string in .env")

_is_sqlite = False

# Optimized for 75 nodes: Large pool and overflow for sudden spikes in trading activity
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_timeout=45,
    pool_pre_ping=True,
    echo=False
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
