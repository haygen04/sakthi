"""
Sakthi Manufacturing MIS Report Generator — CSV Ingestion & Report Generator
Allows users to upload or supply custom PMS production and rejection CSV files,
ingests them through the ETL pipeline, and generates Excel and PDF reports.
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config.loader import get_config
from etl.extract import parse_iso_week, parse_month, write_to_staging
from etl.load import WarehouseLoader, get_db_connection, log_report_run, update_report_run
from etl.transform import DataTransformer
from etl.validate import DataValidator
from reports.excel_builder import ExcelReportBuilder
from reports.pdf_builder import PDFReportBuilder

logger = logging.getLogger("etl.import_csv")


def detect_periods_from_csv(prod_df: pd.DataFrame) -> Tuple[str, str, str, str]:
    """
    Detects the minimum/maximum dates, ISO week, and month from production CSV.
    Returns: (start_date, end_date, iso_week, year_month)
    """
    date_col = None
    for col in ["production_date", "date", "log_date", "entry_date"]:
        if col in prod_df.columns:
            date_col = col
            break

    if not date_col:
        # Fallback to current week/month
        today = datetime.date.today()
        iso_year, iso_week, _ = today.isocalendar()
        return (str(today), str(today), f"{iso_year}-W{iso_week:02d}", today.strftime("%Y-%m"))

    dates = pd.to_datetime(prod_df[date_col], errors="coerce").dropna().sort_values()
    if dates.empty:
        today = datetime.date.today()
        iso_year, iso_week, _ = today.isocalendar()
        return (str(today), str(today), f"{iso_year}-W{iso_week:02d}", today.strftime("%Y-%m"))

    min_date = dates.iloc[0].date()
    max_date = dates.iloc[-1].date()

    iso_year, iso_week, _ = min_date.isocalendar()
    week_key = f"{iso_year}-W{iso_week:02d}"
    month_key = min_date.strftime("%Y-%m")

    return (str(min_date), str(max_date), week_key, month_key)


def process_custom_csvs(
    prod_csv_path: Optional[Path | str] = None,
    rej_csv_path: Optional[Path | str] = None,
    prod_content: Optional[str] = None,
    rej_content: Optional[str] = None,
    target_week: Optional[str] = None,
    target_month: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingests custom CSV contents or files into staging and fact tables,
    then automatically builds weekly and monthly reports.
    """
    import io

    # 1. Load DataFrames
    if prod_csv_path:
        prod_df = pd.read_csv(prod_csv_path)
    elif prod_content:
        prod_df = pd.read_csv(io.StringIO(prod_content))
    else:
        prod_df = pd.DataFrame()

    if rej_csv_path:
        rej_df = pd.read_csv(rej_csv_path)
    elif rej_content:
        rej_df = pd.read_csv(io.StringIO(rej_content))
    else:
        rej_df = pd.DataFrame()

    if prod_df.empty and rej_df.empty:
        raise ValueError("Both production and rejection CSV inputs are empty.")

    # 2. Determine target periods
    start_d, end_d, auto_week, auto_month = detect_periods_from_csv(prod_df if not prod_df.empty else rej_df)
    week_key = target_week or auto_week
    month_key = target_month or auto_month

    batch_id = f"BATCH-UPLOAD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    logger.info("Ingesting custom CSVs: Batch %s | Week %s | Month %s", batch_id, week_key, month_key)

    # 3. Write raw data to staging
    db_path = Path("mis_reporting.db")
    write_to_staging(prod_df, rej_df, batch_id, "CSV_UPLOAD", db_path)

    # 4. Transform & Validate
    transformer = DataTransformer()
    trans_res = transformer.transform(prod_df, rej_df)
    fact_prod_df = trans_res.get("fact_production", pd.DataFrame())
    fact_rej_df = trans_res.get("fact_rejection", pd.DataFrame())

    # 5. Warehouse Load (Idempotent Upsert)
    loader = WarehouseLoader()
    w_conn = loader.get_connection()
    try:
        # Ensure dates in dimension
        all_dates = []
        if not fact_prod_df.empty and "production_date" in fact_prod_df.columns:
            all_dates.extend(fact_prod_df["production_date"].dropna().astype(str).unique().tolist())
        if not fact_rej_df.empty and "production_date" in fact_rej_df.columns:
            all_dates.extend(fact_rej_df["production_date"].dropna().astype(str).unique().tolist())
        if all_dates:
            loader.ensure_date_dimension(w_conn, list(set(all_dates)))

        prod_count = loader.load_fact_production(w_conn, fact_prod_df)
        rej_count = loader.load_fact_rejection(w_conn, fact_rej_df)
    finally:
        w_conn.close()

    logger.info("Warehouse loaded: %d production rows, %d rejection rows.", prod_count, rej_count)

    # 6. Generate Standardized Reports (Excel + PDF)
    excel_builder = ExcelReportBuilder()
    pdf_builder = PDFReportBuilder()

    reports = {}

    # Weekly Foundry
    f_excel = excel_builder.build_weekly_foundry(period_key=week_key)
    f_pdf = pdf_builder.build_weekly_foundry_pdf(period_key=week_key)
    reports["weekly_foundry"] = {
        "excel": str(f_excel),
        "pdf": str(f_pdf),
        "excel_url": f"/output/weekly_foundry/{week_key}/{Path(f_excel).name}",
        "pdf_url": f"/output/weekly_foundry/{week_key}/{Path(f_pdf).name}",
    }

    # Weekly Machine Shop
    m_excel = excel_builder.build_weekly_machine_shop(period_key=week_key)
    m_pdf = pdf_builder.build_weekly_machine_shop_pdf(period_key=week_key)
    reports["weekly_machine_shop"] = {
        "excel": str(m_excel),
        "pdf": str(m_pdf),
        "excel_url": f"/output/weekly_machine_shop/{week_key}/{Path(m_excel).name}",
        "pdf_url": f"/output/weekly_machine_shop/{week_key}/{Path(m_pdf).name}",
    }

    # Monthly Rejection
    mon_excel = excel_builder.build_monthly_rejection(month_key=month_key)
    mon_pdf = pdf_builder.build_monthly_rejection_pdf(month_key=month_key)
    reports["monthly_rejection"] = {
        "excel": str(mon_excel),
        "pdf": str(mon_pdf),
        "excel_url": f"/output/monthly_rejection/{month_key}/{Path(mon_excel).name}",
        "pdf_url": f"/output/monthly_rejection/{month_key}/{Path(mon_pdf).name}",
    }

    return {
        "status": "SUCCESS",
        "batch_id": batch_id,
        "week_key": week_key,
        "month_key": month_key,
        "production_rows_loaded": prod_count,
        "rejection_rows_loaded": rej_count,
        "reports": reports,
    }


