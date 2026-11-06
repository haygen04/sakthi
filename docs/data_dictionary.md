# Data Dictionary: Automated Manufacturing MIS & Rejection Report Generator

This document defines the schema, entities, and attributes across all three layers of the reporting architecture:
1. **PMS Source Layer** (Operational Production Management System)
2. **Staging Schema Layer** (`staging_*`)
3. **Reporting Warehouse Layer** (`dim_*`, `fact_*`, `report_runs`)

---

## 1. PMS Source Entities & Field Specification

The PMS captures shop-floor logs across two primary operations: **Foundry** (melting, molding, pouring) and **Machine Shop** (CNC, VMC, turning, grinding, finishing).

### 1.1 `pms_production_logs` (Daily / Shift Production)
Records production output by date, shop, line, part, and shift.

| Field Name | Data Type | Nullable | Primary/Foreign Key | Description | Example Value |
|---|---|---|---|---|---|
| `log_id` | VARCHAR(64) | No | PK | Unique identifier in PMS | `PROD-20261102-001` |
| `production_date` | DATE | No | Index | Date of production shift | `2026-11-02` |
| `shop_code` | VARCHAR(32) | No | FK -> shops | Shop identifier (`FOUNDRY`, `MACHINE_SHOP`) | `FOUNDRY` |
| `shift_code` | VARCHAR(16) | No | FK -> shifts | Shift identifier (`SHIFT_A`, `SHIFT_B`, `SHIFT_C`) | `SHIFT_A` |
| `machine_code` | VARCHAR(32) | No | FK -> machines | Machine / Line identifier | `FND-DISA-01` |
| `part_number` | VARCHAR(64) | No | FK -> parts | Finished / casting part code | `P-BRK-DISC-01` |
| `target_qty` | INT | No | None | Planned production target for shift | `850` |
| `produced_qty` | INT | No | None | Total units produced/poured | `820` |
| `accepted_qty` | INT | No | None | OK units passing first inspection | `792` |
| `gross_weight_kg` | DECIMAL(10,2) | Yes | None | Total weight poured/cast (Foundry only) | `14760.00` |
| `operator_id` | VARCHAR(32) | Yes | None | Shift supervisor / operator ID | `EMP-4019` |
| `created_at` | DATETIME | No | None | Record creation timestamp | `2026-11-02 14:10:00` |

### 1.2 `pms_rejection_logs` (Quality & Defect Tracking)
Detailed log of every rejected piece or batch inspection failure.

| Field Name | Data Type | Nullable | Primary/Foreign Key | Description | Example Value |
|---|---|---|---|---|---|
| `rejection_id` | VARCHAR(64) | No | PK | Unique rejection inspection record | `REJ-20261102-042` |
| `production_date` | DATE | No | Index | Date of defect occurrence | `2026-11-02` |
| `shop_code` | VARCHAR(32) | No | FK -> shops | Shop where rejection was caught | `FOUNDRY` |
| `shift_code` | VARCHAR(16) | No | FK -> shifts | Shift code | `SHIFT_A` |
| `machine_code` | VARCHAR(32) | No | FK -> machines | Machine where defect originated | `FND-DISA-01` |
| `part_number` | VARCHAR(64) | No | FK -> parts | Part number rejected | `P-BRK-DISC-01` |
| `defect_code` | VARCHAR(32) | No | FK -> defects | Standard defect classification code | `DEF-SAND-INC` |
| `rejected_qty` | INT | No | None | Quantity rejected | `18` |
| `reworkable_qty` | INT | No | None | Quantity capable of rework/salvage | `5` |
| `scrap_qty` | INT | No | None | Quantity permanently scrapped | `13` |
| `unit_cost` | DECIMAL(10,2) | Yes | None | Estimated unit cost of lost material/labor | `145.50` |
| `inspector_id` | VARCHAR(32) | Yes | None | QC Inspector ID | `QC-104` |
| `root_cause_notes`| VARCHAR(255) | Yes | None | Initial inspector notes / root cause | `Sand inclusion near gate cavity` |
| `created_at` | DATETIME | No | None | Record timestamp | `2026-11-02 14:35:00` |

---

## 2. Dimension Master Entities

### 2.1 `dim_shop`
- `shop_id` (INT, PK AUTO_INCREMENT)
- `shop_code` (VARCHAR(32), UNIQUE, e.g. `FOUNDRY`, `MACHINE_SHOP`)
- `shop_name` (VARCHAR(100), e.g. `High Pressure Molding Foundry`, `Precision CNC Machine Shop`)
- `manager_name` (VARCHAR(100))
- `is_active` (BOOLEAN DEFAULT TRUE)

### 2.2 `dim_shift`
- `shift_id` (INT, PK AUTO_INCREMENT)
- `shift_code` (VARCHAR(16), UNIQUE, e.g. `SHIFT_A`, `SHIFT_B`, `SHIFT_C`)
- `shift_name` (VARCHAR(50), e.g. `Morning Shift`, `Afternoon Shift`, `Night Shift`)
- `start_time` (TIME, e.g. `06:00:00`)
- `end_time` (TIME, e.g. `14:00:00`)
- `hours` (DECIMAL(4,2), e.g. `8.00`)

