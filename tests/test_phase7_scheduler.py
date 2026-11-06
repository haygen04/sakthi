"""
Phase 7 Tests — Scheduling and Email Delivery
Verifies APScheduler configuration, mail formatting, dry-run delivery,
weekly and monthly pipeline execution, and administrative failure handling.
"""
from pathlib import Path
import pytest

from notify.mailer import ReportMailer
from scheduler.jobs import (
    create_scheduler,
    get_default_month_key,
    get_default_week_key,
    run_weekly_foundry_pipeline,
    run_weekly_machine_shop_pipeline,
    run_weekly_reports_job,
    run_monthly_reports_job,
)


# ---------------------------------------------------------------------------
# Test Suite: Notification Mailer
# ---------------------------------------------------------------------------

class TestReportMailer:
    def test_mailer_initialization(self):
        mailer = ReportMailer()
        assert mailer.sender is not None
        assert "@" in mailer.sender
        assert isinstance(mailer.enabled, bool)

    def test_get_recipients_by_category(self):
        mailer = ReportMailer()
        f_recipients = mailer.get_recipients("foundry_weekly")
        m_recipients = mailer.get_recipients("machine_shop_weekly")
        mon_recipients = mailer.get_recipients("monthly_rejection")
        admin_recipients = mailer.get_recipients("admin_alerts")

        assert len(f_recipients) > 0, "No foundry_weekly recipients configured"
        assert len(m_recipients) > 0, "No machine_shop_weekly recipients configured"
        assert len(mon_recipients) > 0, "No monthly_rejection recipients configured"
        assert len(admin_recipients) > 0, "No admin_alerts recipients configured"
        assert any("foundry" in r.lower() for r in f_recipients)

    def test_build_report_email_html(self):
        mailer = ReportMailer()
        kpis = {
            "produced_qty": 7850,
            "rejected_qty": 220,
            "rejection_pct": 2.80,
            "scrap_cost": 45000.0,
            "status": "warning",
        }
        observations = ["High rejection observed on Line 2."]
        attachments = [Path("sample_data/pms_exports/pms_production_sample.csv")]

        html = mailer.build_report_email_html(
            report_title="Weekly Foundry MIS Report",
            period_key="2026-W45",
            kpis=kpis,
            observations=observations,
            attachments=attachments,
        )

        assert "Weekly Foundry MIS Report" in html
        assert "2026-W45" in html
        assert "7,850" in html
        assert "2.80%" in html
        assert "WARNING" in html
        assert "High rejection observed" in html
        assert "pms_production_sample.csv" in html

    def test_build_failure_alert_html(self):
        mailer = ReportMailer()
        html = mailer.build_failure_alert_html(
            job_name="Weekly Test Job",
            period_key="2026-W45",
            error_message="Simulated connection timeout to PMS database",
            traceback_str="Traceback (most recent call last):\n  File 'test.py', line 10",
        )
        assert "Weekly Test Job" in html
        assert "Simulated connection timeout" in html
        assert "Traceback" in html
        assert "CRITICAL PIPELINE INCIDENT" in html

    def test_dry_run_send_email(self):
        mailer = ReportMailer()
        # In testing default config, notify.enabled = False (dry run mode)
        assert mailer.enabled is False

        sent = mailer.send_email(
            recipients=["test.recipient@sakthi.com"],
            subject="Test Dry Run Email",
            html_body="<p>Test Content</p>",
            attachments=[Path("config/settings.yaml")],
        )

        assert sent is True
        assert len(mailer.sent_messages) == 1
        msg = mailer.sent_messages[0]
        assert msg["to"] == ["test.recipient@sakthi.com"]
        assert msg["subject"] == "Test Dry Run Email"
        assert any("settings.yaml" in a for a in msg["attachments"])

    def test_send_report_convenience(self):
        mailer = ReportMailer()
        kpis = {"produced_qty": 5000, "rejected_qty": 100, "rejection_pct": 2.0}
        success = mailer.send_report(
            report_type="WEEKLY_FOUNDRY",
            period_key="2026-W45",
            kpis=kpis,
        )
        assert success is True
        assert len(mailer.sent_messages) > 0
        last = mailer.sent_messages[-1]
        assert "Foundry" in last["subject"]

    def test_send_failure_alert_convenience(self):
        mailer = ReportMailer()
        success = mailer.send_failure_alert(
            job_name="Foundry ETL",
            period_key="2026-W45",
            error_message="Test DB Error",
        )
        assert success is True
        last = mailer.sent_messages[-1]
        assert "ALERT" in last["subject"]


# ---------------------------------------------------------------------------
# Test Suite: Scheduler Configuration & Cron
# ---------------------------------------------------------------------------

class TestSchedulerConfig:
    def test_period_key_helpers(self):
        w = get_default_week_key()
        m = get_default_month_key()
        assert "-W" in w, f"Expected YYYY-Www, got {w}"
        assert "-" in m and len(m) == 7, f"Expected YYYY-MM, got {m}"

    def test_scheduler_job_registration(self):
        scheduler = create_scheduler(blocking=False)
        jobs = scheduler.get_jobs()
        job_ids = [j.id for j in jobs]

        assert "weekly_mis_reports" in job_ids, "Missing weekly_mis_reports job"
        assert "monthly_rejection_report" in job_ids, "Missing monthly_rejection_report job"


# ---------------------------------------------------------------------------
# Test Suite: End-to-End Pipeline Execution
# ---------------------------------------------------------------------------

class TestSchedulerPipelines:
    def test_run_weekly_foundry_pipeline(self):
        res = run_weekly_foundry_pipeline(week_key="2026-W45")
        assert res["status"] == "SUCCESS"
        assert Path(res["excel_path"]).exists()
        assert Path(res["pdf_path"]).exists()
        assert res["mail_sent"] is True
        assert res["kpis"]["produced_qty"] > 0

    def test_run_weekly_machine_shop_pipeline(self):
        res = run_weekly_machine_shop_pipeline(week_key="2026-W45")
        assert res["status"] == "SUCCESS"
        assert Path(res["excel_path"]).exists()
        assert Path(res["pdf_path"]).exists()
        assert res["mail_sent"] is True

    def test_run_monthly_reports_job(self):
        res = run_monthly_reports_job(month_key="2026-11")
        assert res["status"] == "SUCCESS"
        assert Path(res["excel_path"]).exists()
        assert Path(res["pdf_path"]).exists()
        assert res["mail_sent"] is True