def main():
    parser = argparse.ArgumentParser(description="Sakthi MIS — Custom CSV Ingestion & Report Generator")
    parser.add_argument("--prod", help="Path to production CSV file")
    parser.add_argument("--rej", help="Path to rejection CSV file")
    parser.add_argument("--week", help="Target ISO week (e.g., 2026-W45, or auto-detect)")
    parser.add_argument("--month", help="Target month (e.g., 2026-11, or auto-detect)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if not args.prod and not args.rej:
        print("Please provide at least one CSV file via --prod or --rej.")
        parser.print_help()
        sys.exit(1)

    print("\n========================================================")
    print(" Ingesting Custom CSVs and Generating Reports")
    print(f" Production CSV: {args.prod}")
    print(f" Rejection CSV:  {args.rej}")
    print("========================================================\n")

    result = process_custom_csvs(
        prod_csv_path=args.prod,
        rej_csv_path=args.rej,
        target_week=args.week,
        target_month=args.month,
    )

    print("\n--------------------------------------------------------")
    print(" Reports Generation Completed Successfully!")
    print(f" Detected Period: Week {result['week_key']} | Month {result['month_key']}")
    print(f" Production Rows: {result['production_rows_loaded']}")
    print(f" Rejection Rows:  {result['rejection_rows_loaded']}")
    print("\n Generated Artifacts:")
    for name, files in result["reports"].items():
        print(f" [{name.upper()}]")
        print(f"   Excel: {files['excel']}")
        print(f"   PDF:   {files['pdf']}")
    print("--------------------------------------------------------\n")


if __name__ == "__main__":
    main()
