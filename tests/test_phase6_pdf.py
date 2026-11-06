"""
Phase 6 Tests — PDF Report Generator
Verifies PDF files are created with correct size, HTML previews contain
expected section titles, and report_runs audit entries are logged.
"""
import os
import pytest
from pathlib import Path

WEEK_KEY = "2026-W45"
MONTH_KEY = "2026-11"
OUTPUT_ROOT = Path("output")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pdf_path(report_type: str, period: str, stem: str) -> Path:
    return OUTPUT_ROOT / report_type / period / f"{stem}.pdf"


def _html_path(report_type: str, period: str, stem: str) -> Path:
    return OUTPUT_ROOT / report_type / period / f"{stem}.html"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWeeklyFoundryPDF:
    PDF = _pdf_path("weekly_foundry", WEEK_KEY, f"weekly_foundry_{WEEK_KEY}")
    HTML = _html_path("weekly_foundry", WEEK_KEY, f"weekly_foundry_{WEEK_KEY}")

    def test_pdf_exists_and_non_trivial(self):
        assert self.PDF.exists(), f"PDF not found: {self.PDF}"
        size = self.PDF.stat().st_size
        assert size > 5_000, f"PDF too small ({size} bytes) — likely empty/broken"

    def test_html_exists(self):
        assert self.HTML.exists(), f"HTML preview not found: {self.HTML}"

    def test_html_contains_section_titles(self):
        content = self.HTML.read_text(encoding="utf-8", errors="replace")
        assert "Daily Production" in content, "Missing section 1 title"
        assert "Shift" in content, "Missing shift section"
        assert "Defect Pareto" in content or "Defect" in content, "Missing defect section"
        assert "Foundry" in content, "Missing foundry header"

    def test_html_no_rupee_glyph(self):
        """Ensure ₹ glyph is not in HTML (should use INR prefix instead)."""
        content = self.HTML.read_text(encoding="utf-8", errors="replace")
        assert "₹" not in content, "₹ glyph found in HTML — xhtml2pdf will render as blank box"

    def test_pdf_is_pdf_header(self):
        """Verify PDF starts with %PDF magic bytes."""
        with open(self.PDF, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF", f"File does not start with %PDF header: {header!r}"


class TestWeeklyMachineShopPDF:
    PDF = _pdf_path("weekly_machine_shop", WEEK_KEY, f"weekly_machine_shop_{WEEK_KEY}")
    HTML = _html_path("weekly_machine_shop", WEEK_KEY, f"weekly_machine_shop_{WEEK_KEY}")

    def test_pdf_exists_and_non_trivial(self):
        assert self.PDF.exists(), f"PDF not found: {self.PDF}"
        size = self.PDF.stat().st_size
        assert size > 5_000, f"PDF too small ({size} bytes)"

    def test_html_exists(self):
        assert self.HTML.exists(), f"HTML preview not found: {self.HTML}"

    def test_html_contains_section_titles(self):
        content = self.HTML.read_text(encoding="utf-8", errors="replace")
        assert "Machining" in content or "Machine" in content, "Missing machining header"
        assert "Defect" in content, "Missing defect section"

    def test_html_no_rupee_glyph(self):
        content = self.HTML.read_text(encoding="utf-8", errors="replace")
        assert "₹" not in content, "₹ glyph found in HTML"

    def test_pdf_is_pdf_header(self):
        with open(self.PDF, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF", f"File does not start with %PDF: {header!r}"


class TestMonthlyRejectionPDF:
    PDF = _pdf_path("monthly_rejection", MONTH_KEY, f"monthly_rejection_{MONTH_KEY}")
    HTML = _html_path("monthly_rejection", MONTH_KEY, f"monthly_rejection_{MONTH_KEY}")

    def test_pdf_exists_and_non_trivial(self):
        assert self.PDF.exists(), f"PDF not found: {self.PDF}"
        size = self.PDF.stat().st_size
        assert size > 5_000, f"PDF too small ({size} bytes)"

    def test_html_exists(self):
        assert self.HTML.exists(), f"HTML preview not found: {self.HTML}"

    def test_html_contains_section_titles(self):
        content = self.HTML.read_text(encoding="utf-8", errors="replace")
        assert "Division Quality" in content or "Rejection" in content, "Missing monthly header"
        assert "Pareto" in content or "Defect" in content, "Missing pareto section"

    def test_html_no_rupee_glyph(self):
        content = self.HTML.read_text(encoding="utf-8", errors="replace")
        assert "₹" not in content, "₹ glyph found in HTML"

    def test_pdf_is_pdf_header(self):
        with open(self.PDF, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF", f"File does not start with %PDF: {header!r}"


class TestReportRunsAudit:
    def test_report_runs_logged(self):
        """Verify report_runs table contains PDF run entries."""
        import sqlite3
        conn = sqlite3.connect("mis_reporting.db")
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM report_runs WHERE report_type IN "
            "('WEEKLY_FOUNDRY_PDF','WEEKLY_MACHINE_SHOP_PDF','MONTHLY_REJECTION_PDF')"
        )
        count = cur.fetchone()[0]
        conn.close()
        assert count >= 3, f"Expected >=3 PDF report_runs entries, got {count}"

    def test_report_runs_has_pdf_path(self):
        """PDF runs should record the pdf_path."""
        import sqlite3
        conn = sqlite3.connect("mis_reporting.db")
        cur = conn.cursor()
        cur.execute(
            "SELECT pdf_path FROM report_runs WHERE report_type LIKE '%PDF%' "
            "ORDER BY run_id DESC LIMIT 3"
        )
        rows = cur.fetchall()
        conn.close()
        assert len(rows) > 0, "No PDF report_run rows found"
        for (path,) in rows:
            if path:
                assert ".pdf" in path.lower(), f"pdf_path does not look like PDF: {path}"

