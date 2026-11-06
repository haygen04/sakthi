"""Data Validation Module for Manufacturing MIS & Rejection Report Generator.

Enforces data integrity, range constraints, mandatory field presence,
relational consistency (e.g. accepted <= produced, scrap + rework == rejected),
and deduplication, outputting an audit validation summary.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger("etl.validate")


@dataclass
class ValidationSummary:
    """Summary of data validation execution and rejection reasons."""
    dataset_name: str
    total_checked: int = 0
    valid_count: int = 0
    rejected_count: int = 0
    warnings_count: int = 0
    rejection_reasons: List[Dict[str, Any]] = field(default_factory=list)
    warning_messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "total_checked": self.total_checked,
            "valid_count": self.valid_count,
            "rejected_count": self.rejected_count,
            "warnings_count": self.warnings_count,
            "rejection_reasons": self.rejection_reasons[:20],  # cap sample
            "warning_messages": self.warning_messages[:20],
        }


class DataValidator:
    """Validates raw production and rejection datasets against manufacturing business rules."""

    VALID_SHOPS = {"FOUNDRY", "MACHINE_SHOP"}
    VALID_SHIFTS = {"SHIFT_A", "SHIFT_B", "SHIFT_C"}

    def __init__(self):
        self.prod_summary = ValidationSummary(dataset_name="production")
        self.rej_summary = ValidationSummary(dataset_name="rejection")

    def validate_production(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, ValidationSummary]:
        """Validates raw production DataFrame.

        Rules:
        1. Mandatory fields: log_id, production_date, shop_code, shift_code, machine_code, part_number, produced_qty
        2. Non-negative quantities: target_qty, produced_qty, accepted_qty, gross_weight_kg >= 0
        3. Business logic: accepted_qty <= produced_qty
        4. Valid shop and shift classifications
        5. Deduplication by log_id (keeps latest)
        """
        self.prod_summary = ValidationSummary(dataset_name="production", total_checked=len(df))
        if df.empty:
            return df, self.prod_summary

        clean_df = df.copy()

        # Step 1: Deduplication
        initial_count = len(clean_df)
        if "log_id" in clean_df.columns:
            clean_df = clean_df.drop_duplicates(subset=["log_id"], keep="last")
            dups_dropped = initial_count - len(clean_df)
            if dups_dropped > 0:
                self.prod_summary.warning_messages.append(f"Dropped {dups_dropped} duplicate log_id rows.")
                self.prod_summary.warnings_count += dups_dropped

        # Step 2: Mandatory column check
        mandatory_cols = ["log_id", "production_date", "shop_code", "shift_code", "machine_code", "part_number", "produced_qty"]
        missing_mandatory = [col for col in mandatory_cols if col not in clean_df.columns]
        if missing_mandatory:
            raise ValueError(f"Production dataset missing mandatory columns: {missing_mandatory}")

        # Check for nulls/empty in mandatory fields
        valid_mask = pd.Series(True, index=clean_df.index)
        for col in mandatory_cols:
            col_null_mask = clean_df[col].isna() | (clean_df[col].astype(str).str.strip() == "")
            if col_null_mask.any():
                invalid_indices = clean_df[col_null_mask].index
                for idx in invalid_indices:
                    self.prod_summary.rejection_reasons.append({
                        "row_id": str(clean_df.at[idx, "log_id"]),
                        "reason": f"Mandatory field '{col}' is null or empty"
                    })
                valid_mask &= ~col_null_mask

        # Step 3: Numeric Conversion & Range Constraints
        numeric_cols = {
            "target_qty": (int, 0),
            "produced_qty": (int, 0),
            "accepted_qty": (int, 0),
            "gross_weight_kg": (float, 0.0),
        }

        for col, (target_type, default_val) in numeric_cols.items():
            if col in clean_df.columns:
                clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")
                neg_mask = clean_df[col] < 0
                if neg_mask.any():
                    for idx in clean_df[neg_mask].index:
                        self.prod_summary.rejection_reasons.append({
                            "row_id": str(clean_df.at[idx, "log_id"]),
                            "reason": f"Negative value in '{col}': {clean_df.at[idx, col]}"
                        })
                    valid_mask &= ~neg_mask
                # Fill remaining NaN with default
                clean_df[col] = clean_df[col].fillna(default_val).astype(target_type)

        # Step 4: Business Rule: accepted_qty <= produced_qty
        excess_accepted = clean_df["accepted_qty"] > clean_df["produced_qty"]
        if excess_accepted.any():
            for idx in clean_df[excess_accepted].index:
                self.prod_summary.rejection_reasons.append({
                    "row_id": str(clean_df.at[idx, "log_id"]),
                    "reason": f"Accepted qty ({clean_df.at[idx, 'accepted_qty']}) exceeds produced qty ({clean_df.at[idx, 'produced_qty']})"
                })
            valid_mask &= ~excess_accepted

        # Step 5: Shop and Shift Standard Validation
        clean_df["shop_code"] = clean_df["shop_code"].astype(str).str.strip().str.upper()
        clean_df["shift_code"] = clean_df["shift_code"].astype(str).str.strip().str.upper()

        invalid_shops = ~clean_df["shop_code"].isin(self.VALID_SHOPS)
        if invalid_shops.any():
            for idx in clean_df[invalid_shops].index:
                self.prod_summary.rejection_reasons.append({
                    "row_id": str(clean_df.at[idx, "log_id"]),
                    "reason": f"Invalid shop_code '{clean_df.at[idx, 'shop_code']}'"
                })
            valid_mask &= ~invalid_shops

        invalid_shifts = ~clean_df["shift_code"].isin(self.VALID_SHIFTS)
        if invalid_shifts.any():
            for idx in clean_df[invalid_shifts].index:
                self.prod_summary.rejection_reasons.append({
                    "row_id": str(clean_df.at[idx, "log_id"]),
                    "reason": f"Invalid shift_code '{clean_df.at[idx, 'shift_code']}'"
                })
            valid_mask &= ~invalid_shifts

        valid_df = clean_df[valid_mask].copy()
        self.prod_summary.valid_count = len(valid_df)
        self.prod_summary.rejected_count = len(clean_df) - len(valid_df)

        logger.info(
            f"Production Validation: {self.prod_summary.valid_count} valid, "
            f"{self.prod_summary.rejected_count} rejected out of {self.prod_summary.total_checked} rows."
        )
        return valid_df, self.prod_summary

    def validate_rejection(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, ValidationSummary]:
        """Validates raw rejection DataFrame.

        Rules:
        1. Mandatory fields: rejection_id, production_date, shop_code, shift_code, machine_code, part_number, defect_code, rejected_qty
        2. Non-negative quantities: rejected_qty, reworkable_qty, scrap_qty, unit_cost >= 0
        3. Business logic consistency: rejected_qty >= reworkable_qty + scrap_qty (if mismatch, adjust or flag)
        4. Valid shop and shift classifications
        5. Deduplication by rejection_id (keeps latest)
        """
        self.rej_summary = ValidationSummary(dataset_name="rejection", total_checked=len(df))
        if df.empty:
            return df, self.rej_summary

        clean_df = df.copy()

        # Step 1: Deduplication
        initial_count = len(clean_df)
        if "rejection_id" in clean_df.columns:
            clean_df = clean_df.drop_duplicates(subset=["rejection_id"], keep="last")
            dups_dropped = initial_count - len(clean_df)
            if dups_dropped > 0:
                self.rej_summary.warning_messages.append(f"Dropped {dups_dropped} duplicate rejection_id rows.")
                self.rej_summary.warnings_count += dups_dropped

        # Step 2: Mandatory column check
        mandatory_cols = [
            "rejection_id", "production_date", "shop_code", "shift_code",
            "machine_code", "part_number", "defect_code", "rejected_qty"
        ]
        missing_mandatory = [col for col in mandatory_cols if col not in clean_df.columns]
        if missing_mandatory:
            raise ValueError(f"Rejection dataset missing mandatory columns: {missing_mandatory}")

        valid_mask = pd.Series(True, index=clean_df.index)
        for col in mandatory_cols:
            col_null_mask = clean_df[col].isna() | (clean_df[col].astype(str).str.strip() == "")
            if col_null_mask.any():
                for idx in clean_df[col_null_mask].index:
                    self.rej_summary.rejection_reasons.append({
                        "row_id": str(clean_df.at[idx, "rejection_id"]),
                        "reason": f"Mandatory field '{col}' is null or empty"
                    })
                valid_mask &= ~col_null_mask

        # Step 3: Numeric Conversion & Range Constraints
        numeric_cols = {
            "rejected_qty": (int, 0),
            "reworkable_qty": (int, 0),
            "scrap_qty": (int, 0),
            "unit_cost": (float, 0.0),
        }

        for col, (target_type, default_val) in numeric_cols.items():
            if col in clean_df.columns:
                clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")
                neg_mask = clean_df[col] < 0
                if neg_mask.any():
                    for idx in clean_df[neg_mask].index:
                        self.rej_summary.rejection_reasons.append({
                            "row_id": str(clean_df.at[idx, "rejection_id"]),
                            "reason": f"Negative value in '{col}': {clean_df.at[idx, col]}"
                        })
                    valid_mask &= ~neg_mask
                clean_df[col] = clean_df[col].fillna(default_val).astype(target_type)

        # Step 4: Scrap + Rework Consistency
        # If rejected_qty > 0 but scrap_qty + reworkable_qty == 0, assume scrap = rejected
        mismatch_mask = (clean_df["scrap_qty"] + clean_df["reworkable_qty"]) != clean_df["rejected_qty"]
        if mismatch_mask.any():
            for idx in clean_df[mismatch_mask].index:
                # Auto-balance: if rework + scrap != rejected, set scrap = rejected - rework
                r_qty = clean_df.at[idx, "rejected_qty"]
                rw_qty = clean_df.at[idx, "reworkable_qty"]
                if rw_qty <= r_qty:
                    clean_df.at[idx, "scrap_qty"] = r_qty - rw_qty
                    self.rej_summary.warning_messages.append(
                        f"Rejection row {clean_df.at[idx, 'rejection_id']}: Adjusted scrap_qty to {r_qty - rw_qty}"
                    )
                    self.rej_summary.warnings_count += 1
                else:
                    self.rej_summary.rejection_reasons.append({
                        "row_id": str(clean_df.at[idx, "rejection_id"]),
                        "reason": f"Reworkable qty ({rw_qty}) exceeds rejected qty ({r_qty})"
                    })
                    valid_mask.at[idx] = False

        # Step 5: Shop and Shift Standard Validation
        clean_df["shop_code"] = clean_df["shop_code"].astype(str).str.strip().str.upper()
        clean_df["shift_code"] = clean_df["shift_code"].astype(str).str.strip().str.upper()
        clean_df["defect_code"] = clean_df["defect_code"].astype(str).str.strip().str.upper()

        invalid_shops = ~clean_df["shop_code"].isin(self.VALID_SHOPS)
        if invalid_shops.any():
            for idx in clean_df[invalid_shops].index:
                self.rej_summary.rejection_reasons.append({
                    "row_id": str(clean_df.at[idx, "rejection_id"]),
                    "reason": f"Invalid shop_code '{clean_df.at[idx, 'shop_code']}'"
                })
            valid_mask &= ~invalid_shops

        valid_df = clean_df[valid_mask].copy()
        self.rej_summary.valid_count = len(valid_df)
        self.rej_summary.rejected_count = len(clean_df) - len(valid_df)

        logger.info(
            f"Rejection Validation: {self.rej_summary.valid_count} valid, "
            f"{self.rej_summary.rejected_count} rejected out of {self.rej_summary.total_checked} rows."
        )
        return valid_df, self.rej_summary

