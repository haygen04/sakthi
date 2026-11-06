# Automated Manufacturing MIS and Rejection Report Generator

> Extract production and quality data from the existing PMS, transform it, and present it as standardized weekly Foundry / Machine Shop MIS reports and monthly rejection reports, with a calm, Dribbble-style dashboard on top.

---

## 1. Project Summary

| Item | Detail |
|---|---|
| Problem | PMS holds production and quality data, but weekly Foundry/Machine Shop reports and monthly rejection reports are compiled by hand |
| Goal | Automate extraction, transformation and presentation into standardized management reports |
| Outputs | Weekly Foundry MIS, weekly Machine Shop MIS, monthly Rejection Report (Excel + PDF), plus a live dashboard |
| Users | Plant managers, quality engineers, production supervisors, admin |

## 2. Tech Stack (all tools used)

| Layer | Tool | Role in project |
|---|---|---|
| Extraction | Python, SQLAlchemy, `pandas.read_sql`, `requests` | Pull data from PMS DB / REST API / CSV exports |
| Transformation | pandas, NumPy | Clean, validate, aggregate, compute KPIs |
| Reporting DB | MySQL | Staging + reporting schema, historical data |
| Excel reports | openpyxl, XlsxWriter | Formatted workbooks with tables and native charts |
| PDF reports | Jinja2, WeasyPrint | Template-based, standardized PDFs |
| Charts | Matplotlib, Plotly | Static charts for PDFs, interactive charts for UI |
| Scheduling | APScheduler (cron / Task Scheduler as fallback) | Weekly and monthly auto-generation |
| Delivery | `smtplib` | Email reports to configured recipients |
| Analytics UI | Streamlit | Interactive exploration page (embedded in main app) |
| Main app | Spring Boot, Spring Security, Spring Data JPA, HTML/CSS/JavaScript | Login, roles, REST APIs, dashboard shell |
| Dev tools | Git, GitHub, Maven, pytest, logging | Version control, build, tests, audit trail |

## 3. Architecture

```
PMS (DB / API / CSV)
        |
        v
[Extract: Python + SQLAlchemy / requests]
        |
        v
[Transform: pandas + NumPy]  -->  validation + logs
        |
        v
[Reporting DB: MySQL]
        |
   +----+-----------------------------+
   |                                  |
   v                                  v
[Report engine]                 [Spring Boot REST API]
openpyxl / XlsxWriter                 |
Jinja2 + WeasyPrint                   v
Matplotlib / Plotly            [Web UI: HTML/CSS/JS + Streamlit]
   |
   v
[APScheduler] --> [smtplib email] --> Managers
```

## 4. Suggested Folder Structure

```
mis-report-generator/
├── etl/
│   ├── extract.py
│   ├── transform.py
│   ├── validate.py
│   └── load.py
├── reports/
│   ├── templates/          # Jinja2 HTML + CSS for PDFs
│   ├── excel_builder.py
│   ├── pdf_builder.py
│   └── charts.py
├── scheduler/
│   └── jobs.py
├── notify/
│   └── mailer.py
├── analytics/
│   └── streamlit_app.py
├── backend/                # Spring Boot project
│   └── src/main/java/...
├── frontend/               # Dashboard HTML/CSS/JS
├── sql/
│   └── schema.sql
├── tests/
├── config/
│   └── settings.example.yaml
├── logs/
├── requirements.txt
└── README.md
```

---

## 5. UI Design System (Dribbble-style, minimal contrast)

The look is soft, airy and quiet: low-contrast surfaces, generous spacing, rounded cards, subtle shadows. Nothing shouts. Color is used sparingly and in muted tones.

### 5.1 Principles

- **Low contrast, high calm:** text is soft slate, never pure black; surfaces are barely different from the background.
- **Cards over borders:** separate content with soft shadows and spacing, not hard lines.
- **One quiet accent:** a single muted lavender-blue; status colors are pastel.
- **Big rounded shapes:** 16-24px radii, pill buttons, circular avatars/icons.
- **Whitespace first:** 24-32px padding in cards, 24px gaps between them.
- **Soft motion:** 150-250ms ease transitions, gentle hover lift.

