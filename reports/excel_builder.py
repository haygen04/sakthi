"""Excel Report Generator Module for Manufacturing MIS & Rejection Reports.

Builds standardized, formatted workbooks for:
1. Weekly Foundry MIS Report
2. Weekly Machine Shop MIS Report
3. Monthly Plant-Wide Rejection & Cost Report

Styling strictly adheres to Section 5: soft palette, light fills (#EEF0F6, #E6E9FF),
no harsh black borders, freeze panes, auto-fit column widths, native number formatting,
and embedded high-resolution visual charts.
"""

import sys
import sqlite3
import argparse
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import xlsxwriter

from config.loader import load_config
from etl.extract import resolve_date_range
from etl.load import WarehouseLoader
from reports.charts import (
    chart_production_vs_target_mpl,
    chart_rejection_trend_mpl,
    chart_defect_pareto_mpl,
    chart_rejection_split_donut_mpl,
    chart_shop_comparison_bar_mpl,
    save_matplotlib_png,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_BASE = ROOT_DIR / "output"
LOGS_DIR = ROOT_DIR / "logs"
LOG_FILE = LOGS_DIR / "etl.log"

logger = logging.getLogger("reports.excel")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setFormatter(formatter)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(sh)


class ExcelReportBuilder:
    """Constructs standardized MIS Excel workbooks with XlsxWriter."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (ROOT_DIR / "mis_reporting.db")
        self.config = load_config()

    def get_connection(self):
        return sqlite3.connect(str(self.db_path))

    # -----------------------------------------------------------------------
    # Styling Setup
    # -----------------------------------------------------------------------
    def _create_formats(self, workbook: xlsxwriter.Workbook) -> Dict[str, Any]:
        """Creates unified font, border, and color formats matching Section 5 design."""
        return {
            "title": workbook.add_format({
                "bold": True, "font_size": 16, "font_color": "#3F4558",
                "font_name": "Segoe UI", "align": "left", "valign": "vcenter",
            }),
            "subtitle": workbook.add_format({
                "font_size": 10, "font_color": "#8A90A6", "font_name": "Segoe UI",
            }),
            "kpi_label": workbook.add_format({
                "font_size": 9, "font_color": "#8A90A6", "font_name": "Segoe UI",
                "bg_color": "#FBFBFD", "bold": True,
            }),
            "kpi_val_num": workbook.add_format({
                "font_size": 15, "bold": True, "font_color": "#3F4558", "font_name": "Segoe UI",
                "bg_color": "#FBFBFD", "num_format": "#,##0",
            }),
            "kpi_val_pct": workbook.add_format({
                "font_size": 15, "bold": True, "font_color": "#3F4558", "font_name": "Segoe UI",
                "bg_color": "#FBFBFD", "num_format": "0.00%",
            }),
            "kpi_val_cur": workbook.add_format({
                "font_size": 15, "bold": True, "font_color": "#3F4558", "font_name": "Segoe UI",
                "bg_color": "#FBFBFD", "num_format": "₹#,##0",
            }),
            "th": workbook.add_format({
                "bold": True, "font_size": 10, "font_name": "Segoe UI",
                "font_color": "#3F4558", "bg_color": "#EEF0F6",
                "align": "center", "valign": "vcenter", "border": 1, "border_color": "#E2E6EF",
            }),
            "th_left": workbook.add_format({
                "bold": True, "font_size": 10, "font_name": "Segoe UI",
                "font_color": "#3F4558", "bg_color": "#EEF0F6",
                "align": "left", "valign": "vcenter", "border": 1, "border_color": "#E2E6EF",
            }),
            "cell_text": workbook.add_format({
                "font_size": 9.5, "font_name": "Segoe UI", "font_color": "#3F4558",
                "border": 1, "border_color": "#EEF0F6",
            }),
            "cell_center": workbook.add_format({
                "font_size": 9.5, "font_name": "Segoe UI", "font_color": "#3F4558",
                "align": "center", "border": 1, "border_color": "#EEF0F6",
            }),
            "cell_num": workbook.add_format({
                "font_size": 9.5, "font_name": "Segoe UI", "font_color": "#3F4558",
                "num_format": "#,##0", "border": 1, "border_color": "#EEF0F6",
            }),
            "cell_pct": workbook.add_format({
                "font_size": 9.5, "font_name": "Segoe UI", "font_color": "#3F4558",
                "num_format": "0.00%", "border": 1, "border_color": "#EEF0F6",
            }),
            "cell_cur": workbook.add_format({
                "font_size": 9.5, "font_name": "Segoe UI", "font_color": "#3F4558",
                "num_format": "₹#,##0", "border": 1, "border_color": "#EEF0F6",
            }),
            "cell_dec": workbook.add_format({
                "font_size": 9.5, "font_name": "Segoe UI", "font_color": "#3F4558",
                "num_format": "0.00", "border": 1, "border_color": "#EEF0F6",
            }),
            "total_row_label": workbook.add_format({
                "bold": True, "font_size": 10, "font_name": "Segoe UI", "font_color": "#3F4558",
                "bg_color": "#F4F5F9", "border": 1, "border_color": "#D5D8E2",
            }),
            "total_row_num": workbook.add_format({
                "bold": True, "font_size": 10, "font_name": "Segoe UI", "font_color": "#3F4558",
                "bg_color": "#F4F5F9", "num_format": "#,##0", "border": 1, "border_color": "#D5D8E2",
            }),
            "total_row_pct": workbook.add_format({
                "bold": True, "font_size": 10, "font_name": "Segoe UI", "font_color": "#3F4558",
                "bg_color": "#F4F5F9", "num_format": "0.00%", "border": 1, "border_color": "#D5D8E2",
            }),
            "total_row_cur": workbook.add_format({
                "bold": True, "font_size": 10, "font_name": "Segoe UI", "font_color": "#3F4558",
                "bg_color": "#F4F5F9", "num_format": "₹#,##0", "border": 1, "border_color": "#D5D8E2",
            }),
            "status_good": workbook.add_format({
                "bold": True, "font_size": 9, "font_name": "Segoe UI", "font_color": "#4E8F73",
                "bg_color": "#A8DCC4", "align": "center", "border": 1, "border_color": "#EEF0F6",
            }),
            "status_warn": workbook.add_format({
                "bold": True, "font_size": 9, "font_name": "Segoe UI", "font_color": "#A98433",
                "bg_color": "#F6DDA8", "align": "center", "border": 1, "border_color": "#EEF0F6",
            }),
            "status_bad": workbook.add_format({
                "bold": True, "font_size": 9, "font_name": "Segoe UI", "font_color": "#B25A66",
                "bg_color": "#F4B9C0", "align": "center", "border": 1, "border_color": "#EEF0F6",
            }),
        }

    def _auto_fit_columns(self, ws, max_col: int, padding: int = 4):
        """Sets comfortable column widths without truncation."""
        for c in range(max_col):
            ws.set_column(c, c, 18)

    # -----------------------------------------------------------------------
    # 1. Weekly Foundry MIS Workbook
    # -----------------------------------------------------------------------
    def build_weekly_foundry(self, period_key: str = "2026-W45", output_path: Optional[Path] = None) -> Path:
        """Constructs formatted Weekly Foundry MIS workbook."""
        logger.info(f"Generating Weekly Foundry MIS Excel workbook for {period_key}...")
        if output_path is None:
            output_dir = OUTPUT_BASE / "weekly_foundry" / period_key
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"weekly_foundry_{period_key}.xlsx"

        conn = self.get_connection()

        # Data Queries
        # Daily
        q_daily = """
        SELECT 
            p.date_key, d.day_name,
            SUM(p.target_qty) AS target_qty,
            SUM(p.produced_qty) AS produced_qty,
            SUM(p.accepted_qty) AS accepted_qty,
            SUM(p.rejected_qty) AS rejected_qty,
            ROUND(SUM(p.gross_weight_kg) / 1000.0, 2) AS weight_mt
        FROM fact_production p
        JOIN dim_date d ON p.date_key = d.date_key
        JOIN dim_shop s ON p.shop_id = s.shop_id
        WHERE p.year_week = ? AND s.shop_code = 'FOUNDRY'
        GROUP BY p.date_key, d.day_name
        ORDER BY p.date_key ASC;
        """
        df_daily = pd.read_sql_query(q_daily, conn, params=(period_key,))

        # Shift
        q_shift = """
        SELECT 
            sh.shift_name,
            SUM(p.target_qty) AS target_qty,
            SUM(p.produced_qty) AS produced_qty,
            SUM(p.accepted_qty) AS accepted_qty,
            SUM(p.rejected_qty) AS rejected_qty
        FROM fact_production p
        JOIN dim_shift sh ON p.shift_id = sh.shift_id
        JOIN dim_shop s ON p.shop_id = s.shop_id
        WHERE p.year_week = ? AND s.shop_code = 'FOUNDRY'
        GROUP BY sh.shift_name;
        """
        df_shift = pd.read_sql_query(q_shift, conn, params=(period_key,))

        # Defect Pareto
        q_defect = """
        SELECT 
            def.defect_code, def.defect_name, def.category,
            SUM(r.rejected_qty) AS rejected_qty,
            SUM(r.scrap_qty) AS scrap_qty,
            SUM(r.reworkable_qty) AS reworkable_qty,
            SUM(r.scrap_cost) AS scrap_cost
        FROM fact_rejection r
        JOIN dim_defect def ON r.defect_id = def.defect_id
        JOIN dim_shop s ON r.shop_id = s.shop_id
        WHERE r.year_week = ? AND s.shop_code = 'FOUNDRY'
        GROUP BY def.defect_code, def.defect_name, def.category
        ORDER BY rejected_qty DESC;
        """
        df_defect = pd.read_sql_query(q_defect, conn, params=(period_key,))

        # Parts
        q_part = """
        SELECT 
            pt.part_number, pt.part_name, pt.material_grade,
            SUM(p.produced_qty) AS produced_qty,
            SUM(p.accepted_qty) AS accepted_qty,
            SUM(p.rejected_qty) AS rejected_qty
        FROM fact_production p
        JOIN dim_part pt ON p.part_id = pt.part_id
        JOIN dim_shop s ON p.shop_id = s.shop_id
        WHERE p.year_week = ? AND s.shop_code = 'FOUNDRY'
        GROUP BY pt.part_number, pt.part_name, pt.material_grade
        ORDER BY rejected_qty DESC;
        """
        df_part = pd.read_sql_query(q_part, conn, params=(period_key,))
        conn.close()

        # Workbook Creation
        wb = xlsxwriter.Workbook(str(output_path))
        fmt = self._create_formats(wb)

        # SHEET 1: Executive Summary & Daily
        ws_sum = wb.add_worksheet("Foundry Summary & Daily")
        ws_sum.freeze_panes(8, 0)
        ws_sum.set_column(0, 0, 14)
        ws_sum.set_column(1, 1, 14)
        ws_sum.set_column(2, 8, 16)

        # Header Block
        ws_sum.write(0, 0, "SAKTHI AUTOMOTIVE GROUP - FOUNDRY DIVISION", fmt["title"])
        ws_sum.write(1, 0, f"Weekly MIS Report: {period_key} | Generated: {datetime.now().strftime('%d-%b-%Y %H:%M')}", fmt["subtitle"])

        # KPI Tiles
        tot_prod = int(df_daily["produced_qty"].sum()) if not df_daily.empty else 0
        tot_acc = int(df_daily["accepted_qty"].sum()) if not df_daily.empty else 0
        tot_rej = int(df_daily["rejected_qty"].sum()) if not df_daily.empty else 0
        tot_wt = float(df_daily["weight_mt"].sum()) if not df_daily.empty else 0.0
        tot_cost = float(df_defect["scrap_cost"].sum()) if not df_defect.empty else 0.0
        rej_pct = (tot_rej / tot_prod) if tot_prod > 0 else 0.0

        tiles = [
            ("TOTAL CASTINGS POURED", tot_prod, fmt["kpi_val_num"]),
            ("POURED METAL (MT)", tot_wt, fmt["kpi_val_num"]),
            ("OVERALL REJECTION %", rej_pct, fmt["kpi_val_pct"]),
            ("FIRST-PASS YIELD %", 1.0 - rej_pct, fmt["kpi_val_pct"]),
            ("SCRAP COST IMPACT", tot_cost, fmt["kpi_val_cur"]),
        ]
        for col_idx, (label, val, val_fmt) in enumerate(tiles):
            ws_sum.write(3, col_idx + 1, label, fmt["kpi_label"])
            ws_sum.write(4, col_idx + 1, val, val_fmt)

        # Table Header
        headers = ["Date", "Day", "Target Pcs", "Poured Pcs", "Accepted Pcs", "Rejected Pcs", "Rejection %", "Melt Wt (MT)", "Status"]
        for c_idx, h in enumerate(headers):
            ws_sum.write(7, c_idx, h, fmt["th"])

        row_idx = 8
        for _, r in df_daily.iterrows():
            r_pct = (r["rejected_qty"] / r["produced_qty"]) if r["produced_qty"] > 0 else 0.0
            status_fmt = fmt["status_good"] if r_pct <= 0.035 else (fmt["status_warn"] if r_pct <= 0.045 else fmt["status_bad"])
            status_text = "Good" if r_pct <= 0.035 else ("Watch" if r_pct <= 0.045 else "Critical")

            ws_sum.write(row_idx, 0, str(r["date_key"]), fmt["cell_center"])
            ws_sum.write(row_idx, 1, str(r["day_name"]), fmt["cell_center"])
            ws_sum.write(row_idx, 2, int(r["target_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 3, int(r["produced_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 4, int(r["accepted_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 5, int(r["rejected_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 6, r_pct, fmt["cell_pct"])
            ws_sum.write(row_idx, 7, float(r["weight_mt"]), fmt["cell_dec"])
            ws_sum.write(row_idx, 8, status_text, status_fmt)
            row_idx += 1

        # Total Row
        ws_sum.write(row_idx, 0, "TOTAL / AVERAGE", fmt["total_row_label"])
        ws_sum.write(row_idx, 1, "-", fmt["total_row_label"])
        ws_sum.write(row_idx, 2, f"=SUM(C9:C{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 3, f"=SUM(D9:D{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 4, f"=SUM(E9:E{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 5, f"=SUM(F9:F{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 6, f"=F{row_idx+1}/D{row_idx+1}", fmt["total_row_pct"])
        ws_sum.write(row_idx, 7, f"=SUM(H9:H{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 8, "Weekly Aggregate", fmt["total_row_label"])

        # Embed Charts
        chart_dir = output_path.parent / "temp_charts"
        chart_dir.mkdir(parents=True, exist_ok=True)
        if not df_daily.empty:
            fig1 = chart_production_vs_target_mpl(df_daily, "Foundry Daily Production vs Target")
            c1_path = save_matplotlib_png(fig1, chart_dir / "foundry_prod.png", dpi=150)
            ws_sum.insert_image(row_idx + 3, 1, str(c1_path), {"x_scale": 0.85, "y_scale": 0.85})

            fig2 = chart_rejection_trend_mpl(df_daily.assign(rejection_pct=df_daily["rejected_qty"]/df_daily["produced_qty"]*100), 3.5, "Daily Rejection % Trend")
            c2_path = save_matplotlib_png(fig2, chart_dir / "foundry_rej.png", dpi=150)
            ws_sum.insert_image(row_idx + 21, 1, str(c2_path), {"x_scale": 0.85, "y_scale": 0.85})

        # SHEET 2: Shift Performance
        ws_shift = wb.add_worksheet("Shift Performance")
        ws_shift.freeze_panes(4, 0)
        ws_shift.set_column(0, 4, 18)
        ws_shift.write(0, 0, "FOUNDRY SHIFT PERFORMANCE BREAKDOWN", fmt["title"])
        shift_headers = ["Shift Name", "Target Pcs", "Poured Pcs", "Accepted Pcs", "Rejected Pcs", "Rejection %"]
        for c, h in enumerate(shift_headers):
            ws_shift.write(3, c, h, fmt["th"])

        s_row = 4
        for _, r in df_shift.iterrows():
            r_pct = (r["rejected_qty"] / r["produced_qty"]) if r["produced_qty"] > 0 else 0.0
            ws_shift.write(s_row, 0, str(r["shift_name"]), fmt["cell_center"])
            ws_shift.write(s_row, 1, int(r["target_qty"]), fmt["cell_num"])
            ws_shift.write(s_row, 2, int(r["produced_qty"]), fmt["cell_num"])
            ws_shift.write(s_row, 3, int(r["accepted_qty"]), fmt["cell_num"])
            ws_shift.write(s_row, 4, int(r["rejected_qty"]), fmt["cell_num"])
            ws_shift.write(s_row, 5, r_pct, fmt["cell_pct"])
            s_row += 1

        # SHEET 3: Defect Pareto
        ws_def = wb.add_worksheet("Defect Pareto")
        ws_def.freeze_panes(4, 0)
        ws_def.set_column(0, 0, 16)
        ws_def.set_column(1, 1, 32)
        ws_def.set_column(2, 6, 16)
        ws_def.write(0, 0, "FOUNDRY DEFECT PARETO ANALYSIS", fmt["title"])

        def_headers = ["Defect Code", "Defect Description", "Category", "Rejected Qty", "Scrap Qty", "Rework Qty", "Scrap Cost", "% of Defect", "Cumulative %"]
        for c, h in enumerate(def_headers):
            ws_def.write(3, c, h, fmt["th"])

        tot_def = df_defect["rejected_qty"].sum() if not df_defect.empty else 1
        d_row = 4
        cum = 0.0
        for _, r in df_defect.iterrows():
            pct = (r["rejected_qty"] / tot_def)
            cum += pct
            ws_def.write(d_row, 0, str(r["defect_code"]), fmt["cell_center"])
            ws_def.write(d_row, 1, str(r["defect_name"]), fmt["cell_text"])
            ws_def.write(d_row, 2, str(r["category"]), fmt["cell_center"])
            ws_def.write(d_row, 3, int(r["rejected_qty"]), fmt["cell_num"])
            ws_def.write(d_row, 4, int(r["scrap_qty"]), fmt["cell_num"])
            ws_def.write(d_row, 5, int(r["reworkable_qty"]), fmt["cell_num"])
            ws_def.write(d_row, 6, float(r["scrap_cost"]), fmt["cell_cur"])
            ws_def.write(d_row, 7, pct, fmt["cell_pct"])
            ws_def.write(d_row, 8, min(cum, 1.0), fmt["cell_pct"])
            d_row += 1

        if not df_defect.empty:
            fig3 = chart_defect_pareto_mpl(df_defect.assign(cumulative_pct=df_defect["rejected_qty"].cumsum()/tot_def*100), "Foundry Defect Pareto")
            c3_path = save_matplotlib_png(fig3, chart_dir / "foundry_pareto.png", dpi=150)
            ws_def.insert_image(d_row + 2, 1, str(c3_path), {"x_scale": 0.85, "y_scale": 0.85})

        # SHEET 4: Part Analysis
        ws_part = wb.add_worksheet("Part Analysis")
        ws_part.freeze_panes(4, 0)
        ws_part.set_column(0, 0, 18)
        ws_part.set_column(1, 1, 36)
        ws_part.set_column(2, 6, 16)
        ws_part.write(0, 0, "FOUNDRY HIGH-RUNNER PART QUALITY MATRIX", fmt["title"])
        part_headers = ["Part Number", "Description", "Grade", "Poured Pcs", "Accepted Pcs", "Rejected Pcs", "Rejection %"]
        for c, h in enumerate(part_headers):
            ws_part.write(3, c, h, fmt["th"])

        p_row = 4
        for _, r in df_part.iterrows():
            r_pct = (r["rejected_qty"] / r["produced_qty"]) if r["produced_qty"] > 0 else 0.0
            ws_part.write(p_row, 0, str(r["part_number"]), fmt["cell_center"])
            ws_part.write(p_row, 1, str(r["part_name"]), fmt["cell_text"])
            ws_part.write(p_row, 2, str(r["material_grade"]), fmt["cell_center"])
            ws_part.write(p_row, 3, int(r["produced_qty"]), fmt["cell_num"])
            ws_part.write(p_row, 4, int(r["accepted_qty"]), fmt["cell_num"])
            ws_part.write(p_row, 5, int(r["rejected_qty"]), fmt["cell_num"])
            ws_part.write(p_row, 6, r_pct, fmt["cell_pct"])
            p_row += 1

        wb.close()
        logger.info(f"Weekly Foundry MIS Workbook generated: {output_path}")
        return output_path

    # -----------------------------------------------------------------------
    # 2. Weekly Machine Shop MIS Workbook
    # -----------------------------------------------------------------------
    def build_weekly_machine_shop(self, period_key: str = "2026-W45", output_path: Optional[Path] = None) -> Path:
        """Constructs formatted Weekly Machine Shop MIS workbook."""
        logger.info(f"Generating Weekly Machine Shop MIS Excel workbook for {period_key}...")
        if output_path is None:
            output_dir = OUTPUT_BASE / "weekly_machine_shop" / period_key
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"weekly_machine_shop_{period_key}.xlsx"

        conn = self.get_connection()

        # Daily
        q_daily = """
        SELECT 
            p.date_key, d.day_name,
            SUM(p.target_qty) AS target_qty,
            SUM(p.produced_qty) AS produced_qty,
            SUM(p.accepted_qty) AS accepted_qty,
            SUM(p.rejected_qty) AS rejected_qty
        FROM fact_production p
        JOIN dim_date d ON p.date_key = d.date_key
        JOIN dim_shop s ON p.shop_id = s.shop_id
        WHERE p.year_week = ? AND s.shop_code = 'MACHINE_SHOP'
        GROUP BY p.date_key, d.day_name
        ORDER BY p.date_key ASC;
        """
        df_daily = pd.read_sql_query(q_daily, conn, params=(period_key,))

        # Machine Lines
        q_mach = """
        SELECT 
            m.machine_code, m.machine_name, m.line_name,
            SUM(p.target_qty) AS target_qty,
            SUM(p.produced_qty) AS produced_qty,
            SUM(p.accepted_qty) AS accepted_qty,
            SUM(p.rejected_qty) AS rejected_qty
        FROM fact_production p
        JOIN dim_machine m ON p.machine_id = m.machine_id
        JOIN dim_shop s ON p.shop_id = s.shop_id
        WHERE p.year_week = ? AND s.shop_code = 'MACHINE_SHOP'
        GROUP BY m.machine_code, m.machine_name, m.line_name
        ORDER BY rejected_qty DESC;
        """
        df_mach = pd.read_sql_query(q_mach, conn, params=(period_key,))

        # Defect Pareto
        q_defect = """
        SELECT 
            def.defect_code, def.defect_name, def.category,
            SUM(r.rejected_qty) AS rejected_qty,
            SUM(r.scrap_qty) AS scrap_qty,
            SUM(r.reworkable_qty) AS reworkable_qty,
            SUM(r.scrap_cost) AS scrap_cost
        FROM fact_rejection r
        JOIN dim_defect def ON r.defect_id = def.defect_id
        JOIN dim_shop s ON r.shop_id = s.shop_id
        WHERE r.year_week = ? AND s.shop_code = 'MACHINE_SHOP'
        GROUP BY def.defect_code, def.defect_name, def.category
        ORDER BY rejected_qty DESC;
        """
        df_defect = pd.read_sql_query(q_defect, conn, params=(period_key,))

        # Parts
        q_part = """
        SELECT 
            pt.part_number, pt.part_name,
            SUM(p.produced_qty) AS produced_qty,
            SUM(p.accepted_qty) AS accepted_qty,
            SUM(p.rejected_qty) AS rejected_qty
        FROM fact_production p
        JOIN dim_part pt ON p.part_id = pt.part_id
        JOIN dim_shop s ON p.shop_id = s.shop_id
        WHERE p.year_week = ? AND s.shop_code = 'MACHINE_SHOP'
        GROUP BY pt.part_number, pt.part_name
        ORDER BY rejected_qty DESC;
        """
        df_part = pd.read_sql_query(q_part, conn, params=(period_key,))
        conn.close()

        # Workbook Creation
        wb = xlsxwriter.Workbook(str(output_path))
        fmt = self._create_formats(wb)

        # SHEET 1: Summary & Daily
        ws_sum = wb.add_worksheet("Machining Summary & Daily")
        ws_sum.freeze_panes(8, 0)
        ws_sum.set_column(0, 0, 14)
        ws_sum.set_column(1, 1, 14)
        ws_sum.set_column(2, 7, 16)

        ws_sum.write(0, 0, "SAKTHI AUTOMOTIVE GROUP - PRECISION MACHINING DIVISION", fmt["title"])
        ws_sum.write(1, 0, f"Weekly MIS Report: {period_key} | Generated: {datetime.now().strftime('%d-%b-%Y %H:%M')}", fmt["subtitle"])

        tot_prod = int(df_daily["produced_qty"].sum()) if not df_daily.empty else 0
        tot_acc = int(df_daily["accepted_qty"].sum()) if not df_daily.empty else 0
        tot_rej = int(df_daily["rejected_qty"].sum()) if not df_daily.empty else 0
        tot_cost = float(df_defect["scrap_cost"].sum()) if not df_defect.empty else 0.0
        rej_pct = (tot_rej / tot_prod) if tot_prod > 0 else 0.0

        tiles = [
            ("TOTAL COMPONENTS MACHINED", tot_prod, fmt["kpi_val_num"]),
            ("FINISHED OK OUTPUT", tot_acc, fmt["kpi_val_num"]),
            ("MACHINING REJECTION %", rej_pct, fmt["kpi_val_pct"]),
            ("FIRST-PASS YIELD %", 1.0 - rej_pct, fmt["kpi_val_pct"]),
            ("MACHINING LOSS COST", tot_cost, fmt["kpi_val_cur"]),
        ]
        for col_idx, (label, val, val_fmt) in enumerate(tiles):
            ws_sum.write(3, col_idx + 1, label, fmt["kpi_label"])
            ws_sum.write(4, col_idx + 1, val, val_fmt)

        headers = ["Date", "Day", "Target Pcs", "Machined Pcs", "OK Pcs", "Rejected Pcs", "Rejection %", "Status"]
        for c_idx, h in enumerate(headers):
            ws_sum.write(7, c_idx, h, fmt["th"])

        row_idx = 8
        for _, r in df_daily.iterrows():
            r_pct = (r["rejected_qty"] / r["produced_qty"]) if r["produced_qty"] > 0 else 0.0
            status_fmt = fmt["status_good"] if r_pct <= 0.020 else (fmt["status_warn"] if r_pct <= 0.028 else fmt["status_bad"])
            status_text = "Good" if r_pct <= 0.020 else ("Watch" if r_pct <= 0.028 else "Critical")

            ws_sum.write(row_idx, 0, str(r["date_key"]), fmt["cell_center"])
            ws_sum.write(row_idx, 1, str(r["day_name"]), fmt["cell_center"])
            ws_sum.write(row_idx, 2, int(r["target_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 3, int(r["produced_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 4, int(r["accepted_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 5, int(r["rejected_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 6, r_pct, fmt["cell_pct"])
            ws_sum.write(row_idx, 7, status_text, status_fmt)
            row_idx += 1

        # Total Row
        ws_sum.write(row_idx, 0, "TOTAL / AVERAGE", fmt["total_row_label"])
        ws_sum.write(row_idx, 1, "-", fmt["total_row_label"])
        ws_sum.write(row_idx, 2, f"=SUM(C9:C{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 3, f"=SUM(D9:D{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 4, f"=SUM(E9:E{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 5, f"=SUM(F9:F{row_idx})", fmt["total_row_num"])
        ws_sum.write(row_idx, 6, f"=F{row_idx+1}/D{row_idx+1}", fmt["total_row_pct"])
        ws_sum.write(row_idx, 7, "Weekly Total", fmt["total_row_label"])

        # Charts
        chart_dir = output_path.parent / "temp_charts"
        chart_dir.mkdir(parents=True, exist_ok=True)
        if not df_daily.empty:
            fig1 = chart_production_vs_target_mpl(df_daily, "Machine Shop Output vs Target")
            c1_path = save_matplotlib_png(fig1, chart_dir / "mshop_prod.png", dpi=150)
            ws_sum.insert_image(row_idx + 3, 1, str(c1_path), {"x_scale": 0.85, "y_scale": 0.85})

        # SHEET 2: Machine Cell Performance
        ws_m = wb.add_worksheet("Cell Performance")
        ws_m.freeze_panes(4, 0)
        ws_m.set_column(0, 0, 16)
        ws_m.set_column(1, 1, 32)
        ws_m.set_column(2, 6, 16)
        ws_m.write(0, 0, "MACHINE CELL & LINE EFFICIENCY BREAKDOWN", fmt["title"])
        m_headers = ["Machine Code", "Machine Description", "Line Name", "Target Pcs", "Machined Pcs", "Rejected Pcs", "Rejection %"]
        for c, h in enumerate(m_headers):
            ws_m.write(3, c, h, fmt["th"])

        m_row = 4
        for _, r in df_mach.iterrows():
            r_pct = (r["rejected_qty"] / r["produced_qty"]) if r["produced_qty"] > 0 else 0.0
            ws_m.write(m_row, 0, str(r["machine_code"]), fmt["cell_center"])
            ws_m.write(m_row, 1, str(r["machine_name"]), fmt["cell_text"])
            ws_m.write(m_row, 2, str(r["line_name"]), fmt["cell_center"])
            ws_m.write(m_row, 3, int(r["target_qty"]), fmt["cell_num"])
            ws_m.write(m_row, 4, int(r["produced_qty"]), fmt["cell_num"])
            ws_m.write(m_row, 5, int(r["rejected_qty"]), fmt["cell_num"])
            ws_m.write(m_row, 6, r_pct, fmt["cell_pct"])
            m_row += 1

        # SHEET 3: Defect Pareto
        ws_def = wb.add_worksheet("Machining Defects")
        ws_def.freeze_panes(4, 0)
        ws_def.set_column(0, 0, 16)
        ws_def.set_column(1, 1, 32)
        ws_def.set_column(2, 6, 16)
        ws_def.write(0, 0, "MACHINE SHOP DEFECT BREAKDOWN", fmt["title"])
        for c, h in enumerate(["Defect Code", "Defect Description", "Category", "Rejected Qty", "Scrap Qty", "Rework Qty", "Scrap Cost"]):
            ws_def.write(3, c, h, fmt["th"])

        d_row = 4
        for _, r in df_defect.iterrows():
            ws_def.write(d_row, 0, str(r["defect_code"]), fmt["cell_center"])
            ws_def.write(d_row, 1, str(r["defect_name"]), fmt["cell_text"])
            ws_def.write(d_row, 2, str(r["category"]), fmt["cell_center"])
            ws_def.write(d_row, 3, int(r["rejected_qty"]), fmt["cell_num"])
            ws_def.write(d_row, 4, int(r["scrap_qty"]), fmt["cell_num"])
            ws_def.write(d_row, 5, int(r["reworkable_qty"]), fmt["cell_num"])
            ws_def.write(d_row, 6, float(r["scrap_cost"]), fmt["cell_cur"])
            d_row += 1

        wb.close()
        logger.info(f"Weekly Machine Shop MIS Workbook generated: {output_path}")
        return output_path

    # -----------------------------------------------------------------------
    # 3. Monthly Rejection & Quality Cost Workbook
    # -----------------------------------------------------------------------
    def build_monthly_rejection(self, month_key: str = "2026-11", output_path: Optional[Path] = None) -> Path:
        """Constructs formatted Monthly Rejection & Cost-of-Quality workbook."""
        logger.info(f"Generating Monthly Rejection Report Excel workbook for {month_key}...")
        if output_path is None:
            output_dir = OUTPUT_BASE / "monthly_rejection" / month_key
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"monthly_rejection_{month_key}.xlsx"

        conn = self.get_connection()

        # Shop Comparison
        q_shop = """
        SELECT 
            s.shop_code, s.shop_name,
            SUM(p.produced_qty) AS produced_qty,
            SUM(p.accepted_qty) AS accepted_qty,
            SUM(p.rejected_qty) AS rejected_qty
        FROM fact_production p
        JOIN dim_shop s ON p.shop_id = s.shop_id
        WHERE p.year_month = ?
        GROUP BY s.shop_code, s.shop_name;
        """
        df_shop = pd.read_sql_query(q_shop, conn, params=(month_key,))

        # Overall Plant Defect Pareto
        q_pareto = """
        SELECT 
            s.shop_code, def.defect_code, def.defect_name, def.category,
            SUM(r.rejected_qty) AS rejected_qty,
            SUM(r.scrap_qty) AS scrap_qty,
            SUM(r.reworkable_qty) AS reworkable_qty,
            SUM(r.scrap_cost) AS scrap_cost
        FROM fact_rejection r
        JOIN dim_defect def ON r.defect_id = def.defect_id
        JOIN dim_shop s ON r.shop_id = s.shop_id
        WHERE r.year_month = ?
        GROUP BY s.shop_code, def.defect_code, def.defect_name, def.category
        ORDER BY rejected_qty DESC;
        """
        df_pareto = pd.read_sql_query(q_pareto, conn, params=(month_key,))
        conn.close()

        # Workbook Creation
        wb = xlsxwriter.Workbook(str(output_path))
        fmt = self._create_formats(wb)

        # SHEET 1: Monthly Executive Summary
        ws_sum = wb.add_worksheet("Monthly Executive Summary")
        ws_sum.freeze_panes(8, 0)
        ws_sum.set_column(0, 0, 18)
        ws_sum.set_column(1, 1, 32)
        ws_sum.set_column(2, 6, 16)

        ws_sum.write(0, 0, "SAKTHI AUTOMOTIVE GROUP - QUALITY ASSURANCE COMMAND", fmt["title"])
        ws_sum.write(1, 0, f"Monthly Rejection & Quality Cost Report: {month_key} | Generated: {datetime.now().strftime('%d-%b-%Y %H:%M')}", fmt["subtitle"])

        tot_prod = int(df_shop["produced_qty"].sum()) if not df_shop.empty else 0
        tot_acc = int(df_shop["accepted_qty"].sum()) if not df_shop.empty else 0
        tot_rej = int(df_shop["rejected_qty"].sum()) if not df_shop.empty else 0
        tot_cost = float(df_pareto["scrap_cost"].sum()) if not df_pareto.empty else 0.0
        rej_pct = (tot_rej / tot_prod) if tot_prod > 0 else 0.0

        tiles = [
            ("TOTAL PLANT PRODUCTION", tot_prod, fmt["kpi_val_num"]),
            ("TOTAL REJECTED PCS", tot_rej, fmt["kpi_val_num"]),
            ("PLANT REJECTION %", rej_pct, fmt["kpi_val_pct"]),
            ("TOTAL QUALITY LOSS (COP)", tot_cost, fmt["kpi_val_cur"]),
        ]
        for col_idx, (label, val, val_fmt) in enumerate(tiles):
            ws_sum.write(3, col_idx + 1, label, fmt["kpi_label"])
            ws_sum.write(4, col_idx + 1, val, val_fmt)

        headers = ["Shop Code", "Division Name", "Produced Pcs", "OK Pcs", "Rejected Pcs", "Rejection %", "Quality Status"]
        for c_idx, h in enumerate(headers):
            ws_sum.write(7, c_idx, h, fmt["th"])

        row_idx = 8
        for _, r in df_shop.iterrows():
            r_pct = (r["rejected_qty"] / r["produced_qty"]) if r["produced_qty"] > 0 else 0.0
            th = 0.035 if "FOUNDRY" in r["shop_code"] else 0.020
            status_fmt = fmt["status_good"] if r_pct <= th else fmt["status_bad"]
            status_text = "Within Control" if r_pct <= th else "Action Required"

            ws_sum.write(row_idx, 0, str(r["shop_code"]), fmt["cell_center"])
            ws_sum.write(row_idx, 1, str(r["shop_name"]), fmt["cell_text"])
            ws_sum.write(row_idx, 2, int(r["produced_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 3, int(r["accepted_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 4, int(r["rejected_qty"]), fmt["cell_num"])
            ws_sum.write(row_idx, 5, r_pct, fmt["cell_pct"])
            ws_sum.write(row_idx, 6, status_text, status_fmt)
            row_idx += 1

        # Charts
        chart_dir = output_path.parent / "temp_charts"
        chart_dir.mkdir(parents=True, exist_ok=True)
        if not df_shop.empty:
            fig5 = chart_shop_comparison_bar_mpl(df_shop.assign(rejection_pct=df_shop["rejected_qty"]/df_shop["produced_qty"]*100), "Monthly Shop Rejection %")
            c5_path = save_matplotlib_png(fig5, chart_dir / "monthly_shop.png", dpi=150)
            ws_sum.insert_image(row_idx + 3, 1, str(c5_path), {"x_scale": 0.85, "y_scale": 0.85})

        # SHEET 2: Defect Pareto
        ws_pareto = wb.add_worksheet("Plant Defect Pareto")
        ws_pareto.freeze_panes(4, 0)
        ws_pareto.set_column(0, 0, 14)
        ws_pareto.set_column(1, 1, 16)
        ws_pareto.set_column(2, 2, 32)
        ws_pareto.set_column(3, 7, 16)
        ws_pareto.write(0, 0, "PLANT-WIDE DEFECT PARETO & COST BREAKDOWN", fmt["title"])

        p_headers = ["Shop", "Defect Code", "Defect Description", "Rejected Pcs", "Scrap Pcs", "Rework Pcs", "Loss Cost", "Cumulative %"]
        for c, h in enumerate(p_headers):
            ws_pareto.write(3, c, h, fmt["th"])

        tot_def = df_pareto["rejected_qty"].sum() if not df_pareto.empty else 1
        p_row = 4
        cum = 0.0
        for _, r in df_pareto.iterrows():
            pct = (r["rejected_qty"] / tot_def)
            cum += pct
            ws_pareto.write(p_row, 0, str(r["shop_code"]), fmt["cell_center"])
            ws_pareto.write(p_row, 1, str(r["defect_code"]), fmt["cell_center"])
            ws_pareto.write(p_row, 2, str(r["defect_name"]), fmt["cell_text"])
            ws_pareto.write(p_row, 3, int(r["rejected_qty"]), fmt["cell_num"])
            ws_pareto.write(p_row, 4, int(r["scrap_qty"]), fmt["cell_num"])
            ws_pareto.write(p_row, 5, int(r["reworkable_qty"]), fmt["cell_num"])
            ws_pareto.write(p_row, 6, float(r["scrap_cost"]), fmt["cell_cur"])
            ws_pareto.write(p_row, 7, min(cum, 1.0), fmt["cell_pct"])
            p_row += 1

        wb.close()
        logger.info(f"Monthly Rejection Report Workbook generated: {output_path}")
        return output_path

    # -----------------------------------------------------------------------
    # Batch Generator
    # -----------------------------------------------------------------------
    def build_all_reports(self, period_key: str = "2026-W45", month_key: str = "2026-11") -> Dict[str, Path]:
        """Builds all three workbooks and logs to report_runs."""
        loader = WarehouseLoader(self.db_path)
        results = {}

        # 1. Weekly Foundry
        f_path = self.build_weekly_foundry(period_key)
        loader.log_report_run(
            report_type="WEEKLY_FOUNDRY",
            period_key=period_key,
            status="SUCCESS",
            excel_path=str(f_path),
            generated_by="ExcelBuilder",
        )
        results["weekly_foundry"] = f_path

        # 2. Weekly Machine Shop
        m_path = self.build_weekly_machine_shop(period_key)
        loader.log_report_run(
            report_type="WEEKLY_MACHINE_SHOP",
            period_key=period_key,
            status="SUCCESS",
            excel_path=str(m_path),
            generated_by="ExcelBuilder",
        )
        results["weekly_machine_shop"] = m_path

        # 3. Monthly Rejection
        mo_path = self.build_monthly_rejection(month_key)
        loader.log_report_run(
            report_type="MONTHLY_REJECTION",
            period_key=month_key,
            status="SUCCESS",
            excel_path=str(mo_path),
            generated_by="ExcelBuilder",
        )
        results["monthly_rejection"] = mo_path

        return results


def main():
    parser = argparse.ArgumentParser(description="Generate MIS Excel Workbooks.")
    parser.add_argument("--week", type=str, default="2026-W45", help="ISO week key, e.g. 2026-W45")
    parser.add_argument("--month", type=str, default="2026-11", help="Month key, e.g. 2026-11")
    parser.add_argument("--type", type=str, choices=["foundry", "machine_shop", "monthly", "all"], default="all")

    args = parser.parse_args()
    builder = ExcelReportBuilder()

    print("\n" + "=" * 65)
    print(" Generating MIS Excel Workbooks...")
    print(f" Period: {args.week} | Month: {args.month} | Target: {args.type}")
    print("=" * 65)

    if args.type == "foundry":
        p = builder.build_weekly_foundry(args.week)
        print(f" Generated: {p}")
    elif args.type == "machine_shop":
        p = builder.build_weekly_machine_shop(args.week)
        print(f" Generated: {p}")
    elif args.type == "monthly":
        p = builder.build_monthly_rejection(args.month)
        print(f" Generated: {p}")
    else:
        res = builder.build_all_reports(args.week, args.month)
        for k, p in res.items():
            print(f" [{k.upper()}] -> {p}")
    print("=" * 65)


if __name__ == "__main__":
    main()

