"""
Sakthi Manufacturing MIS Report Generator — Phase 7: Scheduling Engine
Automates extraction, transformation, warehouse loading, Excel/PDF generation,
and executive email dispatch using APScheduler with cron triggers and error handling.
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:
    BackgroundScheduler = None  # type: ignore
    BlockingScheduler = None     # type: ignore
    CronTrigger = None           # type: ignore

from config.loader import get_config
from etl.extract import run_extraction
from etl.load import get_db_connection, load_pipeline, log_report_run, update_report_run
from notify.mailer import ReportMailer
from reports.excel_builder import ExcelReportBuilder
from reports.pdf_builder import PDFReportBuilder

logger = logging.getLogger("scheduler.jobs")


# ---------------------------------------------------------------------------
# Default Period Resolvers
# ---------------------------------------------------------------------------

def get_default_week_key() -> str:
    """
    Returns ISO week string for the previous complete week (or current week).
    Format: YYYY-Www (e.g., '2026-W45').
    """
    today = datetime.date.today()
    # Go back 7 days to report on previous week
    prev_week_day = today - datetime.timedelta(days=7)
    iso_year, iso_week, _ = prev_week_day.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def get_default_month_key() -> str:
    """
    Returns month string for the previous complete month (or current month).
    Format: YYYY-MM (e.g., '2026-11').
    """
    today = datetime.date.today()
    first_of_month = today.replace(day=1)
    prev_month_last_day = first_of_month - datetime.timedelta(days=1)
    return prev_month_last_day.strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Pipeline Execution Functions
# ---------------------------------------------------------------------------

def run_weekly_foundry_pipeline(
    week_key: Optional[str] = None,
    mailer: Optional[ReportMailer] = None,
) -> Dict[str, Any]:
    """
    Execute full pipeline for Weekly Foundry MIS report:
    extract -> transform & load -> Excel -> PDF -> email delivery.
    """
    week_key = week_key or get_default_week_key()
    mailer = mailer or ReportMailer()
    run_id: Optional[int] = None
    start_time = datetime.datetime.now()

    logger.info("[scheduler] Starting Weekly Foundry pipeline for %s", week_key)
    try:
        run_id = log_report_run(
            report_type="WEEKLY_FOUNDRY_PIPELINE",
            period_key=week_key,
            generated_by="scheduler",
        )

        # 1. Extraction (CSV fallback or DB/API based on configuration)
        run_extraction(week=week_key)

        # 2. Transform & Warehouse Load
        load_summary = load_pipeline(week=week_key)

        # 3. Build Excel Report
        excel_builder = ExcelReportBuilder()
        excel_path = excel_builder.build_weekly_foundry(period_key=week_key)

        # 4. Build PDF Report
        pdf_builder = PDFReportBuilder()
        pdf_path = pdf_builder.build_weekly_foundry_pdf(period_key=week_key)

        # 5. Extract KPIs for email notification
        kpis = {}
        observations = []
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT 
                        COALESCE(SUM(fp.produced_qty), 0) AS produced_qty,
                        COALESCE(SUM(fp.accepted_qty), 0) AS accepted_qty,
                        COALESCE(SUM(fp.rejected_qty), 0) AS rejected_qty,
                        COALESCE(SUM(fp.gross_weight_kg), 0) / 1000.0 AS total_weight_mt
                    FROM fact_production fp
                    JOIN dim_shop ds ON fp.shop_id = ds.shop_id
                    WHERE ds.shop_code = 'FOUNDRY' AND fp.year_week = ?
                    """,
                    (week_key,),
                )
                row = cur.fetchone()
                p, a, r, wt = row if row else (0, 0, 0, 0.0)

                cur.execute(
                    """
                    SELECT COALESCE(SUM(fr.scrap_cost), 0)
                    FROM fact_rejection fr
                    JOIN dim_shop ds ON fr.shop_id = ds.shop_id
                    WHERE ds.shop_code = 'FOUNDRY' AND fr.year_week = ?
                    """,
                    (week_key,),
                )
                sc_row = cur.fetchone()
                sc = sc_row[0] if sc_row else 0.0

                rej_pct = (r / p * 100.0) if p > 0 else 0.0
                kpis = {
                    "produced_qty": p,
                    "accepted_qty": a,
                    "rejected_qty": r,
                    "rejection_pct": rej_pct,
                    "total_weight_mt": wt,
                    "scrap_cost": sc,
                    "status": "critical" if rej_pct >= 4.5 else ("warning" if rej_pct >= 3.5 else "good"),
                }
                observations.append(
                    f"Weekly poured castings reached {p:,} units with overall foundry rejection rate at {rej_pct:.2f}%."
                )
            except Exception as e:
                logger.warning("[scheduler] Failed to query Foundry email KPIs: %s", e)
            finally:
                conn.close()

        # 6. Dispatch Email Notification
        attachments = [p for p in [excel_path, pdf_path] if p and Path(p).exists()]
        mail_sent = mailer.send_report(
            report_type="WEEKLY_FOUNDRY",
            period_key=week_key,
            kpis=kpis,
            observations=observations,
            attachments=attachments,
        )

        duration_ms = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
        if run_id:
            update_report_run(
                run_id=run_id,
                status="SUCCESS",
                excel_path=str(excel_path) if excel_path else None,
                pdf_path=str(pdf_path) if pdf_path else None,
                total_produced=kpis.get("produced_qty"),
                total_rejected=kpis.get("rejected_qty"),
                rejection_pct=kpis.get("rejection_pct"),
                run_duration_ms=duration_ms,
            )

        logger.info("[scheduler] Weekly Foundry pipeline completed successfully.")
        return {
            "status": "SUCCESS",
            "period": week_key,
            "excel_path": str(excel_path),
            "pdf_path": str(pdf_path),
            "mail_sent": mail_sent,
            "kpis": kpis,
        }

    except Exception as exc:
        err_msg = str(exc)
        tb = traceback.format_exc()
        logger.error("[scheduler] Weekly Foundry pipeline failed: %s\n%s", err_msg, tb)
        if run_id:
            update_report_run(run_id=run_id, status="FAILED", error_message=err_msg)
        mailer.send_failure_alert("Weekly Foundry Pipeline", week_key, err_msg, tb)
        raise


