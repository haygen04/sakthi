# Automated Manufacturing MIS and Rejection Report Generator

An automated data pipeline and reporting system that extracts daily shop-floor production and quality rejection data from the existing PMS (Production Management System), transforms and validates it into clean KPI metrics, and generates standardized weekly Foundry and Machine Shop MIS reports and monthly rejection reports (Excel + PDF), topped with a calm, Dribbble-style executive dashboard.

---

## 1. Project Overview & Deliverables

- **Target Manufacturing Divisions:**
  - **Foundry Division:** Disamatic high-pressure molding lines, auto-pouring, grey iron & ductile iron castings (brake discs, drums, knuckles, flywheels).
  - **Machine Shop Division:** CNC turning, high-speed VMC milling, dynamic balancing, and precision finishing lines.
- **Automated Outputs:**
  1. **Weekly Foundry MIS Report** (Excel + PDF)
  2. **Weekly Machine Shop MIS Report** (Excel + PDF)
  3. **Monthly Rejection & Cost-of-Quality Report** (Excel + PDF)
  4. **Executive Dashboard UI** (Minimal-contrast Dribbble aesthetic with soft surfaces and pastel status chips)
  5. **Interactive Streamlit Explorer** (Deep-dive slicing and Pareto ad-hoc analysis)

---

## 2. Architecture & Technology Stack

```
PMS (DB / REST API / CSV Exports)
         │
         ▼
[Extract: Python + SQLAlchemy / requests]
         │
         ▼
[Transform: pandas + NumPy] ──> Validation + Audit Logs
         │
         ▼
[Reporting Warehouse: MySQL 8.0 / SQLite]
         │
    ┌────┴─────────────────────────────┐
    │                                  │
    ▼                                  ▼
[Report Engine]                [Spring Boot REST API]
openpyxl / XlsxWriter                  │
Jinja2 + HTML / PDF                    ▼
Matplotlib / Plotly             [Web UI: HTML/CSS/JS + Streamlit]
    │
    ▼
[APScheduler] ──> [smtplib email] ──> Plant Leadership
```

---

## 3. Directory Layout

```
.
├── etl/
│   ├── __init__.py
│   ├── db_init.py             # Schema initialization & table verification
│   ├── extract.py             # Multi-source extraction (DB, API, CSV)
│   ├── transform.py           # Cleaning, validation, KPI calculations
│   ├── validate.py            # Integrity rules & anomaly flags
│   └── load.py                # Idempotent warehouse upsert
├── reports/
│   ├── __init__.py
│   ├── templates/             # Jinja2 HTML templates + CSS for PDFs
│   ├── excel_builder.py       # Standardized workbooks with XlsxWriter/openpyxl
│   ├── pdf_builder.py         # Standardized executive PDFs
│   └── charts.py              # Pure Matplotlib and Plotly visualizers
├── scheduler/
│   ├── __init__.py
│   └── jobs.py                # APScheduler cron trigger pipelines
├── notify/
│   ├── __init__.py
│   └── mailer.py              # Email dispatch with attachments
├── analytics/
│   └── streamlit_app.py       # Interactive slice-and-dice explorer
├── backend/                   # Spring Boot application
├── frontend/                  # Dashboard shell HTML/CSS/JS
├── sql/
│   ├── schema.sql             # Staging, dimensions, facts, and audit tables
│   └── seed_pms_data.sql      # Seed dimensions and simulated PMS records
├── sample_data/
│   ├── pms_exports/           # Realistic PMS CSV extract samples
│   └── references/            # Layout references for all 3 manual reports
├── config/
│   ├── loader.py              # Dynamic YAML & environment variable loader
│   ├── settings.example.yaml  # Reference configuration without secrets
│   └── settings.yaml          # Active local configuration
├── tests/
│   ├── __init__.py
│   └── test_phase0_setup.py   # Discovery & setup validation suite
├── requirements.txt
└── README.md
```

---

## 4. Phase-by-Phase Roadmap