### 5.2 Color Tokens

```css
:root {
  /* Surfaces */
  --bg:            #F4F5F9;   /* app background */
  --surface:       #FBFBFD;   /* cards */
  --surface-alt:   #EEF0F6;   /* inputs, table stripes, chips */

  /* Text (soft, no pure black) */
  --text:          #3F4558;
  --text-muted:    #8A90A6;
  --text-faint:    #B3B8CA;

  /* Accent (muted lavender-blue) */
  --accent:        #8E9BFF;
  --accent-soft:   #E6E9FF;

  /* Status (pastel) */
  --good:          #A8DCC4;   /* low rejection */
  --good-text:     #4E8F73;
  --warn:          #F6DDA8;   /* watch */
  --warn-text:     #A98433;
  --bad:           #F4B9C0;   /* high rejection */
  --bad-text:      #B25A66;

  /* Shape and depth */
  --radius-lg:     24px;
  --radius-md:     16px;
  --radius-pill:   999px;
  --shadow-soft:   0 8px 30px rgba(120, 128, 160, 0.10);
  --shadow-hover:  0 12px 36px rgba(120, 128, 160, 0.16);
}

/* Optional muted dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --bg:          #1B1D27;
    --surface:     #222532;
    --surface-alt: #2A2D3C;
    --text:        #C9CCDB;
    --text-muted:  #8187A0;
    --text-faint:  #5B607A;
    --accent:      #8E9BFF;
    --accent-soft: #2E3354;
    --shadow-soft: 0 8px 30px rgba(0, 0, 0, 0.25);
  }
}
```

### 5.3 Typography

- Font: **Inter** (fallback: system-ui, sans-serif). Optional pairing: **DM Sans** for headings.
- Scale: 12 / 14 / 16 / 20 / 28 / 40 px. Weights: 400, 500, 600 only.
- Big numbers (KPIs): 40px, weight 600, `--text`. Labels: 12px, `--text-muted`, slight letter-spacing.

### 5.4 Layout

```
+---------+----------------------------------------------+
|         |  Search            Date range     Avatar     |
| Sidebar +----------------------------------------------+
| (icons) |  KPI card   KPI card   KPI card   KPI card   |
|         |  +--------------------+  +-----------------+ |
|  Home   |  | Production trend   |  | Rejection donut | |
|  Weekly |  +--------------------+  +-----------------+ |
|  Monthly|  +--------------------+  +-----------------+ |
|  Explore|  | Defect Pareto      |  | Recent reports  | |
|  Settings  +--------------------+  +-----------------+ |
+---------+----------------------------------------------+
```

- Slim icon sidebar (72px) on soft surface, active item shown as an accent-soft pill.
- 12-column grid, 24px gutters, max content width 1280px.
- Responsive: sidebar collapses to bottom bar on mobile; cards stack in one column.

### 5.5 Components

| Component | Style |
|---|---|
| KPI card | Surface, 24px radius, soft shadow, big number, tiny pastel delta chip (e.g. "-0.4%") |
| Buttons | Pill shaped; primary = accent-soft background with accent text; no heavy fills |
| Inputs / dropdowns | `--surface-alt` background, no border, 16px radius |
| Tables | No grid lines, row hover = `--surface-alt`, status shown as pastel pills |
| Charts | Plotly with transparent background, no gridlines except faint horizontals, pastel palette (accent, mint, peach, rose, sky) |
| Report cards | File-type icon, title, date, download pill button |
| Toasts | Floating soft card, bottom right, fades in/out |
| Empty states | Light illustration + one line of muted text |

### 5.6 Chart Palette (muted)

`#8E9BFF` lavender, `#A8DCC4` mint, `#F6DDA8` butter, `#F4B9C0` rose, `#B7D8F5` sky, `#D4C2F0` lilac

### 5.7 PDF Report Styling

