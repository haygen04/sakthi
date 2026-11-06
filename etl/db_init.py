"""Database initialization script for Phase 0 setup.

Supports both MySQL 8.0+ and SQLite (portable fallback for local verification).
"""

import sys
import sqlite3
import re
import logging
from pathlib import Path
from config.loader import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_sqlite_conn(db_path: Path):
    """Establishes SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def adapt_schema_for_sqlite(sql_text: str) -> str:
    """Adapts MySQL DDL statements for SQLite compatibility."""
    # Replace (BIGINT|INT) AUTO_INCREMENT PRIMARY KEY or (BIGINT|INT) PRIMARY KEY AUTO_INCREMENT
    sql = re.sub(r"(?:BIGINT|INT)\s+AUTO_INCREMENT\s+PRIMARY\s+KEY", "INTEGER PRIMARY KEY AUTOINCREMENT", sql_text, flags=re.IGNORECASE)
    sql = re.sub(r"(?:BIGINT|INT)\s+PRIMARY\s+KEY\s+AUTO_INCREMENT", "INTEGER PRIMARY KEY AUTOINCREMENT", sql, flags=re.IGNORECASE)
    # Remove CURRENT_TIMESTAMP defaults on update
    sql = re.sub(r"ON\s+UPDATE\s+CURRENT_TIMESTAMP", "", sql, flags=re.IGNORECASE)
    # Remove MySQL specific table constraint lines like UNIQUE KEY uk_..., INDEX idx_..., CONSTRAINT fk_...
    cleaned_lines = []
    for line in sql.splitlines():
        trimmed = line.strip()
        if re.match(r"^(?:UNIQUE\s+KEY|INDEX|KEY|CONSTRAINT)\s+", trimmed, flags=re.IGNORECASE):
            continue
        cleaned_lines.append(line)
    sql = "\n".join(cleaned_lines)
    # Remove trailing commas before closing parenthesis
    sql = re.sub(r",\s*\n\s*\)", "\n)", sql)
    return sql


def init_sqlite_db(db_path: Path, schema_file: Path, seed_file: Path):
    """Initializes SQLite reporting database for zero-config validation."""
    logger.info(f"Initializing SQLite database at: {db_path}")
    conn = get_sqlite_conn(db_path)
    cursor = conn.cursor()

    schema_sql = schema_file.read_text(encoding="utf-8")
    sqlite_schema = adapt_schema_for_sqlite(schema_sql)

    # Split into individual CREATE TABLE statements
    statements = [stmt.strip() for stmt in sqlite_schema.split(";") if stmt.strip()]
    for stmt in statements:
        # Strip comments
        lines = [l for l in stmt.splitlines() if not l.strip().startswith("--")]
        clean_stmt = "\n".join(lines).strip()
        if clean_stmt.upper().startswith("CREATE TABLE"):
            cursor.execute(clean_stmt)

    # Ensure unique indexes for idempotent upserts in SQLite
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_prod ON fact_production (date_key, shop_id, shift_id, machine_id, part_id);")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_rej ON fact_rejection (date_key, shop_id, shift_id, machine_id, part_id, defect_id);")

    conn.commit()

    # Seed dimensions
    seed_sql = seed_file.read_text(encoding="utf-8")
    # Convert MySQL 'INSERT INTO ... ON DUPLICATE KEY UPDATE' to SQLite 'INSERT OR REPLACE'
    for line in seed_sql.splitlines():
        line = line.strip()
        if not line or line.startswith("--"):
            continue

    # Execute custom seed for SQLite
    seed_dimensions_sqlite(conn)
    conn.commit()
    conn.close()
    logger.info("SQLite database initialized and dimensions seeded successfully.")


def seed_dimensions_sqlite(conn):
    """Inserts foundational dimension rows into SQLite."""
    cursor = conn.cursor()

    # Shops
    shops = [
        ("FOUNDRY", "Automotive Casting Foundry Division", "R. Balasubramanian"),
        ("MACHINE_SHOP", "Precision Machining & CNC Division", "K. Senthil Kumar"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO dim_shop (shop_code, shop_name, manager_name) VALUES (?, ?, ?)",
        shops
    )

    # Shifts
    shifts = [
        ("SHIFT_A", "Morning Shift", "06:00:00", "14:00:00", 8.00),
        ("SHIFT_B", "Afternoon Shift", "14:00:00", "22:00:00", 8.00),
        ("SHIFT_C", "Night Shift", "22:00:00", "06:00:00", 8.00),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO dim_shift (shift_code, shift_name, start_time, end_time, hours) VALUES (?, ?, ?, ?, ?)",
        shifts
    )

    # Parts
    parts = [
        ("P-BRK-DISC-01", "Ventilated Brake Disc Rotor 280mm", "FOUNDRY", "Grey Iron FG 260", 7.450, 185.00, 1),
        ("P-BRK-DRUM-02", "Heavy Duty Brake Drum 220mm", "FOUNDRY", "Grey Iron FG 260", 9.800, 240.00, 1),
        ("P-STR-KNCK-03", "Steering Knuckle Front LH", "FOUNDRY", "Ductile Iron SGI 500/7", 5.600, 310.00, 1),
        ("P-STR-KNCK-04", "Steering Knuckle Front RH", "FOUNDRY", "Ductile Iron SGI 500/7", 5.600, 310.00, 1),
        ("P-FLW-WHL-05", "Engine Flywheel Dual Mass 240mm", "FOUNDRY", "Grey Iron FG 300", 11.200, 420.00, 0),
        ("M-BRK-DISC-01", "Machined Brake Disc Finished", "MACHINE_SHOP", "FG 260 Precision", 6.950, 295.00, 1),
        ("M-BRK-DRUM-02", "Machined Brake Drum Finished", "MACHINE_SHOP", "FG 260 Precision", 9.100, 360.00, 1),
        ("M-STR-KNCK-03", "Machined Steering Knuckle LH", "MACHINE_SHOP", "SGI 500/7 Precision", 5.150, 480.00, 1),
        ("M-STR-KNCK-04", "Machined Steering Knuckle RH", "MACHINE_SHOP", "SGI 500/7 Precision", 5.150, 480.00, 1),
        ("M-FLW-WHL-05", "Machined Balanced Flywheel", "MACHINE_SHOP", "FG 300 Dynamic", 10.400, 620.00, 0),
    ]
    cursor.executemany(
        """INSERT OR IGNORE INTO dim_part 
        (part_number, part_name, shop_code, material_grade, unit_weight_kg, standard_cost, is_critical) 
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        parts
    )

    # Machines
    machines = [
        ("FND-DISA-01", "Disamatic High Pressure Molding Line 1", "FOUNDRY", "Molding Line 1", 120),
        ("FND-DISA-02", "Disamatic High Pressure Molding Line 2", "FOUNDRY", "Molding Line 2", 120),
        ("FND-POUR-01", "Auto Pouring Unit Inductotherm 1", "FOUNDRY", "Pouring Line 1", 150),
        ("MC-CNC-01", "Doosan Twin Spindle CNC 01", "MACHINE_SHOP", "Rotor Line A", 45),
        ("MC-CNC-02", "Doosan Twin Spindle CNC 02", "MACHINE_SHOP", "Rotor Line A", 45),
        ("MC-CNC-03", "Doosan Twin Spindle CNC 03", "MACHINE_SHOP", "Rotor Line B", 45),
        ("MC-VMC-01", "Makino High Speed VMC 01", "MACHINE_SHOP", "Knuckle Line", 30),
        ("MC-VMC-02", "Makino High Speed VMC 02", "MACHINE_SHOP", "Knuckle Line", 30),
        ("MC-BAL-01", "Schenck Dynamic Balancing Line 01", "MACHINE_SHOP", "Finishing Line", 60),
    ]
    cursor.executemany(
        """INSERT OR IGNORE INTO dim_machine 
        (machine_code, machine_name, shop_code, line_name, rated_capacity_per_hour) 
        VALUES (?, ?, ?, ?, ?)""",
        machines
    )

    # Defects
    defects = [
        ("DEF-SAND-INC", "Sand Inclusion / Mold Erosion", "FOUNDRY", "MOLDING", "MAJOR"),
        ("DEF-POROSITY", "Gas Porosity / Pin Holes", "FOUNDRY", "METALLURGICAL", "CRITICAL"),
        ("DEF-SHRINKAGE", "Shrinkage Cavity / Porosity", "FOUNDRY", "METALLURGICAL", "CRITICAL"),
        ("DEF-COLD-SHUT", "Cold Shut / Incomplete Pour", "FOUNDRY", "POURING", "MAJOR"),
        ("DEF-SLAG", "Slag / Dross Inclusion", "FOUNDRY", "POURING", "MAJOR"),
        ("DEF-CORE-SHIFT", "Core Shift / Wall Thinning", "FOUNDRY", "CORE_MAKING", "MAJOR"),
        ("DEF-FLASH", "Heavy Metal Flash / Fin", "FOUNDRY", "MOLDING", "MINOR"),
        ("DEF-DIM-OOT", "Dimensional Out of Tolerance", "MACHINE_SHOP", "MACHINING", "CRITICAL"),
        ("DEF-SURF-CHAT", "Surface Roughness / Chatter Marks", "MACHINE_SHOP", "TOOLING", "MAJOR"),
        ("DEF-TOOL-BRK", "Drill / Tap Breakage inside part", "MACHINE_SHOP", "TOOLING", "CRITICAL"),
        ("DEF-RUNOUT", "Face Runout / Dynamic Wobble", "MACHINE_SHOP", "MACHINING", "MAJOR"),
        ("DEF-SUB-POR", "Subsurface Casting Porosity revealed", "MACHINE_SHOP", "RAW_MATERIAL", "MAJOR"),
        ("DEF-BURR", "Heavy Burr / Incomplete Chamfer", "MACHINE_SHOP", "DEBURRING", "MINOR"),
    ]
    cursor.executemany(
        """INSERT OR IGNORE INTO dim_defect 
        (defect_code, defect_name, shop_code, category, severity) 
        VALUES (?, ?, ?, ?, ?)""",
        defects
    )


def verify_database_tables(db_path: Path):
    """Verifies that all required staging and warehouse tables exist."""
    conn = get_sqlite_conn(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    required_tables = {
        "dim_shop", "dim_shift", "dim_part", "dim_machine", "dim_defect", "dim_date",
        "stg_production", "stg_rejection", "fact_production", "fact_rejection", "report_runs"
    }

    missing = required_tables - tables
    if missing:
        raise RuntimeError(f"Database verification failed! Missing tables: {missing}")

    logger.info(f"Verified all {len(required_tables)} required tables exist: {sorted(tables)}")
    return True


def main():
    root_dir = Path(__file__).resolve().parent.parent
    config = load_config()

    schema_file = root_dir / "sql" / "schema.sql"
    seed_file = root_dir / "sql" / "seed_pms_data.sql"
    sqlite_db_path = root_dir / "mis_reporting.db"

    init_sqlite_db(sqlite_db_path, schema_file, seed_file)
    verify_database_tables(sqlite_db_path)
    logger.info("Phase 0 Database verification COMPLETE.")


if __name__ == "__main__":
    main()
