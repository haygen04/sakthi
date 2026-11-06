"""
Sakthi Manufacturing MIS Report Generator — Phase 7: Notification Mailer
Handles formatting and dispatch of executive MIS reports and operational alerts
via SMTP, supporting HTML email bodies, Excel/PDF attachments, and dry-run testing.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import smtplib
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from config.loader import get_config

logger = logging.getLogger("notify.mailer")


class ReportMailer:
    """
    Automated mailer for distributing weekly Foundry / Machine Shop MIS reports,
    monthly rejection reviews, and critical pipeline alert notifications.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_config()
        self.notify_cfg = self.config.get("notify", {})
        self.smtp_cfg = self.notify_cfg.get("smtp", {})
        self.recipients_cfg = self.notify_cfg.get("recipients", {})
        
        # Test audit log of simulated transmissions when notify.enabled = False
        self.sent_messages: List[Dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        """Check if notification delivery is actively enabled."""
        return bool(self.notify_cfg.get("enabled", False))

    @property
    def sender(self) -> str:
        """Configured sender display name and address."""
        return self.smtp_cfg.get("sender", "Sakthi MIS Automation <reports@sakthi.com>")

    def get_recipients(self, category: str) -> List[str]:
        """Fetch recipient list for a given report category or audience."""
        recipients = self.recipients_cfg.get(category, [])
        if isinstance(recipients, str):
            return [recipients]
        return list(recipients)

    def build_report_email_html(
        self,
        report_title: str,
        period_key: str,
        kpis: Optional[Dict[str, Any]] = None,
        observations: Optional[List[str]] = None,
        attachments: Optional[List[Union[str, Path]]] = None,
    ) -> str:
        """
        Render a clean, low-contrast HTML email body adhering to the Dribbble aesthetic.
        """
        kpis = kpis or {}
        observations = observations or []
        attachments = attachments or []

        status = kpis.get("status", "good").lower()
        if status == "critical":
            badge_bg = "#F4B9C0"
            badge_fg = "#B25A66"
            badge_text = "CRITICAL"
        elif status == "warning" or status == "warn":
            badge_bg = "#F6DDA8"
            badge_fg = "#A98433"
            badge_text = "WARNING"
        else:
            badge_bg = "#A8DCC4"
            badge_fg = "#4E8F73"
            badge_text = "NORMAL"

        produced = kpis.get("produced_qty", 0)
        rejected = kpis.get("rejected_qty", 0)
        rej_pct = kpis.get("rejection_pct", 0.0)
        scrap_cost = kpis.get("scrap_cost", 0.0)

        obs_html = ""
        if observations:
            items = "".join(f"<li style='margin-bottom: 6px; color: #3F4558;'>{obs}</li>" for obs in observations)
            obs_html = f"""
            <div style="background-color: #EEF0F6; border-radius: 12px; padding: 16px 20px; margin: 20px 0;">
                <h4 style="margin: 0 0 10px 0; color: #3F4558; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Executive Observations</h4>
                <ul style="margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.5;">
                    {items}
                </ul>
            </div>
            """

        att_html = ""
        if attachments:
            items = "".join(
                f"<li style='margin-bottom: 4px; color: #8A90A6; font-size: 12px;'>📁 {Path(a).name}</li>"
                for a in attachments
            )
            att_html = f"""
            <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #EEF0F6;">
                <div style="font-size: 12px; font-weight: 600; color: #8A90A6; margin-bottom: 8px;">ATTACHMENTS ({len(attachments)}):</div>
                <ul style="margin: 0; padding-left: 16px; list-style-type: none;">
                    {items}
                </ul>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{report_title} - {period_key}</title>
        </head>
        <body style="margin: 0; padding: 24px; background-color: #F4F5F9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #3F4558;">
            <div style="max-width: 650px; margin: 0 auto; background-color: #FBFBFD; border-radius: 16px; padding: 32px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);">
                
                <!-- Header -->
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #EEF0F6; padding-bottom: 16px; margin-bottom: 24px;">
                    <div>
                        <div style="font-size: 11px; font-weight: 700; color: #8E9BFF; text-transform: uppercase; letter-spacing: 1px;">Sakthi Automotive Group</div>
                        <h2 style="margin: 4px 0 0 0; font-size: 20px; font-weight: 700; color: #3F4558;">{report_title}</h2>
                        <div style="font-size: 13px; color: #8A90A6; margin-top: 2px;">Period: <strong>{period_key}</strong></div>
                    </div>
                    <div style="text-align: right;">
                        <span style="display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; background-color: {badge_bg}; color: {badge_fg};">
                            {badge_text}
                        </span>
                    </div>
                </div>

                <!-- KPI Tiles Grid -->
                <table style="width: 100%; border-spacing: 12px; margin: 0 -12px;">
                    <tr>
                        <td style="background-color: #EEF0F6; border-radius: 12px; padding: 16px; text-align: center; width: 25%;">
                            <div style="font-size: 11px; font-weight: 600; color: #8A90A6; text-transform: uppercase;">Production</div>
                            <div style="font-size: 20px; font-weight: 700; color: #3F4558; margin-top: 6px;">{produced:,.0f}</div>
                            <div style="font-size: 11px; color: #8A90A6; margin-top: 2px;">Pieces</div>
                        </td>
                        <td style="background-color: #EEF0F6; border-radius: 12px; padding: 16px; text-align: center; width: 25%;">
                            <div style="font-size: 11px; font-weight: 600; color: #8A90A6; text-transform: uppercase;">Rejections</div>
                            <div style="font-size: 20px; font-weight: 700; color: #B25A66; margin-top: 6px;">{rejected:,.0f}</div>
                            <div style="font-size: 11px; color: #8A90A6; margin-top: 2px;">Defects</div>
                        </td>
                        <td style="background-color: #EEF0F6; border-radius: 12px; padding: 16px; text-align: center; width: 25%;">
                            <div style="font-size: 11px; font-weight: 600; color: #8A90A6; text-transform: uppercase;">Rejection %</div>
                            <div style="font-size: 20px; font-weight: 700; color: {badge_fg}; margin-top: 6px;">{rej_pct:.2f}%</div>
                            <div style="font-size: 11px; color: #8A90A6; margin-top: 2px;">Actual</div>
                        </td>
                        <td style="background-color: #EEF0F6; border-radius: 12px; padding: 16px; text-align: center; width: 25%;">
                            <div style="font-size: 11px; font-weight: 600; color: #8A90A6; text-transform: uppercase;">Scrap Loss</div>
                            <div style="font-size: 18px; font-weight: 700; color: #3F4558; margin-top: 6px;">INR {scrap_cost:,.0f}</div>
                            <div style="font-size: 11px; color: #8A90A6; margin-top: 2px;">Direct Cost</div>
                        </td>
                    </tr>
                </table>

                {obs_html}

                {att_html}

                <!-- Footer -->
                <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #EEF0F6; font-size: 11px; color: #B3B8CA; text-align: center;">
                    Generated automatically by Sakthi Manufacturing MIS &bull; Confidential &bull; For Internal Management Use Only
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def build_failure_alert_html(
        self,
        job_name: str,
        period_key: str,
        error_message: str,
        traceback_str: str = "",
    ) -> str:
        """
        Render an operational failure alert email for technical administration.
        """
        tb_block = ""
        if traceback_str:
            tb_block = f"""
            <div style="background-color: #2D3139; color: #E6E9FF; border-radius: 8px; padding: 14px; font-family: monospace; font-size: 11px; white-space: pre-wrap; overflow-x: auto; margin-top: 14px;">
{traceback_str}
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>MIS Pipeline Alert: {job_name}</title>
        </head>
        <body style="margin: 0; padding: 24px; background-color: #F4F5F9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #3F4558;">
            <div style="max-width: 650px; margin: 0 auto; background-color: #FBFBFD; border-radius: 16px; padding: 32px; border-left: 6px solid #F4B9C0;">
                <div style="font-size: 11px; font-weight: 700; color: #B25A66; text-transform: uppercase; letter-spacing: 1px;">CRITICAL PIPELINE INCIDENT</div>
                <h2 style="margin: 6px 0 12px 0; color: #B25A66; font-size: 18px;">Automated Job Failed: {job_name}</h2>
                <p style="font-size: 13px; line-height: 1.5; color: #3F4558;">
                    The automated MIS extraction and report generation pipeline encountered an unhandled error for period <strong>{period_key}</strong>.
                </p>
                <div style="background-color: #F4B9C0; color: #7B222D; padding: 12px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; margin: 16px 0;">
                    Error: {error_message}
                </div>
                {tb_block}
                <div style="margin-top: 24px; font-size: 12px; color: #8A90A6;">
                    Please check the execution logs at <code>logs/</code> and verify database / PMS connectivity.
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def send_email(
        self,
        recipients: List[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        attachments: Optional[List[Union[str, Path]]] = None,
        raise_on_error: bool = False,
    ) -> bool:
        """
        Dispatch an email with optional attachments to the specified recipients.
        In dry-run mode (enabled=False), logs the dispatch and stores message info.
        """
        if not recipients:
            logger.warning("[notify.mailer] No recipients specified for email '%s'. Skipping.", subject)
            return False

        attachments = attachments or []
        text_body = text_body or "Please view this report in an HTML-capable email client."

        # Create message container
        msg = MIMEMultipart("mixed")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = self.sender
        msg["To"] = ", ".join(recipients)

        # Body alternative
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(text_body, "plain", "utf-8"))
        alt_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt_part)

        # Attach files
        for att in attachments:
            p = Path(att)
            if not p.exists():
                logger.warning("[notify.mailer] Attachment file does not exist: %s", p)
                continue

            ctype, encoding = mimetypes.guess_type(str(p))
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)

            try:
                with open(p, "rb") as fp:
                    part = MIMEBase(maintype, subtype)
                    part.set_payload(fp.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
                msg.attach(part)
            except Exception as e:
                logger.error("[notify.mailer] Failed to read/attach file %s: %s", p, e)

        # Record transmission metadata
        record = {
            "to": recipients,
            "subject": subject,
            "attachments": [str(a) for a in attachments],
            "enabled": self.enabled,
        }
        self.sent_messages.append(record)

        if not self.enabled:
            logger.info(
                "[notify.mailer] Notification DRY-RUN (enabled=False): Sent '%s' to %s with %d attachment(s).",
                subject,
                recipients,
                len(attachments),
            )
            return True

        # Live SMTP delivery
        host = self.smtp_cfg.get("host", "localhost")
        port = int(self.smtp_cfg.get("port", 25))
        use_tls = bool(self.smtp_cfg.get("use_tls", False))
        user = self.smtp_cfg.get("user", "")
        password = self.smtp_cfg.get("password", "")

        try:
            logger.info("[notify.mailer] Connecting to SMTP server %s:%d (TLS=%s)...", host, port, use_tls)
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
            logger.info("[notify.mailer] Email '%s' successfully delivered to %s.", subject, recipients)
            return True
        except Exception as e:
            logger.error("[notify.mailer] SMTP delivery failed for '%s': %s", subject, e)
            if raise_on_error:
                raise
            return False

    def send_report(
        self,
        report_type: str,
        period_key: str,
        kpis: Optional[Dict[str, Any]] = None,
        observations: Optional[List[str]] = None,
        attachments: Optional[List[Union[str, Path]]] = None,
    ) -> bool:
        """
        Convenience method to deliver a weekly or monthly MIS report to its designated audience.
        """
        type_upper = report_type.upper()
        if "FOUNDRY" in type_upper:
            category = "foundry_weekly"
            title = "Foundry Division Weekly MIS Report"
        elif "MACHINE" in type_upper:
            category = "machine_shop_weekly"
            title = "Machine Shop Weekly MIS Report"
        elif "MONTHLY" in type_upper or "REJECTION" in type_upper:
            category = "monthly_rejection"
            title = "Monthly Quality & Rejection Analysis"
        else:
            category = "admin_alerts"
            title = f"MIS Report: {report_type}"

        recipients = self.get_recipients(category)
        if not recipients:
            logger.warning("[notify.mailer] No recipients found for category '%s'", category)
            return False

        subject = f"[Sakthi MIS] {title} - {period_key}"
        html_body = self.build_report_email_html(
            report_title=title,
            period_key=period_key,
            kpis=kpis,
            observations=observations,
            attachments=attachments,
        )

        return self.send_email(
            recipients=recipients,
            subject=subject,
            html_body=html_body,
            attachments=attachments,
        )

    def send_failure_alert(
        self,
        job_name: str,
        period_key: str,
        error_message: str,
        traceback_str: str = "",
    ) -> bool:
        """
        Send an immediate operational failure alert to system administrators.
        """
        recipients = self.get_recipients("admin_alerts")
        if not recipients:
            recipients = ["mis.admin@sakthi.com"]

        subject = f"[ALERT] Sakthi MIS Pipeline Failure: {job_name} ({period_key})"
        html_body = self.build_failure_alert_html(
            job_name=job_name,
            period_key=period_key,
            error_message=error_message,
            traceback_str=traceback_str,
        )

        return self.send_email(
            recipients=recipients,
            subject=subject,
            html_body=html_body,
        )