Same tokens in `reports/templates/report.css`: off-white page, soft slate text, rounded KPI tiles, pastel status pills, a thin accent line under the title, page header with plant name and period, footer with generated-on timestamp and page numbers.

---

## 6. Phase-by-Phase Build Plan

### Phase 0: Discovery and Setup

**Goal:** Know exactly what data exists and how to reach it.

- [ ] Identify PMS access method: direct DB, REST API, or CSV/Excel exports
- [ ] List the tables/fields for production, quality, rejection, defect codes, shifts, parts, machines
- [ ] Collect 2-3 existing manual reports (weekly Foundry, weekly Machine Shop, monthly rejection) as layout references
- [ ] Define the KPI list (production qty, rejection qty, rejection %, defect-wise split, shift-wise, part-wise, week-on-week trend)
- [ ] Create the GitHub repo, folder structure, Python virtual env, `requirements.txt`
- [ ] Set up MySQL locally; create `staging` and `reporting` schemas

**Tools:** Git, GitHub, Python, MySQL
**Deliverable:** Data dictionary + KPI definitions + repo skeleton

---

### Phase 1: Data Extraction

**Goal:** Reliably pull raw data from the PMS.

- [ ] Build `etl/extract.py` with SQLAlchemy (DB) and `requests` (API) connectors
- [ ] Add CSV/Excel fallback loader using pandas
- [ ] Parameterize by date range (`week_start`, `week_end`, `month`)
- [ ] Store credentials in `config/settings.yaml` / environment variables (never in code)
- [ ] Add retry logic and logging (`logs/etl.log`)
- [ ] Write raw extracts to the `staging` schema

**Tools:** Python, SQLAlchemy, pandas, requests, MySQL
**Deliverable:** Command like `python -m etl.extract --week 2026-W45` that fills staging tables

---

### Phase 2: Transformation and Validation

**Goal:** Turn raw rows into clean, report-ready data.

- [ ] Clean: trim text, standardize shop/part/defect names, fix date formats, handle nulls
- [ ] Validate: rejected qty <= produced qty, no negative values, no duplicates, mandatory fields present
- [ ] Aggregate: by shop, shift, part, machine, defect type, day, week, month
- [ ] Compute KPIs: rejection %, first-pass yield, week-on-week and month-on-month change, top-N defects, Pareto cumulative %
- [ ] Flag anomalies: rejection % above a configurable threshold
- [ ] Write a validation summary (rows checked, rows rejected, reasons) to the log and DB

**Tools:** pandas, NumPy, Python logging
**Deliverable:** `etl/transform.py` and `etl/validate.py` with unit tests (pytest)

---

### Phase 3: Reporting Database

**Goal:** Store clean, historical data for fast reporting.

- [ ] Design `reporting` schema: `fact_production`, `fact_rejection`, `dim_shop`, `dim_part`, `dim_defect`, `dim_machine`, `dim_date`, `report_runs`
- [ ] Write `sql/schema.sql` with indexes on date, shop, part
- [ ] Build `etl/load.py` (upsert logic so reruns do not duplicate data)
- [ ] Add a `report_runs` table that logs each generated report (type, period, status, file path, time)

**Tools:** MySQL, SQLAlchemy, pandas
**Deliverable:** Populated reporting DB, idempotent load job

---

### Phase 4: Charts

**Goal:** Reusable visuals for both reports and UI.

- [ ] Build `reports/charts.py` with Matplotlib (static, for PDF/Excel images) and Plotly (interactive, for UI)
- [ ] Charts: production vs target (line), rejection % trend (line), rejection by shop (bar), defect Pareto (bar + cumulative line), rejection split (donut)
- [ ] Apply the muted palette and transparent backgrounds from Section 5
- [ ] Keep every chart function pure: `(dataframe) -> figure`

**Tools:** Matplotlib, Plotly, pandas
**Deliverable:** Chart library with a preview script

---

### Phase 5: Excel Report Generator

**Goal:** Formatted weekly and monthly workbooks.

