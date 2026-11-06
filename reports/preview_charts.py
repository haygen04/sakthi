"""Chart Preview Script.

Generates and exports sample preview images (PNG) and interactive widgets (HTML)
for all 5 core manufacturing charts using the loaded warehouse data.
"""

import sys
from pathlib import Path
import pandas as pd
import sqlite3

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
    save_matplotlib_png,
)
from etl.load import WarehouseLoader
from etl.transform import DataTransformer

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output" / "charts_preview"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_chart_previews(week: str = "2026-W45"):
    """Pulls warehouse data for specified week and renders preview charts."""
    print(f"\n[INFO] Generating Chart Previews for period: {week}")
    db_path = ROOT_DIR / "mis_reporting.db"
    conn = sqlite3.connect(str(db_path))

    # Query daily production summary
    query_daily = """
    SELECT 
        d.day_name,
        p.date_key,
        SUM(p.target_qty) AS target_qty,
        SUM(p.produced_qty) AS produced_qty,
        SUM(p.accepted_qty) AS accepted_qty,
        SUM(p.rejected_qty) AS rejected_qty,
        ROUND((SUM(p.rejected_qty) * 100.0 / NULLIF(SUM(p.produced_qty), 0)), 2) AS rejection_pct
    FROM fact_production p
    JOIN dim_date d ON p.date_key = d.date_key
    WHERE p.year_week = ?
    GROUP BY d.day_name, p.date_key
    ORDER BY p.date_key ASC;
    """
    df_daily = pd.read_sql_query(query_daily, conn, params=(week,))

    # Query defect Pareto
    query_pareto = """
    SELECT 
        def.defect_code,
        SUM(r.rejected_qty) AS rejected_qty,
        SUM(r.scrap_qty) AS scrap_qty,
        SUM(r.reworkable_qty) AS reworkable_qty
    FROM fact_rejection r
    JOIN dim_defect def ON r.defect_id = def.defect_id
    WHERE r.year_week = ?
    GROUP BY def.defect_code
    ORDER BY rejected_qty DESC;
    """
    df_pareto = pd.read_sql_query(query_pareto, conn, params=(week,))
    if not df_pareto.empty:
        total = df_pareto["rejected_qty"].sum()
        df_pareto["defect_pct"] = (df_pareto["rejected_qty"] / total) * 100
        df_pareto["cumulative_pct"] = df_pareto["defect_pct"].cumsum().round(2)

    # Query shop comparison
    query_shop = """
    SELECT 
        s.shop_code,
        SUM(p.produced_qty) AS produced_qty,
        SUM(p.rejected_qty) AS rejected_qty,
        ROUND((SUM(p.rejected_qty) * 100.0 / NULLIF(SUM(p.produced_qty), 0)), 2) AS rejection_pct
    FROM fact_production p
    JOIN dim_shop s ON p.shop_id = s.shop_id
    WHERE p.year_week = ?
    GROUP BY s.shop_code;
    """
    df_shop = pd.read_sql_query(query_shop, conn, params=(week,))
    conn.close()

    if df_daily.empty or df_pareto.empty:
        print("[WARNING] No warehouse records found for preview. Please run etl.load first.")
        return

    # 1. Production vs Target
    fig1 = chart_production_vs_target_mpl(df_daily)
    p1 = save_matplotlib_png(fig1, OUTPUT_DIR / "production_vs_target.png")
    fig1_plotly = chart_production_vs_target_plotly(df_daily)
    fig1_plotly.write_html(str(OUTPUT_DIR / "production_vs_target.html"))

    # 2. Rejection % Trend
    fig2 = chart_rejection_trend_mpl(df_daily, threshold_pct=3.5)
    p2 = save_matplotlib_png(fig2, OUTPUT_DIR / "rejection_trend.png")
    fig2_plotly = chart_rejection_trend_plotly(df_daily, threshold_pct=3.5)
    fig2_plotly.write_html(str(OUTPUT_DIR / "rejection_trend.html"))

    # 3. Defect Pareto
    fig3 = chart_defect_pareto_mpl(df_pareto)
    p3 = save_matplotlib_png(fig3, OUTPUT_DIR / "defect_pareto.png")
    fig3_plotly = chart_defect_pareto_plotly(df_pareto)
    fig3_plotly.write_html(str(OUTPUT_DIR / "defect_pareto.html"))

    # 4. Rejection Donut (Scrap vs Rework)
    df_donut = pd.DataFrame([
        {"category": "Scrap (Permanent Loss)", "quantity": df_pareto["scrap_qty"].sum()},
        {"category": "Reworkable (Salvageable)", "quantity": df_pareto["reworkable_qty"].sum()},
    ])
    fig4 = chart_rejection_split_donut_mpl(df_donut)
    p4 = save_matplotlib_png(fig4, OUTPUT_DIR / "rejection_donut.png")
    fig4_plotly = chart_rejection_split_donut_plotly(df_donut)
    fig4_plotly.write_html(str(OUTPUT_DIR / "rejection_donut.html"))

    # 5. Shop Comparison Bar
    fig5 = chart_shop_comparison_bar_mpl(df_shop)
    p5 = save_matplotlib_png(fig5, OUTPUT_DIR / "shop_comparison.png")

    print("\n" + "=" * 65)
    print(" Chart Previews Generated Successfully!")
    print(f" Output Directory: {OUTPUT_DIR}")
    print(f" [PNG] {p1.name}")
    print(f" [PNG] {p2.name}")
    print(f" [PNG] {p3.name}")
    print(f" [PNG] {p4.name}")
    print(f" [PNG] {p5.name}")
    print(f" [HTML] Interactive Plotly widgets also saved (*.html)")
    print("=" * 65)


if __name__ == "__main__":
    generate_chart_previews()