### 2.3 `dim_part`
- `part_id` (INT, PK AUTO_INCREMENT)
- `part_number` (VARCHAR(64), UNIQUE, e.g. `P-BRK-DISC-01`)
- `part_name` (VARCHAR(120), e.g. `Ventilated Brake Disc 280mm`)
- `shop_code` (VARCHAR(32), e.g. `FOUNDRY`)
- `material_grade` (VARCHAR(64), e.g. `Grey Iron FG 260`)
- `unit_weight_kg` (DECIMAL(8,3), e.g. `7.450`)
- `standard_cost` (DECIMAL(10,2), e.g. `185.00`)
- `is_critical` (BOOLEAN DEFAULT FALSE)

### 2.4 `dim_machine`
- `machine_id` (INT, PK AUTO_INCREMENT)
- `machine_code` (VARCHAR(32), UNIQUE, e.g. `MC-CNC-04`, `FND-DISA-01`)
- `machine_name` (VARCHAR(100), e.g. `Doosan Twin Spindle CNC-04`)
- `shop_code` (VARCHAR(32))
- `line_name` (VARCHAR(64), e.g. `Brake Rotor Line A`)
- `rated_capacity_per_hour` (INT)

### 2.5 `dim_defect`
- `defect_id` (INT, PK AUTO_INCREMENT)
- `defect_code` (VARCHAR(32), UNIQUE, e.g. `DEF-SAND-INC`, `DEF-POROSITY`)
- `defect_name` (VARCHAR(100), e.g. `Sand Inclusion`, `Gas Porosity`, `Shrinkage Cavity`, `Tool Chatter / Finish`, `Dimensional Out of Spec`)
- `shop_code` (VARCHAR(32))
- `category` (VARCHAR(64), e.g. `MOLDING_DEFECT`, `METALLURGICAL`, `MACHINING_DIMENSIONAL`, `TOOLING`)
- `severity` (VARCHAR(16), e.g. `CRITICAL`, `MAJOR`, `MINOR`)

---

## 3. Staging Schema (`stg_*`)

Used for idempotent bulk loading and raw data ingestion prior to transformation.

### 3.1 `stg_production`
- Staging table mirroring raw extract rows.
- Contains extraction batch metadata (`batch_id`, `extracted_at`, `source_type`).
- Untransformed text types to prevent ingestion crashes on dirty input.

### 3.2 `stg_rejection`
- Staging table for raw rejection transactions.
- Contains extraction batch metadata and uncleaned string fields for subsequent validation pipeline.

---

## 4. Reporting Warehouse Layer (`fact_*`)

### 4.1 `fact_production` (Clean Daily/Shift Aggregates)
- `fact_id` (BIGINT, PK AUTO_INCREMENT)
- `date_key` (DATE, Index)
- `year_week` (VARCHAR(10), Index, e.g. `2026-W45`)
- `year_month` (VARCHAR(7), Index, e.g. `2026-11`)
- `shop_id` (INT, FK -> dim_shop)
- `shift_id` (INT, FK -> dim_shift)
- `machine_id` (INT, FK -> dim_machine)
- `part_id` (INT, FK -> dim_part)
- `target_qty` (INT)
- `produced_qty` (INT)
- `accepted_qty` (INT)
- `rejected_qty` (INT)
- `rejection_pct` (DECIMAL(6,3))
- `first_pass_yield_pct` (DECIMAL(6,3))
- `total_weight_kg` (DECIMAL(12,2))
- `created_at` (DATETIME)

### 4.2 `fact_rejection` (Defect-Grain Fact)
- `fact_rejection_id` (BIGINT, PK AUTO_INCREMENT)
- `date_key` (DATE, Index)
- `year_week` (VARCHAR(10), Index)
- `year_month` (VARCHAR(7), Index)
- `shop_id` (INT, FK -> dim_shop)
- `shift_id` (INT, FK -> dim_shift)
- `machine_id` (INT, FK -> dim_machine)
- `part_id` (INT, FK -> dim_part)
- `defect_id` (INT, FK -> dim_defect)
- `rejected_qty` (INT)
- `scrap_qty` (INT)
- `reworkable_qty` (INT)
- `scrap_cost` (DECIMAL(12,2))
- `created_at` (DATETIME)

### 4.3 `report_runs` (Audit & Generation Registry)
- `run_id` (BIGINT, PK AUTO_INCREMENT)
- `report_type` (VARCHAR(32), e.g. `WEEKLY_FOUNDRY`, `WEEKLY_MACHINE_SHOP`, `MONTHLY_REJECTION`)
- `period_key` (VARCHAR(16), e.g. `2026-W45`, `2026-11`)
- `status` (VARCHAR(20), e.g. `SUCCESS`, `FAILED`, `IN_PROGRESS`)
- `excel_path` (VARCHAR(255))
- `pdf_path` (VARCHAR(255))
- `total_produced` (INT)
- `total_rejected` (INT)
- `rejection_pct` (DECIMAL(6,3))
- `generated_by` (VARCHAR(64), e.g. `APScheduler`, `admin`)
- `run_duration_ms` (INT)
- `error_message` (TEXT)
- `created_at` (DATETIME)

