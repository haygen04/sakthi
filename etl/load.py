"""Reporting Warehouse Loader Module.

Resolves natural codes to dimension surrogate keys, populates dim_date,
executes idempotent upserts on fact_production and fact_rejection,
and manages audit logging in report_runs.
"""

import sys
import sqlite3
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import numpy as np

from config.loader import load_config
from etl.db_init import get_sqlite_conn
from etl.extract import resolve_date_range, run_extraction
from etl.transform import DataTransformer

ROOT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT_DIR / "logs"
LOG_FILE = LOGS_DIR / "etl.log"

logger = logging.getLogger("etl.load")
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


class WarehouseLoader:
    """Manages dimension lookups and idempotent upserts into fact and audit tables."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (ROOT_DIR / "mis_reporting.db")
        self.config = load_config()

    def get_connection(self):
        return get_sqlite_conn(self.db_path)

    # -----------------------------------------------------------------------
    # Dimension Key Resolution
    # -----------------------------------------------------------------------
    def get_dimension_lookups(self, conn) -> Dict[str, Dict[str, int]]:
        """Loads natural code to surrogate ID lookup dictionaries from dim tables."""
        cursor = conn.cursor()

        lookups = {}
        # Shops
        cursor.execute("SELECT shop_code, shop_id FROM dim_shop;")
        lookups["shop"] = {row[0].upper(): row[1] for row in cursor.fetchall()}

        # Shifts
        cursor.execute("SELECT shift_code, shift_id FROM dim_shift;")
        lookups["shift"] = {row[0].upper(): row[1] for row in cursor.fetchall()}

        # Parts
        cursor.execute("SELECT part_number, part_id FROM dim_part;")
        lookups["part"] = {row[0].upper(): row[1] for row in cursor.fetchall()}

        # Machines
        cursor.execute("SELECT machine_code, machine_id FROM dim_machine;")
        lookups["machine"] = {row[0].upper(): row[1] for row in cursor.fetchall()}

        # Defects
        cursor.execute("SELECT defect_code, defect_id FROM dim_defect;")
        lookups["defect"] = {row[0].upper(): row[1] for row in cursor.fetchall()}

        return lookups

    def ensure_date_dimension(self, conn, dates: List[str]):
        """Populates dim_date for all dates encountered in the batch."""
        cursor = conn.cursor()
        for d_str in set(dates):
            if not d_str:
                continue
            cursor.execute("SELECT 1 FROM dim_date WHERE date_key = ?", (d_str,))
            if cursor.fetchone():
                continue

            dt = datetime.strptime(d_str, "%Y-%m-%d").date()
            year, week_num, dow = dt.isocalendar()
            day_name = dt.strftime("%A")
            month_num = dt.month
            month_name = dt.strftime("%B")
            quarter = (month_num - 1) // 3 + 1
            year_week = f"{year}-W{week_num:02d}"
            year_month = f"{year}-{month_num:02d}"
            is_weekend = dow in (6, 7)

            cursor.execute(
                """INSERT OR IGNORE INTO dim_date (
                    date_key, day_name, day_of_week, week_number, year_week,
                    month_number, month_name, year_month, quarter, year, is_weekend
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    d_str, day_name, dow, week_num, year_week,
                    month_num, month_name, year_month, quarter, dt.year, int(is_weekend)
                )
            )
        conn.commit()

    # -----------------------------------------------------------------------
    # Idempotent Fact Loading (Upsert)
    # -----------------------------------------------------------------------
    def load_fact_production(self, conn, fact_prod_df: pd.DataFrame) -> int:
        """Upserts transformed production records into fact_production."""
        if fact_prod_df.empty:
            return 0

        lookups = self.get_dimension_lookups(conn)
        self.ensure_date_dimension(conn, fact_prod_df["date_key"].tolist())

        cursor = conn.cursor()
        records = []
        for _, row in fact_prod_df.iterrows():
            date_key = str(row["date_key"])
            year_week = str(row["year_week"])
            year_month = str(row["year_month"])
            shop_id = lookups["shop"].get(str(row["shop_code"]).upper())
            shift_id = lookups["shift"].get(str(row["shift_code"]).upper())
            machine_id = lookups["machine"].get(str(row["machine_code"]).upper())
            part_id = lookups["part"].get(str(row["part_number"]).upper())

            # Skip if foreign keys could not be resolved
            if not all([shop_id, shift_id, machine_id, part_id]):
                logger.warning(f"Skipping fact_production row due to missing FK: {row.to_dict()}")
                continue

            records.append((
                date_key, year_week, year_month, shop_id, shift_id, machine_id, part_id,
                int(row.get("target_qty", 0)),
                int(row.get("produced_qty", 0)),
                int(row.get("accepted_qty", 0)),
                int(row.get("rejected_qty", 0)),
                float(row.get("rejection_pct", 0.0)),
                float(row.get("first_pass_yield_pct", 100.0)),
                float(row.get("gross_weight_kg", 0.0)),
            ))

        # Idempotent Upsert for SQLite
        upsert_sql = """
        INSERT INTO fact_production (
            date_key, year_week, year_month, shop_id, shift_id, machine_id, part_id,
            target_qty, produced_qty, accepted_qty, rejected_qty, rejection_pct,
            first_pass_yield_pct, gross_weight_kg, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(date_key, shop_id, shift_id, machine_id, part_id) DO UPDATE SET
            target_qty = excluded.target_qty,
            produced_qty = excluded.produced_qty,
            accepted_qty = excluded.accepted_qty,
            rejected_qty = excluded.rejected_qty,
            rejection_pct = excluded.rejection_pct,
            first_pass_yield_pct = excluded.first_pass_yield_pct,
            gross_weight_kg = excluded.gross_weight_kg,
            updated_at = CURRENT_TIMESTAMP;
        """
        cursor.executemany(upsert_sql, records)
        conn.commit()
        logger.info(f"Loaded {len(records)} records into fact_production (idempotent upsert).")
        return len(records)

    def load_fact_rejection(self, conn, fact_rej_df: pd.DataFrame) -> int:
        """Upserts transformed defect transactions into fact_rejection."""
        if fact_rej_df.empty:
            return 0

        lookups = self.get_dimension_lookups(conn)
        self.ensure_date_dimension(conn, fact_rej_df["date_key"].tolist())

        cursor = conn.cursor()
        records = []
        for _, row in fact_rej_df.iterrows():
            date_key = str(row["date_key"])
            year_week = str(row["year_week"])
            year_month = str(row["year_month"])
            shop_id = lookups["shop"].get(str(row["shop_code"]).upper())
            shift_id = lookups["shift"].get(str(row["shift_code"]).upper())
            machine_id = lookups["machine"].get(str(row["machine_code"]).upper())
            part_id = lookups["part"].get(str(row["part_number"]).upper())
            defect_id = lookups["defect"].get(str(row["defect_code"]).upper())

            if not all([shop_id, shift_id, machine_id, part_id, defect_id]):
                logger.warning(f"Skipping fact_rejection row due to missing FK: {row.to_dict()}")
                continue

            records.append((
                date_key, year_week, year_month, shop_id, shift_id, machine_id, part_id, defect_id,
                int(row.get("rejected_qty", 0)),
                int(row.get("scrap_qty", 0)),
                int(row.get("reworkable_qty", 0)),
                float(row.get("scrap_cost", 0.0)),
            ))

        upsert_sql = """
        INSERT INTO fact_rejection (
            date_key, year_week, year_month, shop_id, shift_id, machine_id, part_id, defect_id,
            rejected_qty, scrap_qty, reworkable_qty, scrap_cost, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(date_key, shop_id, shift_id, machine_id, part_id, defect_id) DO UPDATE SET
            rejected_qty = excluded.rejected_qty,
            scrap_qty = excluded.scrap_qty,
            reworkable_qty = excluded.reworkable_qty,
            scrap_cost = excluded.scrap_cost,
            updated_at = CURRENT_TIMESTAMP;
        """
        cursor.executemany(upsert_sql, records)
        conn.commit()
        logger.info(f"Loaded {len(records)} records into fact_rejection (idempotent upsert).")
        return len(records)

    # -----------------------------------------------------------------------
    # Report Runs Audit Registry
    # -----------------------------------------------------------------------
    def log_report_run(
        self,
        report_type: str,
        period_key: str,
        status: str = "IN_PROGRESS",
        excel_path: Optional[str] = None,
        pdf_path: Optional[str] = None,
        total_produced: int = 0,
        total_rejected: int = 0,
        rejection_pct: float = 0.0,
        generated_by: str = "SYSTEM",
        run_duration_ms: int = 0,
        error_message: Optional[str] = None,
    ) -> int:
        """Creates an audit record in report_runs and returns its run_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO report_runs (
                report_type, period_key, status, excel_path, pdf_path,
                total_produced, total_rejected, rejection_pct, generated_by,
                run_duration_ms, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                report_type, period_key, status, excel_path, pdf_path,
                total_produced, total_rejected, rejection_pct, generated_by,
                run_duration_ms, error_message
            )
        )
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Audit log created: report_runs ID {run_id} ({report_type} | {period_key} | {status})")
        return run_id

    def update_report_run(
        self,
        run_id: int,
        status: str,
        excel_path: Optional[str] = None,
        pdf_path: Optional[str] = None,
        run_duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        total_produced: Optional[int] = None,
        total_rejected: Optional[int] = None,
        rejection_pct: Optional[float] = None,
    ):
        """Updates an existing report_runs record status and file links."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE report_runs SET
                status = ?,
                excel_path = COALESCE(?, excel_path),
                pdf_path = COALESCE(?, pdf_path),
                run_duration_ms = COALESCE(?, run_duration_ms),
                error_message = ?,
                total_produced = COALESCE(?, total_produced),
                total_rejected = COALESCE(?, total_rejected),
                rejection_pct = COALESCE(?, rejection_pct)
            WHERE run_id = ?""",
            (
                status,
                excel_path,
                pdf_path,
                run_duration_ms,
                error_message,
                total_produced,
                total_rejected,
                rejection_pct,
                run_id,
            ),
        )
        conn.commit()
        conn.close()


def get_db_connection(db_path: Optional[Path] = None):
    """Convenience helper to retrieve an active SQLite/MySQL database connection."""
    return WarehouseLoader(db_path=db_path).get_connection()


def log_report_run(*args, **kwargs) -> int:
    """Convenience wrapper for WarehouseLoader.log_report_run."""
    return WarehouseLoader().log_report_run(*args, **kwargs)


def update_report_run(*args, **kwargs):
    """Convenience wrapper for WarehouseLoader.update_report_run."""
    return WarehouseLoader().update_report_run(*args, **kwargs)


# ---------------------------------------------------------------------------
# High-Level Pipeline Loader
# ---------------------------------------------------------------------------
def load_pipeline(
    week: Optional[str] = None,
    month: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs extract (if needed), transform, and idempotent loading into warehouse."""
    start_time = datetime.now()
    d_start, d_end, period_key = resolve_date_range(week, month, start_date, end_date)

    loader = WarehouseLoader()
    conn = loader.get_connection()

    # If staging records exist for period, read from staging; else trigger extract
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM stg_production WHERE production_date BETWEEN ? AND ?",
        (str(d_start), str(d_end))
    )
    staged_count = cursor.fetchone()[0]

    if staged_count == 0 or batch_id:
        logger.info(f"No existing staging records found for {period_key}. Triggering extract...")
        extract_res = run_extraction(week=week, month=month, start_date=start_date, end_date=end_date)
        batch_id = extract_res["batch_id"]

    # Pull staging data
    query_prod = "SELECT * FROM stg_production WHERE production_date BETWEEN ? AND ?"
    query_rej = "SELECT * FROM stg_rejection WHERE production_date BETWEEN ? AND ?"

    raw_prod = pd.read_sql_query(query_prod, conn, params=(str(d_start), str(d_end)))
    raw_rej = pd.read_sql_query(query_rej, conn, params=(str(d_start), str(d_end)))

    # Transform
    transformer = DataTransformer()
    trans_res = transformer.transform(raw_prod, raw_rej)

    # Load into facts
    prod_loaded = loader.load_fact_production(conn, trans_res["fact_production"])
    rej_loaded = loader.load_fact_rejection(conn, trans_res["fact_rejection"])

    conn.close()

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    summary = {
        "status": "SUCCESS",
        "period_key": period_key,
        "date_range": f"{d_start} to {d_end}",
        "fact_production_loaded": prod_loaded,
        "fact_rejection_loaded": rej_loaded,
        "duration_ms": duration_ms,
        "shop_kpis": trans_res["shop_kpis"],
    }
    logger.info(f"Warehouse Load Complete: {summary}")
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Load transformed data into reporting warehouse.")
    parser.add_argument("--week", type=str, help="ISO week, e.g. 2026-W45")
    parser.add_argument("--month", type=str, help="Month, e.g. 2026-11")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")

    args = parser.parse_args()
    try:
        res = load_pipeline(
            week=args.week,
            month=args.month,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        print("\n" + "=" * 60)
        print(" Warehouse Load Successful!")
        print(f" Period:                 {res['period_key']} ({res['date_range']})")
        print(f" fact_production Rows:   {res['fact_production_loaded']}")
        print(f" fact_rejection Rows:    {res['fact_rejection_loaded']}")
        print(f" Duration:               {res['duration_ms']} ms")
        print("=" * 60)
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Warehouse load failed: {exc}", exc_info=True)
        print(f"\n[ERROR] Load failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
