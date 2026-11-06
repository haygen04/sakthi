"""Unit and integration tests for Phase 1: Data Extraction."""

import sqlite3
import pytest
from datetime import date
from pathlib import Path
import pandas as pd

from etl.extract import (
    parse_iso_week,
    parse_month,
    resolve_date_range,
    retry_operation,
    CSVFallbackConnector,
    write_to_staging,
    run_extraction,
)
from etl.db_init import init_sqlite_db

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_parse_iso_week():
    """Verify ISO week parsing produces correct Monday to Sunday date range."""
    # Week 45 of 2026 starts Monday 2026-11-02 and ends Sunday 2026-11-08
    start, end = parse_iso_week("2026-W45")
    assert start == date(2026, 11, 2)
    assert end == date(2026, 11, 8)

    # Lowercase & hyphenated variations
    start_lc, end_lc = parse_iso_week("2026-w45")
    assert start_lc == date(2026, 11, 2)
    assert end_lc == date(2026, 11, 8)

    # Invalid week strings should raise ValueError
    with pytest.raises(ValueError):
        parse_iso_week("invalid-week")
    with pytest.raises(ValueError):
        parse_iso_week("2026-W999")


def test_parse_month():
    """Verify month parsing sets start of month and last day of month correctly."""
    start, end = parse_month("2026-11")
    assert start == date(2026, 11, 1)
    assert end == date(2026, 11, 30)

    # Leap year test
    start_feb, end_feb = parse_month("2024-02")
    assert start_feb == date(2024, 2, 1)
    assert end_feb == date(2024, 2, 29)


def test_resolve_date_range():
    """Verify precedence and resolution across week, month, and explicit dates."""
    # Week
    s, e, key = resolve_date_range(week="2026-W45")
    assert key == "2026-W45"
    assert s == date(2026, 11, 2)
    assert e == date(2026, 11, 8)

    # Month
    s, e, key = resolve_date_range(month="2026-11")
    assert key == "2026-11"
    assert s == date(2026, 11, 1)
    assert e == date(2026, 11, 30)

    # Explicit Range
    s, e, key = resolve_date_range(start_date="2026-11-02", end_date="2026-11-04")
    assert key == "2026-11-02_to_2026-11-04"
    assert s == date(2026, 11, 2)
    assert e == date(2026, 11, 4)

    # Error when start > end
    with pytest.raises(ValueError):
        resolve_date_range(start_date="2026-11-05", end_date="2026-11-01")


def test_retry_operation_logic():
    """Verify retry logic recovers from transient failures and raises after max attempts."""
    attempts = 0

    def flaky_func():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Transient network hiccup")
        return "success"

    result = retry_operation(flaky_func, max_retries=3, initial_delay=0.01, backoff=1.0)
    assert result == "success"
    assert attempts == 3

    # Always failing function
    def doomed_func():
        raise TimeoutError("Dead endpoint")

    with pytest.raises(RuntimeError):
        retry_operation(doomed_func, max_retries=2, initial_delay=0.01, backoff=1.0)


def test_csv_fallback_connector_date_filtering():
    """Verify CSV connector filters records strictly within the requested date window."""
    csv_dir = ROOT_DIR / "sample_data" / "pms_exports"
    connector = CSVFallbackConnector(csv_dir)

    # Extract single day (2026-11-02)
    df_prod, df_rej = connector.extract(date(2026, 11, 2), date(2026, 11, 2))
    assert not df_prod.empty
    assert (df_prod["production_date"] == "2026-11-02").all()

    assert not df_rej.empty
    assert (df_rej["production_date"] == "2026-11-02").all()


def test_write_to_staging_table(tmp_path):
    """Verify writing records into staging tables with batch metadata."""
    test_db = tmp_path / "test_stage.db"
    schema_file = ROOT_DIR / "sql" / "schema.sql"
    seed_file = ROOT_DIR / "sql" / "seed_pms_data.sql"
    init_sqlite_db(test_db, schema_file, seed_file)

    sample_prod = pd.DataFrame([{
        "log_id": "TEST-001",
        "production_date": "2026-11-02",
        "shop_code": "FOUNDRY",
        "shift_code": "SHIFT_A",
        "machine_code": "FND-DISA-01",
        "part_number": "P-BRK-DISC-01",
        "target_qty": "500",
        "produced_qty": "490",
        "accepted_qty": "480",
        "gross_weight_kg": "3500.0",
        "operator_id": "EMP-99",
        "raw_timestamp": "2026-11-02 14:00:00",
    }])

    sample_rej = pd.DataFrame([{
        "rejection_id": "REJ-TEST-001",
        "production_date": "2026-11-02",
        "shop_code": "FOUNDRY",
        "shift_code": "SHIFT_A",
        "machine_code": "FND-DISA-01",
        "part_number": "P-BRK-DISC-01",
        "defect_code": "DEF-SAND-INC",
        "rejected_qty": "10",
        "reworkable_qty": "2",
        "scrap_qty": "8",
        "unit_cost": "185.00",
        "inspector_id": "QC-99",
        "root_cause_notes": "Sand inclusion test",
        "raw_timestamp": "2026-11-02 14:15:00",
    }])

    batch_id = "TEST-BATCH-001"
    p_cnt, r_cnt = write_to_staging(sample_prod, sample_rej, batch_id, "TEST", test_db)
    assert p_cnt == 1
    assert r_cnt == 1

    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()
    cur.execute("SELECT batch_id, log_id, produced_qty FROM stg_production WHERE batch_id = ?", (batch_id,))
    row = cur.fetchone()
    assert row == (batch_id, "TEST-001", "490")
    conn.close()


def test_run_extraction_end_to_end():
    """Verify run_extraction end-to-end execution for ISO week 2026-W45."""
    res = run_extraction(week="2026-W45", mode="csv")
    assert res["status"] == "SUCCESS"
    assert res["period_key"] == "2026-W45"
    assert res["stg_production_count"] > 0
    assert res["stg_rejection_count"] > 0
    assert res["batch_id"].startswith("BATCH-")