- [ ] Weekly Foundry MIS workbook: summary sheet, daily production, shift-wise, rejection details, charts
- [ ] Weekly Machine Shop MIS workbook: same structure with machine-wise sections
- [ ] Monthly Rejection workbook: month summary, defect-wise, part-wise, shop-wise, Pareto, trend vs previous months
- [ ] Use XlsxWriter for native Excel charts and conditional formatting; use openpyxl where existing templates need editing
- [ ] Apply the soft palette (light header fills, no heavy borders), freeze panes, number formats, auto column widths
- [ ] Save to `output/{type}/{period}/` with a standard naming convention

**Tools:** XlsxWriter, openpyxl, pandas
**Deliverable:** `reports/excel_builder.py` producing all three workbooks

---

### Phase 6: PDF Report Generator

**Goal:** Polished, standardized PDFs.

- [ ] Create Jinja2 templates: `weekly_foundry.html`, `weekly_machine_shop.html`, `monthly_rejection.html`, shared `base.html` + `report.css` (Section 5.7)
- [ ] Embed Matplotlib charts as base64 images
- [ ] Sections: header, KPI tiles, trend charts, tables, anomalies/remarks, footer
- [ ] Render with WeasyPrint; check page breaks and fonts
- [ ] Add auto-generated "Key observations" lines (e.g. "Rejection rose 0.8% vs last week, driven by shrinkage defects")

**Tools:** Jinja2, WeasyPrint, Matplotlib
**Deliverable:** `reports/pdf_builder.py` producing all three PDFs

---

### Phase 7: Scheduling and Email Delivery

**Goal:** Reports generate and send themselves.

- [ ] APScheduler jobs: weekly (e.g. Monday 7:00 AM) and monthly (1st, 7:00 AM)
- [ ] Pipeline per job: extract, transform, validate, load, build Excel + PDF, log, email
- [ ] `notify/mailer.py` with `smtplib`: recipients by report type from config, report files attached, short summary in the body
- [ ] Failure handling: retries, error email to admin, entry in `report_runs`
- [ ] Provide a cron / Windows Task Scheduler fallback script

**Tools:** APScheduler, smtplib, Python logging
**Deliverable:** Fully hands-off weekly and monthly report generation

---

### Phase 8: Backend (Spring Boot)

**Goal:** Secure APIs and role-based access for the UI.

- [ ] Spring Boot project with Spring Data JPA mapped to the reporting DB
- [ ] Spring Security with JWT: roles `ADMIN`, `MANAGER`, `VIEWER`
- [ ] REST endpoints:
  - `GET /api/kpis?shop=&from=&to=`
  - `GET /api/production/trend`
  - `GET /api/rejections/pareto`
  - `GET /api/reports` (list generated reports)
  - `GET /api/reports/{id}/download`
  - `POST /api/reports/generate` (on-demand, ADMIN/MANAGER; triggers the Python pipeline)
- [ ] Validation, global exception handling, CORS config
- [ ] Maven build, basic JUnit tests

**Tools:** Spring Boot, Spring Security, Spring Data JPA, Hibernate, MySQL, Maven
**Deliverable:** Running API with Swagger/OpenAPI docs

---

### Phase 9: Dashboard UI (Dribbble-style)

**Goal:** A calm, modern interface following Section 5.

- [ ] Build `frontend/` with HTML, CSS (tokens from 5.2), JavaScript (fetch API + Plotly)
- [ ] Pages: Login, Home dashboard, Weekly Reports, Monthly Reports, Explorer, Settings
- [ ] Home: 4 KPI cards, production trend, rejection donut, defect Pareto, recent reports list
- [ ] Filters: shop, date range, part; pill-style segmented controls for Weekly / Monthly
- [ ] Report library: cards with download buttons (Excel / PDF) and status pills
- [ ] "Generate now" button with a soft toast on success
- [ ] Responsive layout, subtle hover lift and 200ms transitions, optional muted dark mode
- [ ] Accessibility: keep text contrast readable even though it is soft (minimum ~4.5:1 for body text), visible focus rings

