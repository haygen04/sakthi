"""Unit tests for Phase 0: Discovery, Setup, Data Dictionary, and Schema."""

import sqlite3
import pandas as pd
from pathlib import Path
from config.loader import load_config
from etl.db_init import init_sqlite_db, verify_database_tables

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_directory_structure():
    """Verify all planned directory modules exist."""
    required_dirs = [
        "etl",
        "reports",
        "reports/templates",
        "scheduler",
        "notify",
        "analytics",
        "backend",
        "frontend",
        "sql",
        "tests",
        "config",
        "logs",
        "docs",
        "sample_data",
        "sample_data/pms_exports",
        "sample_data/references",
        "output",
    ]
    for rel_path in required_dirs:
        dir_path = ROOT_DIR / rel_path
        assert dir_path.is_dir(), f"Expected directory {rel_path} does not exist."


def test_config_loader():
    """Verify configuration loads with correct defaults and environment expansion."""
    config = load_config()
    assert "app" in config
    assert "database" in config
    assert "pms" in config
    assert "reports" in config
    assert "ui_tokens" in config
    assert config["ui_tokens"]["accent"] == "#8E9BFF"
    assert config["ui_tokens"]["good"] == "#A8DCC4"


def test_sql_schema_and_sqlite_init(tmp_path):
    """Verify schema initialization and dimension seeding."""
    test_db = tmp_path / "test_reporting.db"
    schema_file = ROOT_DIR / "sql" / "schema.sql"
    seed_file = ROOT_DIR / "sql" / "seed_pms_data.sql"

    init_sqlite_db(test_db, schema_file, seed_file)
    assert verify_database_tables(test_db) is True

    # Check seeded dimensions
    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM dim_shop;")
    assert cur.fetchone()[0] == 2

    cur.execute("SELECT COUNT(*) FROM dim_shift;")
    assert cur.fetchone()[0] == 3

    cur.execute("SELECT COUNT(*) FROM dim_part;")
    assert cur.fetchone()[0] >= 10

    cur.execute("SELECT COUNT(*) FROM dim_defect;")
    assert cur.fetchone()[0] >= 10

    conn.close()


def test_sample_csv_pms_exports():
    """Verify sample CSV exports conform to the Data Dictionary specification."""
    prod_csv = ROOT_DIR / "sample_data" / "pms_exports" / "pms_production_sample.csv"
    rej_csv = ROOT_DIR / "sample_data" / "pms_exports" / "pms_rejection_sample.csv"

    assert prod_csv.exists()
    assert rej_csv.exists()

    df_prod = pd.read_csv(prod_csv)
    df_rej = pd.read_csv(rej_csv)

    expected_prod_cols = {
        "log_id", "production_date", "shop_code", "shift_code",
        "machine_code", "part_number", "target_qty", "produced_qty",
        "accepted_qty", "gross_weight_kg", "operator_id", "raw_timestamp"
    }
    assert expected_prod_cols.issubset(set(df_prod.columns))
    assert len(df_prod) > 0
    # Business logic rule: produced >= accepted
    assert (df_prod["produced_qty"] >= df_prod["accepted_qty"]).all()

    expected_rej_cols = {
        "rejection_id", "production_date", "shop_code", "shift_code",
        "machine_code", "part_number", "defect_code", "rejected_qty",
        "reworkable_qty", "scrap_qty", "unit_cost", "inspector_id",
        "root_cause_notes", "raw_timestamp"
    }
    assert expected_rej_cols.issubset(set(df_rej.columns))
    assert len(df_rej) > 0
    # Business logic rule: rejected_qty == reworkable_qty + scrap_qty
    assert (df_rej["rejected_qty"] == df_rej["reworkable_qty"] + df_rej["scrap_qty"]).all()


def test_reference_report_documents():
    """Verify manual report reference documents exist for all 3 standard outputs."""
    foundry_ref = ROOT_DIR / "sample_data" / "references" / "weekly_foundry_reference.md"
    mshop_ref = ROOT_DIR / "sample_data" / "references" / "weekly_machine_shop_reference.md"
    monthly_ref = ROOT_DIR / "sample_data" / "references" / "monthly_rejection_reference.md"

    assert foundry_ref.exists() and len(foundry_ref.read_text(encoding="utf-8")) > 200
    assert mshop_ref.exists() and len(mshop_ref.read_text(encoding="utf-8")) > 200
    assert monthly_ref.exists() and len(monthly_ref.read_text(encoding="utf-8")) > 200

