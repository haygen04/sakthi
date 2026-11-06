"""Unit and format test suite for Phase 5: Excel Report Generator."""

import pytest
from pathlib import Path
import openpyxl

from reports.excel_builder import ExcelReportBuilder

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def builder():
    return ExcelReportBuilder()


def test_weekly_foundry_excel(builder, tmp_path):
    """Verify Weekly Foundry MIS Excel workbook structure, sheets, and cell values."""
    out_file = tmp_path / "test_foundry.xlsx"
    path = builder.build_weekly_foundry("2026-W45", out_file)
    assert path.exists()
    assert path.stat().st_size > 20000

    # Inspect with openpyxl
    wb = openpyxl.load_workbook(str(path), data_only=False)
    expected_sheets = ["Foundry Summary & Daily", "Shift Performance", "Defect Pareto", "Part Analysis"]
    for s in expected_sheets:
        assert s in wb.sheetnames

    ws = wb["Foundry Summary & Daily"]
    # Check title
    assert "FOUNDRY DIVISION" in str(ws["A1"].value)
    # Check headers at row 8 (1-indexed)
    assert ws["A8"].value == "Date"
    assert ws["C8"].value == "Target Pcs"
    assert ws["D8"].value == "Poured Pcs"
    # Check formula in total row
    assert "=SUM(" in str(ws.cell(row=ws.max_row, column=3).value)

    wb.close()


def test_weekly_machine_shop_excel(builder, tmp_path):
    """Verify Weekly Machine Shop MIS workbook sheets and contents."""
    out_file = tmp_path / "test_machine_shop.xlsx"
    path = builder.build_weekly_machine_shop("2026-W45", out_file)
    assert path.exists()
    assert path.stat().st_size > 20000

    wb = openpyxl.load_workbook(str(path), data_only=False)
    assert "Machining Summary & Daily" in wb.sheetnames
    assert "Cell Performance" in wb.sheetnames
    assert "Machining Defects" in wb.sheetnames

    ws = wb["Machining Summary & Daily"]
    assert "PRECISION MACHINING" in str(ws["A1"].value)
    wb.close()


def test_monthly_rejection_excel(builder, tmp_path):
    """Verify Monthly Rejection & Cost-of-Quality workbook sheets and contents."""
    out_file = tmp_path / "test_monthly.xlsx"
    path = builder.build_monthly_rejection("2026-11", out_file)
    assert path.exists()
    assert path.stat().st_size > 15000

    wb = openpyxl.load_workbook(str(path), data_only=False)
    assert "Monthly Executive Summary" in wb.sheetnames
    assert "Plant Defect Pareto" in wb.sheetnames

    ws = wb["Monthly Executive Summary"]
    assert "QUALITY ASSURANCE COMMAND" in str(ws["A1"].value)
    wb.close()

