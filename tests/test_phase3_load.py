"""Unit and integration tests for Phase 3: Reporting Database & Load."""

import sqlite3
import pytest
from pathlib import Path
import pandas as pd

from etl.db_init import init_sqlite_db
from etl.load import WarehouseLoader, load_pipeline

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def clean_test_db(tmp_path):
    """Creates a temporary initialized database for testing load operations."""
    db_file = tmp_path / "test_warehouse.db"
    schema_file = ROOT_DIR / "sql" / "schema.sql"
    seed_file = ROOT_DIR / "sql" / "seed_pms_data.sql"
    init_sqlite_db(db_file, schema_file, seed_file)
    return db_file


def test_dimension_lookups(clean_test_db):
    """Verify natural code to surrogate key lookup dictionaries."""
    loader = WarehouseLoader(clean_test_db)
    conn = loader.get_connection()
    lookups = loader.get_dimension_lookups(conn)
    conn.close()

    assert "shop" in lookups and "FOUNDRY" in lookups["shop"]
    assert "shift" in lookups and "SHIFT_A" in lookups["shift"]
    assert "part" in lookups and "P-BRK-DISC-01" in lookups["part"]
    assert "machine" in lookups and "FND-DISA-01" in lookups["machine"]
    assert "defect" in lookups and "DEF-SAND-INC" in lookups["defect"]

    assert isinstance(lookups["shop"]["FOUNDRY"], int)


def test_ensure_date_dimension(clean_test_db):
    """Verify dynamic population of dim_date calendar attributes."""
    loader = WarehouseLoader(clean_test_db)
    conn = loader.get_connection()

    test_dates = ["2026-11-02", "2026-11-03"]
    loader.ensure_date_dimension(conn, test_dates)

    cur = conn.cursor()
    cur.execute("SELECT date_key, day_name, year_week, year_month, is_weekend FROM dim_date WHERE date_key = '2026-11-02'")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "2026-11-02"
    assert row[1] == "Monday"
    assert row[2] == "2026-W45"
    assert row[3] == "2026-11"
    assert row[4] == 0  # Not a weekend


def test_idempotent_fact_upsert(clean_test_db):
    """Verify that inserting the same fact records multiple times updates without duplicating."""
    loader = WarehouseLoader(clean_test_db)
    conn = loader.get_connection()

    fact_df = pd.DataFrame([{
        "date_key": "2026-11-02",
        "year_week": "2026-W45",
        "year_month": "2026-11",
        "shop_code": "FOUNDRY",
        "shift_code": "SHIFT_A",
        "machine_code": "FND-DISA-01",
        "part_number": "P-BRK-DISC-01",
        "target_qty": 500,
        "produced_qty": 480,
        "accepted_qty": 460,
        "rejected_qty": 20,
        "rejection_pct": 4.167,
        "first_pass_yield_pct": 95.833,
        "gross_weight_kg": 3576.0,
    }])

    # First load
    cnt1 = loader.load_fact_production(conn, fact_df)
    assert cnt1 == 1

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), produced_qty FROM fact_production;")
    row1 = cur.fetchone()
    assert row1 == (1, 480)

    # Second load with updated produced_qty
    fact_df["produced_qty"] = 490
    cnt2 = loader.load_fact_production(conn, fact_df)
    assert cnt2 == 1

    cur.execute("SELECT COUNT(*), produced_qty FROM fact_production;")
    row2 = cur.fetchone()
    # Count must remain 1 (no duplicates), but produced_qty updated to 490
    assert row2 == (1, 490)
    conn.close()


def test_report_runs_audit_logging(clean_test_db):
    """Verify audit log creation and status updates in report_runs."""
    loader = WarehouseLoader(clean_test_db)

    run_id = loader.log_report_run(
        report_type="WEEKLY_FOUNDRY",
        period_key="2026-W45",
        status="IN_PROGRESS",
        generated_by="TEST_RUNNER",
    )
    assert isinstance(run_id, int) and run_id > 0

    loader.update_report_run(
        run_id=run_id,
        status="SUCCESS",
        excel_path="output/foundry/weekly_foundry_2026-W45.xlsx",
        pdf_path="output/foundry/weekly_foundry_2026-W45.pdf",
        run_duration_ms=850,
    )

    conn = loader.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status, excel_path, pdf_path, run_duration_ms FROM report_runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()

    assert row == ("SUCCESS", "output/foundry/weekly_foundry_2026-W45.xlsx", "output/foundry/weekly_foundry_2026-W45.pdf", 850)


def test_load_pipeline_end_to_end():
    """Verify load_pipeline loads ISO week 2026-W45 successfully."""
    res = load_pipeline(week="2026-W45")
    assert res["status"] == "SUCCESS"
    assert res["fact_production_loaded"] > 0
    assert res["fact_rejection_loaded"] > 0
    assert "shop_kpis" in res

