-- ============================================================================
-- Automated Manufacturing MIS and Rejection Report Generator
-- Database Schema: Staging, Reporting Warehouse, and Audit Tables
-- Compatible with MySQL 8.0+ and SQLite (portable syntax)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. DIMENSION TABLES (Reporting Schema)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_shop (
    shop_id INT AUTO_INCREMENT PRIMARY KEY,
    shop_code VARCHAR(32) NOT NULL UNIQUE,
    shop_name VARCHAR(100) NOT NULL,
    manager_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_shift (
    shift_id INT AUTO_INCREMENT PRIMARY KEY,
    shift_code VARCHAR(16) NOT NULL UNIQUE,
    shift_name VARCHAR(50) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    hours DECIMAL(4,2) DEFAULT 8.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_part (
    part_id INT AUTO_INCREMENT PRIMARY KEY,
    part_number VARCHAR(64) NOT NULL UNIQUE,
    part_name VARCHAR(120) NOT NULL,
    shop_code VARCHAR(32) NOT NULL,
    material_grade VARCHAR(64),
    unit_weight_kg DECIMAL(8,3) DEFAULT 0.000,
    standard_cost DECIMAL(10,2) DEFAULT 0.00,
    is_critical BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_part_shop (shop_code)
);

CREATE TABLE IF NOT EXISTS dim_machine (
    machine_id INT AUTO_INCREMENT PRIMARY KEY,
    machine_code VARCHAR(32) NOT NULL UNIQUE,
    machine_name VARCHAR(100) NOT NULL,
    shop_code VARCHAR(32) NOT NULL,
    line_name VARCHAR(64),
    rated_capacity_per_hour INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_machine_shop (shop_code)
);

CREATE TABLE IF NOT EXISTS dim_defect (
    defect_id INT AUTO_INCREMENT PRIMARY KEY,
    defect_code VARCHAR(32) NOT NULL UNIQUE,
    defect_name VARCHAR(100) NOT NULL,
    shop_code VARCHAR(32) NOT NULL,
    category VARCHAR(64) NOT NULL,
    severity VARCHAR(16) DEFAULT 'MAJOR',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_defect_shop (shop_code),
    INDEX idx_defect_cat (category)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key DATE PRIMARY KEY,
    day_name VARCHAR(12) NOT NULL,
    day_of_week INT NOT NULL,
    week_number INT NOT NULL,
    year_week VARCHAR(10) NOT NULL,
    month_number INT NOT NULL,
    month_name VARCHAR(16) NOT NULL,
    year_month VARCHAR(7) NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL,
    is_weekend BOOLEAN DEFAULT FALSE,
    INDEX idx_date_yw (year_week),
    INDEX idx_date_ym (year_month)
);

-- ----------------------------------------------------------------------------
-- 2. STAGING SCHEMA (Raw Ingestion)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stg_production (
    staging_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL,
    source_type VARCHAR(32) DEFAULT 'PMS_EXTRACT',
    log_id VARCHAR(64),
    production_date VARCHAR(32),
    shop_code VARCHAR(32),
    shift_code VARCHAR(32),
    machine_code VARCHAR(32),
    part_number VARCHAR(64),
    target_qty VARCHAR(32),
    produced_qty VARCHAR(32),
    accepted_qty VARCHAR(32),
    gross_weight_kg VARCHAR(32),
    operator_id VARCHAR(32),
    raw_timestamp VARCHAR(64),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_prod_batch (batch_id),
    INDEX idx_stg_prod_date (production_date)
);

CREATE TABLE IF NOT EXISTS stg_rejection (
    staging_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL,
    source_type VARCHAR(32) DEFAULT 'PMS_EXTRACT',
    rejection_id VARCHAR(64),
    production_date VARCHAR(32),
    shop_code VARCHAR(32),
    shift_code VARCHAR(32),
    machine_code VARCHAR(32),
    part_number VARCHAR(64),
    defect_code VARCHAR(32),
    rejected_qty VARCHAR(32),
    reworkable_qty VARCHAR(32),
    scrap_qty VARCHAR(32),
    unit_cost VARCHAR(32),
    inspector_id VARCHAR(32),
    root_cause_notes TEXT,
    raw_timestamp VARCHAR(64),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_rej_batch (batch_id),
    INDEX idx_stg_rej_date (production_date)
);

-- ----------------------------------------------------------------------------
-- 3. FACT TABLES (Clean Reporting Warehouse)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS fact_production (
    fact_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    date_key DATE NOT NULL,
    year_week VARCHAR(10) NOT NULL,
    year_month VARCHAR(7) NOT NULL,
    shop_id INT NOT NULL,
    shift_id INT NOT NULL,
    machine_id INT NOT NULL,
    part_id INT NOT NULL,
    target_qty INT NOT NULL DEFAULT 0,
    produced_qty INT NOT NULL DEFAULT 0,
    accepted_qty INT NOT NULL DEFAULT 0,
    rejected_qty INT NOT NULL DEFAULT 0,
    rejection_pct DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    first_pass_yield_pct DECIMAL(6,3) NOT NULL DEFAULT 100.000,
    gross_weight_kg DECIMAL(12,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_fact_prod (date_key, shop_id, shift_id, machine_id, part_id),
    INDEX idx_fact_prod_date (date_key),
    INDEX idx_fact_prod_yw (year_week),
    INDEX idx_fact_prod_ym (year_month),
    INDEX idx_fact_prod_shop (shop_id),
    INDEX idx_fact_prod_part (part_id),
    CONSTRAINT fk_fact_prod_shop FOREIGN KEY (shop_id) REFERENCES dim_shop(shop_id),
    CONSTRAINT fk_fact_prod_shift FOREIGN KEY (shift_id) REFERENCES dim_shift(shift_id),
    CONSTRAINT fk_fact_prod_machine FOREIGN KEY (machine_id) REFERENCES dim_machine(machine_id),
    CONSTRAINT fk_fact_prod_part FOREIGN KEY (part_id) REFERENCES dim_part(part_id)
);

CREATE TABLE IF NOT EXISTS fact_rejection (
    fact_rejection_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    date_key DATE NOT NULL,
    year_week VARCHAR(10) NOT NULL,
    year_month VARCHAR(7) NOT NULL,
    shop_id INT NOT NULL,
    shift_id INT NOT NULL,
    machine_id INT NOT NULL,
    part_id INT NOT NULL,
    defect_id INT NOT NULL,
    rejected_qty INT NOT NULL DEFAULT 0,
    scrap_qty INT NOT NULL DEFAULT 0,
    reworkable_qty INT NOT NULL DEFAULT 0,
    scrap_cost DECIMAL(12,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_fact_rej (date_key, shop_id, shift_id, machine_id, part_id, defect_id),
    INDEX idx_fact_rej_date (date_key),
    INDEX idx_fact_rej_yw (year_week),
    INDEX idx_fact_rej_ym (year_month),
    INDEX idx_fact_rej_shop (shop_id),
    INDEX idx_fact_rej_defect (defect_id),
    INDEX idx_fact_rej_part (part_id),
    CONSTRAINT fk_fact_rej_shop FOREIGN KEY (shop_id) REFERENCES dim_shop(shop_id),
    CONSTRAINT fk_fact_rej_shift FOREIGN KEY (shift_id) REFERENCES dim_shift(shift_id),
    CONSTRAINT fk_fact_rej_machine FOREIGN KEY (machine_id) REFERENCES dim_machine(machine_id),
    CONSTRAINT fk_fact_rej_part FOREIGN KEY (part_id) REFERENCES dim_part(part_id),
    CONSTRAINT fk_fact_rej_defect FOREIGN KEY (defect_id) REFERENCES dim_defect(defect_id)
);

-- ----------------------------------------------------------------------------
-- 4. AUDIT & REPORT REGISTRY
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS report_runs (
    run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    report_type VARCHAR(32) NOT NULL,
    period_key VARCHAR(16) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'IN_PROGRESS',
    excel_path VARCHAR(255),
    pdf_path VARCHAR(255),
    total_produced INT DEFAULT 0,
    total_rejected INT DEFAULT 0,
    rejection_pct DECIMAL(6,3) DEFAULT 0.000,
    generated_by VARCHAR(64) DEFAULT 'SYSTEM',
    run_duration_ms INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_rep_type (report_type),
    INDEX idx_rep_period (period_key),
    INDEX idx_rep_status (status)
);