def run_weekly_machine_shop_pipeline(
    week_key: Optional[str] = None,
    mailer: Optional[ReportMailer] = None,
) -> Dict[str, Any]:
    """
    Execute full pipeline for Weekly Machine Shop MIS report:
    extract -> transform & load -> Excel -> PDF -> email delivery.
    """
    week_key = week_key or get_default_week_key()
    mailer = mailer or ReportMailer()
    run_id: Optional[int] = None
    start_time = datetime.datetime.now()

    logger.info("[scheduler] Starting Weekly Machine Shop pipeline for %s", week_key)
    try:
        run_id = log_report_run(
            report_type="WEEKLY_MACHINE_SHOP_PIPELINE",
            period_key=week_key,
            generated_by="scheduler",
        )

        run_extraction(week=week_key)
        load_summary = load_pipeline(week=week_key)

        excel_builder = ExcelReportBuilder()
        excel_path = excel_builder.build_weekly_machine_shop(period_key=week_key)

        pdf_builder = PDFReportBuilder()
        pdf_path = pdf_builder.build_weekly_machine_shop_pdf(period_key=week_key)

        kpis = {}
        observations = []
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT 
                        COALESCE(SUM(fp.produced_qty), 0) AS produced_qty,
                        COALESCE(SUM(fp.accepted_qty), 0) AS accepted_qty,
                        COALESCE(SUM(fp.rejected_qty), 0) AS rejected_qty
                    FROM fact_production fp
                    JOIN dim_shop ds ON fp.shop_id = ds.shop_id
                    WHERE ds.shop_code = 'MACHINE_SHOP' AND fp.year_week = ?
                    """,
                    (week_key,),
                )
                row = cur.fetchone()
                p, a, r = row if row else (0, 0, 0)

                cur.execute(
                    """
                    SELECT COALESCE(SUM(fr.scrap_cost), 0)
                    FROM fact_rejection fr
                    JOIN dim_shop ds ON fr.shop_id = ds.shop_id
                    WHERE ds.shop_code = 'MACHINE_SHOP' AND fr.year_week = ?
                    """,
                    (week_key,),
                )
                sc_row = cur.fetchone()
                sc = sc_row[0] if sc_row else 0.0

                rej_pct = (r / p * 100.0) if p > 0 else 0.0
                kpis = {
                    "produced_qty": p,
                    "accepted_qty": a,
                    "rejected_qty": r,
                    "rejection_pct": rej_pct,
                    "scrap_cost": sc,
                    "status": "critical" if rej_pct >= 2.8 else ("warning" if rej_pct >= 2.0 else "good"),
                }
                observations.append(
                    f"Machine Shop completed {p:,} units with machining rejection rate at {rej_pct:.2f}%."
                )
            except Exception as e:
                logger.warning("[scheduler] Failed to query Machine Shop email KPIs: %s", e)
            finally:
                conn.close()

        attachments = [p for p in [excel_path, pdf_path] if p and Path(p).exists()]
        mail_sent = mailer.send_report(
            report_type="WEEKLY_MACHINE_SHOP",
            period_key=week_key,
            kpis=kpis,
            observations=observations,
            attachments=attachments,
        )

        duration_ms = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
        if run_id:
            update_report_run(
                run_id=run_id,
                status="SUCCESS",
                excel_path=str(excel_path) if excel_path else None,
                pdf_path=str(pdf_path) if pdf_path else None,
                total_produced=kpis.get("produced_qty"),
                total_rejected=kpis.get("rejected_qty"),
                rejection_pct=kpis.get("rejection_pct"),
                run_duration_ms=duration_ms,
            )

        logger.info("[scheduler] Weekly Machine Shop pipeline completed successfully.")
        return {
            "status": "SUCCESS",
            "period": week_key,
            "excel_path": str(excel_path),
            "pdf_path": str(pdf_path),
            "mail_sent": mail_sent,
            "kpis": kpis,
        }

    except Exception as exc:
        err_msg = str(exc)
        tb = traceback.format_exc()
        logger.error("[scheduler] Weekly Machine Shop pipeline failed: %s\n%s", err_msg, tb)
        if run_id:
            update_report_run(run_id=run_id, status="FAILED", error_message=err_msg)
        mailer.send_failure_alert("Weekly Machine Shop Pipeline", week_key, err_msg, tb)
        raise


def run_weekly_reports_job(week_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience wrapper to run both weekly Foundry and Machine Shop reports.
    """
    week_key = week_key or get_default_week_key()
    mailer = ReportMailer()
    f_res = run_weekly_foundry_pipeline(week_key=week_key, mailer=mailer)
    m_res = run_weekly_machine_shop_pipeline(week_key=week_key, mailer=mailer)
    return {
        "week_key": week_key,
        "foundry": f_res,
        "machine_shop": m_res,
    }