- [x] **Phase 0: Discovery and Setup** (Data dictionary, KPI formulas, layout references, repo skeleton, schema, test suite)
- [x] **Phase 1: Data Extraction** (SQLAlchemy DB, REST API, CSV fallback loader, staging pipeline)
- [x] **Phase 2: Transformation and Validation** (Data cleaning, validation rules, KPI compute, anomaly flags)
- [x] **Phase 3: Reporting Database & Load** (Idempotent warehouse loader, `report_runs` registry)
- [x] **Phase 4: Charts** (Reusable visuals for reports and UI)
- [x] **Phase 5: Excel Report Generator** (Weekly Foundry, Weekly Machine Shop, Monthly Rejection workbooks)
- [x] **Phase 6: PDF Report Generator** (Standardized Jinja2 + CSS + embedded charts)
- [x] **Phase 7: Scheduling & Email Delivery** (APScheduler Monday/1st-of-month jobs + smtplib + Windows Task Scheduler runner)
- [ ] **Phase 8: Spring Boot Backend** (REST endpoints, Spring Security, JWT, on-demand trigger)
- [ ] **Phase 9: Dribbble-Style Dashboard UI** (Calm aesthetic, soft shadows, pill controls, cards)
- [ ] **Phase 10: Interactive Streamlit Analytics** (Explorer page embedded in dashboard)
- [ ] **Phase 11: Testing, Hardening & Deployment** (End-to-end regression tests, Docker Compose)

---

## 5. Running Phase 0 Verification

Run database initialization and schema verification:
```powershell
python -m etl.db_init
```

Run test suite:
```powershell
python -m pytest tests/ -v
```

## 6. Running Phase 1 Data Extraction

Extract by ISO week (e.g., Week 45):
```powershell
python -m etl.extract --week 2026-W45
```

Extract by month:
```powershell
python -m etl.extract --month 2026-11
```

Extract by explicit date range and mode:
```powershell
python -m etl.extract --start-date 2026-11-02 --end-date 2026-11-08 --mode csv
```

## 7. Running Phase 2 Transformation & Validation

Execute full transformation & validation test suite:
```powershell
python -m pytest tests/test_phase2_transform.py -v
```

## 8. Running Phase 3 Warehouse Load (Idempotent Upsert)

Load transformed facts into warehouse for an ISO week:
```powershell
python -m etl.load --week 2026-W45
```

Execute Phase 3 warehouse tests:
```powershell
python -m pytest tests/test_phase3_load.py -v
```

## 9. Running Phase 4 Charts (Static PNGs & Interactive Widgets)

Generate and preview all core manufacturing charts:
```powershell
python -m reports.preview_charts
```
Outputs high-res PNG images and standalone interactive Plotly HTML widgets to `output/charts_preview/`.

Execute Phase 4 chart tests:
```powershell
python -m pytest tests/test_phase4_charts.py -v
```

## 10. Running Phase 5 Excel Report Generator

Generate all three standardized MIS workbooks (Weekly Foundry, Weekly Machine Shop, Monthly Rejection):
```powershell
python -m reports.excel_builder --type all --week 2026-W45 --month 2026-11
```

Generate single report:
```powershell
python -m reports.excel_builder --type foundry --week 2026-W45
python -m reports.excel_builder --type machine_shop --week 2026-W45
python -m reports.excel_builder --type monthly --month 2026-11
```

Execute Phase 5 Excel tests:
```powershell
python -m pytest tests/test_phase5_excel.py -v
```

## 11. Running Phase 6 PDF Report Generator

Generate all three standardized MIS PDF documents (Weekly Foundry, Weekly Machine Shop, Monthly Rejection):
```powershell
python -m reports.pdf_builder --type all --week 2026-W45 --month 2026-11
```

Generate single report PDF:
```powershell
python -m reports.pdf_builder --type foundry --week 2026-W45
python -m reports.pdf_builder --type machine_shop --week 2026-W45
python -m reports.pdf_builder --type monthly --month 2026-11
```

Execute Phase 6 PDF tests:
```powershell
python -m pytest tests/test_phase6_pdf.py -v
```

## 12. Running Phase 7 Scheduling & Email Delivery

Trigger immediate end-to-end report pipeline and dispatch email (dry-run or live):
```powershell
python -m scheduler.jobs --job all --week 2026-W45 --month 2026-11
```

Start the APScheduler background daemon:
```powershell
python -m scheduler.jobs --daemon
```

Execute via Windows Task Scheduler / batch fallback runner:
```powershell
.\scripts\run_scheduled_job.bat weekly 2026-W45
.\scripts\run_scheduled_job.ps1 -Job monthly -Period 2026-11
```

Execute Phase 7 Scheduler & Mailer tests:
```powershell
python -m pytest tests/test_phase7_scheduler.py -v
```

