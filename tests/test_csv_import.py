"""
Tests for Custom CSV Ingestion & On-the-fly Report Generation.
"""
from pathlib import Path
import pandas as pd
import pytest

from etl.import_csv import detect_periods_from_csv, process_custom_csvs


def test_detect_periods_from_csv():
    df = pd.DataFrame({
        "production_date": ["2026-11-02", "2026-11-05", "2026-11-08"],
        "produced_qty": [100, 200, 300],
    })
    start, end, week, month = detect_periods_from_csv(df)
    assert start == "2026-11-02"
    assert end == "2026-11-08"
    assert week == "2026-W45"
    assert month == "2026-11"


def test_process_custom_csvs_end_to_end():
    prod_path = Path("sample_data/pms_exports/pms_production_sample.csv")
    rej_path = Path("sample_data/pms_exports/pms_rejection_sample.csv")

    res = process_custom_csvs(
        prod_csv_path=prod_path,
        rej_csv_path=rej_path,
        target_week="2026-W45",
        target_month="2026-11",
    )

    assert res["status"] == "SUCCESS"
    assert res["production_rows_loaded"] > 0
    assert res["rejection_rows_loaded"] > 0
    assert "reports" in res
    assert Path(res["reports"]["weekly_foundry"]["excel"]).exists()
    assert Path(res["reports"]["weekly_foundry"]["pdf"]).exists()
    assert Path(res["reports"]["weekly_machine_shop"]["excel"]).exists()
    assert Path(res["reports"]["monthly_rejection"]["pdf"]).exists()