def run_monthly_reports_job(month_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute full pipeline for Monthly Rejection & Quality Cost analysis:
    extract -> transform & load -> Excel -> PDF -> email delivery.
    """
    month_key = month_key or get_default_month_key()
    mailer = ReportMailer()
    run_id: Optional[int] = None
    start_time = datetime.datetime.now()

    logger.info("[scheduler] Starting Monthly Rejection pipeline for %s", month_key)
    try:
        run_id = log_report_run(
            report_type="MONTHLY_REJECTION_PIPELINE",
            period_key=month_key,
            generated_by="scheduler",
        )

        run_extraction(month=month_key)
        load_summary = load_pipeline(month=month_key)

        excel_builder = ExcelReportBuilder()
        excel_path = excel_builder.build_monthly_rejection(month_key=month_key)

        pdf_builder = PDFReportBuilder()
        pdf_path = pdf_builder.build_monthly_rejection_pdf(month_key=month_key)

        kpis = {}
        observations = []
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT 
                        COALESCE(SUM(fp.produced_qty), 0) AS produced_qty,
                        COALESCE(SUM(fp.accepted_qty), 0) AS accepted_qty,
                        COALESCE(SUM(fp.rejected_qty), 0) AS rejected_qty
                    FROM fact_production fp
                    WHERE fp.year_month = ?
                    """,
                    (month_key,),
                )
                row = cur.fetchone()
                p, a, r = row if row else (0, 0, 0)

                cur.execute(
                    """
                    SELECT COALESCE(SUM(fr.scrap_cost), 0)
                    FROM fact_rejection fr
                    WHERE fr.year_month = ?
                    """,
                    (month_key,),
                )
                sc_row = cur.fetchone()
                sc = sc_row[0] if sc_row else 0.0

                rej_pct = (r / p * 100.0) if p > 0 else 0.0
                kpis = {
                    "produced_qty": p,
                    "accepted_qty": a,
                    "rejected_qty": r,
                    "rejection_pct": rej_pct,
                    "scrap_cost": sc,
                    "status": "critical" if rej_pct >= 3.5 else ("warning" if rej_pct >= 2.5 else "good"),
                }
                observations.append(
                    f"Total monthly plant volume reached {p:,} units with overall rejection at {rej_pct:.2f}%."
                )
            except Exception as e:
                logger.warning("[scheduler] Failed to query Monthly email KPIs: %s", e)
            finally:
                conn.close()

        attachments = [p for p in [excel_path, pdf_path] if p and Path(p).exists()]
        mail_sent = mailer.send_report(
            report_type="MONTHLY_REJECTION",
            period_key=month_key,
            kpis=kpis,
            observations=observations,
            attachments=attachments,
        )

        duration_ms = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
        if run_id:
            update_report_run(
                run_id=run_id,
                status="SUCCESS",
                excel_path=str(excel_path) if excel_path else None,
                pdf_path=str(pdf_path) if pdf_path else None,
                total_produced=kpis.get("produced_qty"),
                total_rejected=kpis.get("rejected_qty"),
                rejection_pct=kpis.get("rejection_pct"),
                run_duration_ms=duration_ms,
            )

        logger.info("[scheduler] Monthly Rejection pipeline completed successfully.")
        return {
            "status": "SUCCESS",
            "period": month_key,
            "excel_path": str(excel_path),
            "pdf_path": str(pdf_path),
            "mail_sent": mail_sent,
            "kpis": kpis,
        }

    except Exception as exc:
        err_msg = str(exc)
        tb = traceback.format_exc()
        logger.error("[scheduler] Monthly Rejection pipeline failed: %s\n%s", err_msg, tb)
        if run_id:
            update_report_run(run_id=run_id, status="FAILED", error_message=err_msg)
        mailer.send_failure_alert("Monthly Rejection Pipeline", month_key, err_msg, tb)
        raise