**Tools:** HTML, CSS, JavaScript, Plotly, Spring Boot (serves static files)
**Deliverable:** Working dashboard connected to the API

---

### Phase 10: Interactive Analytics (Streamlit)

**Goal:** A flexible explorer for ad-hoc analysis.

- [ ] `analytics/streamlit_app.py` reading from the reporting DB
- [ ] Controls: shop, part, defect, date range, grouping
- [ ] Plotly charts, a data table, and CSV/Excel download of the filtered view
- [ ] Apply the same palette via `.streamlit/config.toml` and custom CSS
- [ ] Embed in the dashboard "Explorer" page via iframe

**Tools:** Streamlit, Plotly, pandas, SQLAlchemy
**Deliverable:** Explorer page inside the main app

---

### Phase 11: Testing, Hardening, Deployment

**Goal:** Make it dependable.

- [ ] pytest for ETL and report builders; JUnit for APIs; manual UI test checklist
- [ ] Compare generated reports against 2-3 historical manual reports to confirm numbers match
- [ ] Add input sanitization, secret management, least-privilege DB user (read-only for PMS)
- [ ] Logging and monitoring: `logs/` rotation, `report_runs` status view
- [ ] Package: Docker Compose (MySQL + Spring Boot + Python worker + Streamlit) or a simple server setup guide
- [ ] Write README: setup, config, how to run each component, how to add a new report

**Tools:** pytest, JUnit, Docker (optional), Git, GitHub
**Deliverable:** Tested, documented, deployable system

---

## 7. Milestone Summary

| Phase | Focus | Output |
|---|---|---|
| 0 | Discovery and setup | Data dictionary, KPI list, repo |
| 1 | Extraction | PMS data in staging |
| 2 | Transformation | Clean, validated KPIs |
| 3 | Reporting DB | Historical warehouse |
| 4 | Charts | Reusable visuals |
| 5 | Excel reports | 3 workbooks |
| 6 | PDF reports | 3 PDFs |
| 7 | Scheduling and email | Fully automatic delivery |
| 8 | Spring Boot backend | Secure REST APIs |
| 9 | Dashboard UI | Dribbble-style interface |
| 10 | Streamlit explorer | Ad-hoc analytics |
| 11 | Testing and deployment | Production-ready system |

## 8. Key Report Contents (reference)

**Weekly Foundry / Machine Shop MIS**
- Production vs target (daily, shift-wise)
- Rejection qty and % (shop, part, machine, defect)
- Top 5 defects and top 5 rejected parts
- Week-on-week comparison
- Remarks / key observations

**Monthly Rejection Report**
- Month total produced, rejected, rejection %
- Defect-wise Pareto
- Part-wise and shop-wise breakdown
- Trend across last 6 months
- Cost of rejection (if cost data is available in PMS)
- Corrective action notes

## 9. Optional Extras

- Anomaly alerts (email when rejection % crosses a threshold)
- Auto-written commentary summaries
- Report version history and re-generate for past periods
- Role-based email subscriptions
- Dark mode toggle

## 10. Agent Prompt (paste into your coding assistant)

```
You are building the "Automated Manufacturing MIS and Rejection Report Generator".
Follow the phases in this file strictly, one at a time. After each phase:
1) show the files changed, 2) show how to run and test it, 3) wait for my approval.

Stack: Python (SQLAlchemy, pandas, NumPy, requests), MySQL, XlsxWriter + openpyxl,
Jinja2 + WeasyPrint, Matplotlib + Plotly, APScheduler, smtplib, Streamlit,
Spring Boot (Security + JPA + Maven), HTML/CSS/JavaScript, Git/GitHub.

UI rules: Dribbble-style, minimal contrast. Use the exact CSS tokens in Section 5.2,
soft shadows, 16-24px radii, pill buttons, no hard borders, pastel status colors,
Inter font. Keep body text readable (>= 4.5:1).

Rules: never hardcode credentials; make ETL idempotent; log everything;
write tests for ETL and report builders; keep report layouts in templates.
```
