"""
test/test_edge_database.py
==========================
Regression tests for EdgeDatabase recency behavior.
"""
from edge.database import EdgeDatabase
from edge.models import TelemetryReading


def _reading(node_id: str, ts: str, soc: float, load_kw: float = 1.0, solar_kw: float = 0.2) -> TelemetryReading:
    return TelemetryReading(
        node_id=node_id,
        timestamp=ts,
        voltage_v=230.0,
        current_a=1.0,
        power_solar_kw=solar_kw,
        power_load_kw=load_kw,
        soc_pct=soc,
        battery_power_kw=solar_kw - load_kw,
        grid_import_kw=max(0.0, load_kw - solar_kw),
        grid_export_kw=max(0.0, solar_kw - load_kw),
    )


def test_get_latest_uses_ingestion_order(tmp_path):
    db = EdgeDatabase("delhi_01", db_dir=str(tmp_path))
    db.initialize()

    # Simulate old future rows from a prior run, then newly ingested current rows.
    db.insert_reading(_reading("delhi_01", "2026-04-01T23:45:00", 9.8))
    db.insert_reading(_reading("delhi_01", "2026-03-30T14:00:00", 100.0))

    latest = db.get_latest(1)[0]
    assert latest.timestamp == "2026-03-30T14:00:00"
    assert latest.soc_pct == 100.0

    db.close()


def test_summary_excludes_future_timestamp_rows(tmp_path):
    db = EdgeDatabase("delhi_01", db_dir=str(tmp_path))
    db.initialize()

    # Older ingested row with future timestamp must not contaminate a newer ingest cycle.
    db.insert_reading(_reading("delhi_01", "2026-04-01T23:45:00", 9.8, load_kw=0.2, solar_kw=0.0))
    db.insert_reading(_reading("delhi_01", "2026-03-30T13:45:00", 99.0, load_kw=1.1, solar_kw=0.2))
    db.insert_reading(_reading("delhi_01", "2026-03-30T14:00:00", 100.0, load_kw=1.2, solar_kw=0.1))

    summary = db.get_summary(hours=1)
    assert summary is not None
    assert summary.as_of == "2026-03-30T14:00:00"
    assert summary.current_soc_pct == 100.0

    # Ensure the future row did not reduce averages to near-zero values.
    assert summary.avg_load_kw >= 1.0
    assert summary.avg_solar_kw <= 0.2

    db.close()
