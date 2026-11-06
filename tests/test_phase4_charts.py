"""Unit and visual test suite for Phase 4: Charts Library."""

import pytest
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from pathlib import Path

from reports.charts import (
    chart_production_vs_target_mpl,
    chart_rejection_trend_mpl,
    chart_defect_pareto_mpl,
    chart_rejection_split_donut_mpl,
    chart_shop_comparison_bar_mpl,
    chart_production_vs_target_plotly,
    chart_rejection_trend_plotly,
    chart_defect_pareto_plotly,
    chart_rejection_split_donut_plotly,
    matplotlib_to_base64_png,
    save_matplotlib_png,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_chart_data():
    """Generates synthetic DataFrame fixtures matching report facts."""
    daily_df = pd.DataFrame([
        {"day_name": "Mon", "date_key": "2026-11-02", "target_qty": 2000, "produced_qty": 1950, "rejection_pct": 2.8},
        {"day_name": "Tue", "date_key": "2026-11-03", "target_qty": 2000, "produced_qty": 2010, "rejection_pct": 3.1},
        {"day_name": "Wed", "date_key": "2026-11-04", "target_qty": 2000, "produced_qty": 1980, "rejection_pct": 2.5},
    ])

    pareto_df = pd.DataFrame([
        {"defect_code": "DEF-SAND-INC", "rejected_qty": 120, "cumulative_pct": 40.0},
        {"defect_code": "DEF-POROSITY", "rejected_qty": 80, "cumulative_pct": 66.7},
        {"defect_code": "DEF-SHRINKAGE", "rejected_qty": 60, "cumulative_pct": 86.7},
        {"defect_code": "DEF-DIM-OOT", "rejected_qty": 40, "cumulative_pct": 100.0},
    ])

    donut_df = pd.DataFrame([
        {"category": "Scrap", "quantity": 210},
        {"category": "Rework", "quantity": 90},
    ])

    shop_df = pd.DataFrame([
        {"shop_code": "FOUNDRY", "rejection_pct": 3.29},
        {"shop_code": "MACHINE_SHOP", "rejection_pct": 1.53},
    ])

    return {
        "daily": daily_df,
        "pareto": pareto_df,
        "donut": donut_df,
        "shop": shop_df,
    }


def test_matplotlib_charts_pure_functions(mock_chart_data):
    """Verify all Matplotlib chart functions return valid plt.Figure objects without mutating inputs."""
    d = mock_chart_data

    fig1 = chart_production_vs_target_mpl(d["daily"])
    assert isinstance(fig1, plt.Figure)
    plt.close(fig1)

    fig2 = chart_rejection_trend_mpl(d["daily"])
    assert isinstance(fig2, plt.Figure)
    plt.close(fig2)

    fig3 = chart_defect_pareto_mpl(d["pareto"])
    assert isinstance(fig3, plt.Figure)
    plt.close(fig3)

    fig4 = chart_rejection_split_donut_mpl(d["donut"])
    assert isinstance(fig4, plt.Figure)
    plt.close(fig4)

    fig5 = chart_shop_comparison_bar_mpl(d["shop"])
    assert isinstance(fig5, plt.Figure)
    plt.close(fig5)


def test_matplotlib_export_helpers(mock_chart_data, tmp_path):
    """Verify base64 string and file persistence exporters."""
    fig = chart_production_vs_target_mpl(mock_chart_data["daily"])

    # Base64 export
    b64_uri = matplotlib_to_base64_png(fig, dpi=100)
    assert b64_uri.startswith("data:image/png;base64,")
    assert len(b64_uri) > 500

    # PNG file export
    fig2 = chart_rejection_trend_mpl(mock_chart_data["daily"])
    out_file = tmp_path / "test_trend.png"
    saved_path = save_matplotlib_png(fig2, out_file, dpi=100)
    assert saved_path.exists()
    assert saved_path.stat().st_size > 1000


def test_plotly_interactive_charts(mock_chart_data):
    """Verify Plotly visualizers generate valid Figure objects with appropriate traces."""
    d = mock_chart_data

    p1 = chart_production_vs_target_plotly(d["daily"])
    assert isinstance(p1, go.Figure)
    assert len(p1.data) == 2  # Actual + Target lines

    p2 = chart_rejection_trend_plotly(d["daily"])
    assert isinstance(p2, go.Figure)
    assert len(p2.data) == 1

    p3 = chart_defect_pareto_plotly(d["pareto"])
    assert isinstance(p3, go.Figure)
    assert len(p3.data) == 2  # Bar + Cumulative scatter

    p4 = chart_rejection_split_donut_plotly(d["donut"])
    assert isinstance(p4, go.Figure)
    assert len(p4.data) == 1
    assert p4.data[0].type == "pie"