# ---------------------------------------------------------------------------
# APScheduler Service Builder
# ---------------------------------------------------------------------------

def create_scheduler(
    blocking: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Build and configure an APScheduler instance with cron jobs defined in settings.yaml.
    """
    if BlockingScheduler is None or CronTrigger is None:
        raise RuntimeError("APScheduler is not installed. Run `pip install apscheduler`.")

    cfg = config or get_config()
    sched_cfg = cfg.get("scheduler", {})
    weekly_cron = sched_cfg.get("weekly_job_cron", "0 7 * * 1")
    monthly_cron = sched_cfg.get("monthly_job_cron", "0 7 1 * *")
    tz_str = sched_cfg.get("timezone", "Asia/Kolkata")

    scheduler_cls = BlockingScheduler if blocking else BackgroundScheduler
    scheduler = scheduler_cls(timezone=tz_str)

    # Weekly trigger
    trigger_weekly = CronTrigger.from_crontab(weekly_cron, timezone=tz_str)
    scheduler.add_job(
        func=run_weekly_reports_job,
        trigger=trigger_weekly,
        id="weekly_mis_reports",
        name="Weekly Foundry and Machine Shop MIS",
        replace_existing=True,
    )
    logger.info(
        "[scheduler] Registered job 'weekly_mis_reports' with cron '%s' (%s)",
        weekly_cron,
        tz_str,
    )

    # Monthly trigger
    trigger_monthly = CronTrigger.from_crontab(monthly_cron, timezone=tz_str)
    scheduler.add_job(
        func=run_monthly_reports_job,
        trigger=trigger_monthly,
        id="monthly_rejection_report",
        name="Monthly Plant Rejection & Cost Report",
        replace_existing=True,
    )
    logger.info(
        "[scheduler] Registered job 'monthly_rejection_report' with cron '%s' (%s)",
        monthly_cron,
        tz_str,
    )

    return scheduler


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sakthi Manufacturing MIS Report Scheduling Engine"
    )
    parser.add_argument(
        "--job",
        choices=["weekly", "monthly", "all"],
        default="all",
        help="Specify which report pipeline to execute",
    )
    parser.add_argument(
        "--week",
        default="2026-W45",
        help="Target ISO week (e.g., '2026-W45')",
    )
    parser.add_argument(
        "--month",
        default="2026-11",
        help="Target month (e.g., '2026-11')",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the pipeline immediately and exit",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run scheduler in background/blocking daemon mode",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.daemon:
        print("Starting Sakthi MIS APScheduler service daemon...")
        sched = create_scheduler(blocking=True)
        try:
            sched.start()
        except (KeyboardInterrupt, SystemExit):
            print("\nShutting down scheduler daemon.")
            sched.shutdown()
        return

    # Direct immediate run
    print(f"\n=================================================================")
    print(f" Executing MIS Scheduled Pipeline (Run-Now Mode)")
    print(f" Job: {args.job} | Week: {args.week} | Month: {args.month}")
    print(f"=================================================================\n")

    if args.job in ("weekly", "all"):
        res = run_weekly_reports_job(week_key=args.week)
        print(f" [WEEKLY FOUNDRY] Excel: {res['foundry']['excel_path']}")
        print(f" [WEEKLY FOUNDRY] PDF:   {res['foundry']['pdf_path']}")
        print(f" [WEEKLY MACHINE] Excel: {res['machine_shop']['excel_path']}")
        print(f" [WEEKLY MACHINE] PDF:   {res['machine_shop']['pdf_path']}")

    if args.job in ("monthly", "all"):
        m_res = run_monthly_reports_job(month_key=args.month)
        print(f" [MONTHLY REJ]   Excel: {m_res['excel_path']}")
        print(f" [MONTHLY REJ]   PDF:   {m_res['pdf_path']}")

    print("\n=================================================================")
    print(" Scheduled Pipeline Execution Completed Successfully.")
    print("=================================================================\n")


if __name__ == "__main__":
    main()
