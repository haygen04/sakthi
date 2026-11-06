"""Unit and integration tests for Phase 2: Transformation and Validation."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from etl.validate import DataValidator, ValidationSummary
from etl.transform import DataTransformer

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_raw_dfs():
    """Loads sample CSV exports for testing transformation."""
    p_csv = ROOT_DIR / "sample_data" / "pms_exports" / "pms_production_sample.csv"
    r_csv = ROOT_DIR / "sample_data" / "pms_exports" / "pms_rejection_sample.csv"
    return pd.read_csv(p_csv), pd.read_csv(r_csv)


def test_validator_production_rules():
    """Verify validation detects null fields, negative numbers, and accepted > produced."""
    validator = DataValidator()

    dirty_prod = pd.DataFrame([
        # Valid row
        {
            "log_id": "V-001", "production_date": "2026-11-02", "shop_code": "FOUNDRY",
            "shift_code": "SHIFT_A", "machine_code": "M1", "part_number": "P1",
            "target_qty": "100", "produced_qty": "100", "accepted_qty": "95", "gross_weight_kg": "500"
        },
        # Invalid row: negative produced qty
        {
            "log_id": "INV-002", "production_date": "2026-11-02", "shop_code": "FOUNDRY",
            "shift_code": "SHIFT_A", "machine_code": "M1", "part_number": "P1",
            "target_qty": "100", "produced_qty": "-10", "accepted_qty": "0", "gross_weight_kg": "500"
        },
        # Invalid row: accepted > produced
        {
            "log_id": "INV-003", "production_date": "2026-11-02", "shop_code": "FOUNDRY",
            "shift_code": "SHIFT_A", "machine_code": "M1", "part_number": "P1",
            "target_qty": "100", "produced_qty": "50", "accepted_qty": "60", "gross_weight_kg": "500"
        },
        # Duplicate of V-001 (should be deduplicated)
        {
            "log_id": "V-001", "production_date": "2026-11-02", "shop_code": "FOUNDRY",
            "shift_code": "SHIFT_A", "machine_code": "M1", "part_number": "P1",
            "target_qty": "100", "produced_qty": "100", "accepted_qty": "95", "gross_weight_kg": "500"
        },
    ])

    clean_df, summary = validator.validate_production(dirty_prod)
    assert summary.total_checked == 4
    assert summary.valid_count == 1
    assert summary.rejected_count == 2
    assert summary.warnings_count >= 1  # Deduplicated notice
    assert len(clean_df) == 1
    assert clean_df.iloc[0]["log_id"] == "V-001"


def test_validator_rejection_rules():
    """Verify rejection validation checks non-negative values and scrap consistency."""
    validator = DataValidator()

    dirty_rej = pd.DataFrame([
        # Valid row
        {
            "rejection_id": "R-001", "production_date": "2026-11-02", "shop_code": "FOUNDRY",
            "shift_code": "SHIFT_A", "machine_code": "M1", "part_number": "P1",
            "defect_code": "D1", "rejected_qty": "10", "reworkable_qty": "3", "scrap_qty": "7", "unit_cost": "100"
        },
        # Invalid: rework exceeds rejected
        {
            "rejection_id": "R-002", "production_date": "2026-11-02", "shop_code": "FOUNDRY",
            "shift_code": "SHIFT_A", "machine_code": "M1", "part_number": "P1",
            "defect_code": "D1", "rejected_qty": "10", "reworkable_qty": "15", "scrap_qty": "0", "unit_cost": "100"
        },
        # Mismatch that gets auto-balanced: scrap + rework != rejected
        {
            "rejection_id": "R-003", "production_date": "2026-11-02", "shop_code": "FOUNDRY",
            "shift_code": "SHIFT_A", "machine_code": "M1", "part_number": "P1",
            "defect_code": "D1", "rejected_qty": "10", "reworkable_qty": "2", "scrap_qty": "0", "unit_cost": "100"
        },
    ])

    clean_df, summary = validator.validate_rejection(dirty_rej)
    assert summary.valid_count == 2  # R-001 valid, R-003 auto-balanced
    assert summary.rejected_count == 1  # R-002 rejected
    # Check that R-003 scrap_qty was adjusted to 8 (10 - 2)
    r3 = clean_df[clean_df["rejection_id"] == "R-003"].iloc[0]
    assert r3["scrap_qty"] == 8


def test_transformer_cleaning_and_dates():
    """Verify text trimming, uppercase conversion, and calendar key generation."""
    transformer = DataTransformer()
    df = pd.DataFrame([{
        "production_date": "2026-11-02",
        "shop_code": "  foundry  ",
        "shift_code": "shift_a",
        "part_number": "p-brk-01 ",
    }])
    cleaned = transformer.clean_text_and_dates(df)
    assert cleaned.at[0, "shop_code"] == "FOUNDRY"
    assert cleaned.at[0, "shift_code"] == "SHIFT_A"
    assert cleaned.at[0, "part_number"] == "P-BRK-01"
    assert cleaned.at[0, "year_week"] == "2026-W45"
    assert cleaned.at[0, "year_month"] == "2026-11"
    assert cleaned.at[0, "day_name"] == "Monday"


def test_transformer_pareto_calculation(sample_raw_dfs):
    """Verify Pareto rankings, cumulative percentages, and 80/20 vital few classification."""
    raw_prod, raw_rej = sample_raw_dfs
    transformer = DataTransformer()
    results = transformer.transform(raw_prod, raw_rej)

    pareto = results["defect_pareto"]
    assert not pareto.empty
    assert "defect_pct" in pareto.columns
    assert "cumulative_pct" in pareto.columns
    assert "is_vital_few" in pareto.columns

    for shop in pareto["shop_code"].unique():
        shop_p = pareto[pareto["shop_code"] == shop]
        # Must be sorted descending by rejected_qty
        assert shop_p["rejected_qty"].is_monotonic_decreasing
        # Cumulative percentage must reach 100%
        assert np.isclose(shop_p["cumulative_pct"].iloc[-1], 100.0, atol=0.2)


def test_transformer_shop_kpis_and_status(sample_raw_dfs):
    """Verify shop-level metrics (Foundry, Machine Shop, Total Plant) and status coloring."""
    raw_prod, raw_rej = sample_raw_dfs
    transformer = DataTransformer()
    results = transformer.transform(raw_prod, raw_rej)

    shop_kpis = results["shop_kpis"]
    assert "FOUNDRY" in shop_kpis
    assert "MACHINE_SHOP" in shop_kpis
    assert "TOTAL_PLANT" in shop_kpis

    fnd = shop_kpis["FOUNDRY"]
    assert fnd["produced_qty"] > 0
    assert fnd["rejection_pct"] > 0
    assert fnd["first_pass_yield_pct"] == round(100.0 - fnd["rejection_pct"], 2)
    assert fnd["status"] in ["good", "warn", "bad"]

    tot = shop_kpis["TOTAL_PLANT"]
    assert tot["produced_qty"] == fnd["produced_qty"] + shop_kpis["MACHINE_SHOP"]["produced_qty"]


def test_transformer_anomalies_and_observations(sample_raw_dfs):
    """Verify anomaly detection flags and executive commentary lines."""
    raw_prod, raw_rej = sample_raw_dfs
    transformer = DataTransformer()
    results = transformer.transform(raw_prod, raw_rej)

    obs = results["observations"]
    assert len(obs) >= 3
    # First observation mentions plant-wide production
    assert "Plant-wide production reached" in obs[0]

    # Verify fact tables returned
    fact_prod = results["fact_production"]
    fact_rej = results["fact_rejection"]
    assert not fact_prod.empty
    assert not fact_rej.empty
    assert "rejection_pct" in fact_prod.columns
    assert "scrap_cost" in fact_rej.columns

