"""Data Extraction Module for Manufacturing MIS & Rejection Report Generator.

Extracts raw production and quality records from PMS (via DB, REST API, or CSV exports),
filters by date range, and writes raw extract records into the staging schema with
retry logic, audit batch IDs, and comprehensive logging.
"""

import os
import sys
import uuid
import time
import argparse
import logging
import calendar
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Tuple, Optional, Any
import pandas as pd

from config.loader import load_config
from etl.db_init import get_sqlite_conn

# ---------------------------------------------------------------------------
# Setup Logging to both console and logs/etl.log
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "etl.log"

logger = logging.getLogger("etl.extract")
logger.setLevel(logging.INFO)
logger.propagate = False

# Formatter
formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

# File Handler
file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# Avoid duplicate handlers if re-imported
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Date Resolution Helpers
# ---------------------------------------------------------------------------
def parse_iso_week(week_str: str) -> Tuple[date, date]:
    """Converts ISO week string like '2026-W45' or '2026-45' to (start_date, end_date)."""
    import re
    match = re.match(r"^(\d{4})-?W?(\d{1,2})$", week_str.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid week format: '{week_str}'. Expected format: 'YYYY-Wnn' (e.g. '2026-W45')")
    year, week = int(match.group(1)), int(match.group(2))
    start = date.fromisocalendar(year, week, 1)  # Monday
    end = date.fromisocalendar(year, week, 7)    # Sunday
    return start, end


def parse_month(month_str: str) -> Tuple[date, date]:
    """Converts month string like '2026-11' to (start_date, end_date)."""
    parts = month_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid month format: '{month_str}'. Expected format: 'YYYY-MM' (e.g. '2026-11')")
    year, month = int(parts[0]), int(parts[1])
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def resolve_date_range(
    week: Optional[str] = None,
    month: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[date, date, str]:
    """Resolves CLI arguments into a concrete date range and period identifier."""
    if week:
        d_start, d_end = parse_iso_week(week)
        period_key = week.upper() if "W" in week.upper() else f"{week[:4]}-W{week[5:]}"
    elif month:
        d_start, d_end = parse_month(month)
        period_key = month
    elif start_date and end_date:
        d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        period_key = f"{start_date}_to_{end_date}"
    else:
        # Default to current ISO week
        today = date.today()
        year, week_num, _ = today.isocalendar()
        period_key = f"{year}-W{week_num:02d}"
        d_start, d_end = parse_iso_week(period_key)

    if d_start > d_end:
        raise ValueError(f"Start date {d_start} cannot be after end date {d_end}")

    return d_start, d_end, period_key


# ---------------------------------------------------------------------------
# PMS Extract Connectors with Retries
# ---------------------------------------------------------------------------
def retry_operation(operation, max_retries: int = 3, initial_delay: float = 1.0, backoff: float = 2.0):
    """Executes an operation with exponential backoff retries."""
    delay = initial_delay
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except Exception as exc:
            last_exc = exc
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {exc}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
            delay *= backoff
    raise RuntimeError(f"Operation failed after {max_retries} attempts: {last_exc}") from last_exc


class CSVFallbackConnector:
    """Extracts PMS production and rejection data from exported CSV/Excel files."""

    def __init__(self, csv_dir: Path):
        self.csv_dir = Path(csv_dir)

    def extract(self, start_date: date, end_date: date) -> Tuple[pd.DataFrame, pd.DataFrame]:
        logger.info(f"Extracting from CSV files in directory: {self.csv_dir}")
        prod_file = self.csv_dir / "pms_production_sample.csv"
        rej_file = self.csv_dir / "pms_rejection_sample.csv"

        if not prod_file.exists() or not rej_file.exists():
            raise FileNotFoundError(f"Sample CSV exports missing in {self.csv_dir}")

        df_prod = pd.read_csv(prod_file, dtype=str)
        df_rej = pd.read_csv(rej_file, dtype=str)

        # Filter by date range
        df_prod["_dt"] = pd.to_datetime(df_prod["production_date"], errors="coerce").dt.date
        df_rej["_dt"] = pd.to_datetime(df_rej["production_date"], errors="coerce").dt.date

        filtered_prod = df_prod[(df_prod["_dt"] >= start_date) & (df_prod["_dt"] <= end_date)].drop(columns=["_dt"])
        filtered_rej = df_rej[(df_rej["_dt"] >= start_date) & (df_rej["_dt"] <= end_date)].drop(columns=["_dt"])

        logger.info(f"CSV Extract complete: {len(filtered_prod)} production rows, {len(filtered_rej)} rejection rows.")
        return filtered_prod, filtered_rej


class DBConnector:
    """Extracts from PMS relational database via SQLAlchemy or fallback connection."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def extract(self, start_date: date, end_date: date) -> Tuple[pd.DataFrame, pd.DataFrame]:
        logger.info(f"Extracting from PMS Database: {self.db_url}")

        def _fetch():
            try:
                import sqlalchemy as sa
                engine = sa.create_engine(self.db_url)
                prod_query = sa.text(
                    "SELECT * FROM pms_production_logs WHERE production_date BETWEEN :s AND :e"
                )
                rej_query = sa.text(
                    "SELECT * FROM pms_rejection_logs WHERE production_date BETWEEN :s AND :e"
                )
                with engine.connect() as conn:
                    df_prod = pd.read_sql(prod_query, conn, params={"s": str(start_date), "e": str(end_date)})
                    df_rej = pd.read_sql(rej_query, conn, params={"s": str(start_date), "e": str(end_date)})
                return df_prod.astype(str), df_rej.astype(str)
            except Exception as e:
                logger.warning(f"Direct DB query failed: {e}. Falling back to SQLite/CSV simulation.")
                raise

        return retry_operation(_fetch, max_retries=2, initial_delay=0.5)


class RESTAPIConnector:
    """Extracts PMS data via REST API endpoints."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def extract(self, start_date: date, end_date: date) -> Tuple[pd.DataFrame, pd.DataFrame]:
        logger.info(f"Extracting from PMS REST API: {self.base_url}")
        import requests

        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        params = {"from": str(start_date), "to": str(end_date)}

        def _fetch():
            prod_res = requests.get(f"{self.base_url}/production", headers=headers, params=params, timeout=self.timeout)
            prod_res.raise_for_status()
            rej_res = requests.get(f"{self.base_url}/rejections", headers=headers, params=params, timeout=self.timeout)
            rej_res.raise_for_status()

            df_prod = pd.DataFrame(prod_res.json()).astype(str)
            df_rej = pd.DataFrame(rej_res.json()).astype(str)
            return df_prod, df_rej

        return retry_operation(_fetch, max_retries=3, initial_delay=1.0)


# ---------------------------------------------------------------------------
# Staging Database Writer
# ---------------------------------------------------------------------------
def write_to_staging(
    df_prod: pd.DataFrame,
    df_rej: pd.DataFrame,
    batch_id: str,
    source_type: str,
    db_path: Path,
) -> Tuple[int, int]:
    """Writes extracted raw DataFrames into stg_production and stg_rejection."""
    logger.info(f"Writing raw extracts to staging (Batch: {batch_id}, Source: {source_type})")
    conn = get_sqlite_conn(db_path)
    cursor = conn.cursor()

    # Insert into stg_production
    prod_inserted = 0
    if not df_prod.empty:
        prod_records = []
        for _, row in df_prod.iterrows():
            prod_records.append((
                batch_id,
                source_type,
                str(row.get("log_id", "")),
                str(row.get("production_date", "")),
                str(row.get("shop_code", "")),
                str(row.get("shift_code", "")),
                str(row.get("machine_code", "")),
                str(row.get("part_number", "")),
                str(row.get("target_qty", "0")),
                str(row.get("produced_qty", "0")),
                str(row.get("accepted_qty", "0")),
                str(row.get("gross_weight_kg", "0.0")),
                str(row.get("operator_id", "")),
                str(row.get("raw_timestamp", "")),
            ))

        cursor.executemany(
            """INSERT INTO stg_production (
                batch_id, source_type, log_id, production_date, shop_code, shift_code,
                machine_code, part_number, target_qty, produced_qty, accepted_qty,
                gross_weight_kg, operator_id, raw_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            prod_records,
        )
        prod_inserted = len(prod_records)

    # Insert into stg_rejection
    rej_inserted = 0
    if not df_rej.empty:
        rej_records = []
        for _, row in df_rej.iterrows():
            rej_records.append((
                batch_id,
                source_type,
                str(row.get("rejection_id", "")),
                str(row.get("production_date", "")),
                str(row.get("shop_code", "")),
                str(row.get("shift_code", "")),
                str(row.get("machine_code", "")),
                str(row.get("part_number", "")),
                str(row.get("defect_code", "")),
                str(row.get("rejected_qty", "0")),
                str(row.get("reworkable_qty", "0")),
                str(row.get("scrap_qty", "0")),
                str(row.get("unit_cost", "0.0")),
                str(row.get("inspector_id", "")),
                str(row.get("root_cause_notes", "")),
                str(row.get("raw_timestamp", "")),
            ))

        cursor.executemany(
            """INSERT INTO stg_rejection (
                batch_id, source_type, rejection_id, production_date, shop_code, shift_code,
                machine_code, part_number, defect_code, rejected_qty, reworkable_qty,
                scrap_qty, unit_cost, inspector_id, root_cause_notes, raw_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rej_records,
        )
        rej_inserted = len(rej_records)

    conn.commit()
    conn.close()
    logger.info(f"Staging ingestion complete: {prod_inserted} production rows, {rej_inserted} rejection rows loaded.")
    return prod_inserted, rej_inserted


# ---------------------------------------------------------------------------
# Main ETL Extract Orchestrator
# ---------------------------------------------------------------------------
def run_extraction(
    week: Optional[str] = None,
    month: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Orchestrates extraction from PMS into the staging schema."""
    config = load_config()
    db_path = ROOT_DIR / "mis_reporting.db"

    # Resolve dates
    d_start, d_end, period_key = resolve_date_range(week, month, start_date, end_date)
    logger.info(f"Starting extraction for period '{period_key}' ({d_start} to {d_end})")

    # Select Mode
    extract_mode = mode or config.get("pms", {}).get("default_mode", "csv")
    batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    df_prod, df_rej = None, None

    if extract_mode == "db":
        db_url = config.get("pms", {}).get("db", {}).get("url")
        connector = DBConnector(db_url)
        try:
            df_prod, df_rej = connector.extract(d_start, d_end)
        except Exception as e:
            logger.warning(f"DB Extraction failed: {e}. Switching to CSV fallback loader.")
            extract_mode = "csv_fallback"

    elif extract_mode == "api":
        api_conf = config.get("pms", {}).get("api", {})
        connector = RESTAPIConnector(api_conf.get("base_url"), api_conf.get("api_key"))
        try:
            df_prod, df_rej = connector.extract(d_start, d_end)
        except Exception as e:
            logger.warning(f"API Extraction failed: {e}. Switching to CSV fallback loader.")
            extract_mode = "csv_fallback"

    if df_prod is None or df_rej is None:
        # CSV mode / fallback
        csv_dir = ROOT_DIR / config.get("pms", {}).get("csv", {}).get("directory", "sample_data/pms_exports")
        csv_connector = CSVFallbackConnector(csv_dir)
        df_prod, df_rej = csv_connector.extract(d_start, d_end)

    # Write to staging tables
    prod_count, rej_count = write_to_staging(
        df_prod, df_rej, batch_id, extract_mode.upper(), db_path
    )

    summary = {
        "status": "SUCCESS",
        "batch_id": batch_id,
        "period_key": period_key,
        "start_date": str(d_start),
        "end_date": str(d_end),
        "source_mode": extract_mode,
        "stg_production_count": prod_count,
        "stg_rejection_count": rej_count,
    }
    logger.info(f"Extraction Pipeline Summary: {summary}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Extract production & rejection data from PMS into staging.")
    parser.add_argument("--week", type=str, help="ISO week string, e.g. 2026-W45")
    parser.add_argument("--month", type=str, help="Month string, e.g. 2026-11")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--mode", type=str, choices=["csv", "db", "api"], help="Extraction mode override")

    args = parser.parse_args()

    try:
        res = run_extraction(
            week=args.week,
            month=args.month,
            start_date=args.start_date,
            end_date=args.end_date,
            mode=args.mode,
        )
        print("\n" + "=" * 60)
        print(" Extraction Successful!")
        print(f" Batch ID:              {res['batch_id']}")
        print(f" Period:                {res['period_key']} ({res['start_date']} to {res['end_date']})")
        print(f" Source Mode:           {res['source_mode']}")
        print(f" Staged Production Rows: {res['stg_production_count']}")
        print(f" Staged Rejection Rows:  {res['stg_rejection_count']}")
        print("=" * 60)
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Extraction failed: {exc}", exc_info=True)
        print(f"\n[ERROR] Extraction failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
