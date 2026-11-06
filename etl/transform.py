"""Data Transformation & KPI Engine for Manufacturing MIS & Rejection Reports.

Performs data cleansing, validation pipeline invocation, multi-dimensional aggregations,
KPI calculations (Rejection %, FPY, Defect Pareto, Scrap Cost, WoW/MoM trends),
and anomaly detection with executive commentary generation.
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import numpy as np

from config.loader import load_config
from etl.validate import DataValidator, ValidationSummary

logger = logging.getLogger("etl.transform")


class DataTransformer:
    """Transforms validated raw staging datasets into clean, aggregated report KPIs."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_config()
        self.validator = DataValidator()

    def clean_text_and_dates(self, df: pd.DataFrame, date_col: str = "production_date") -> pd.DataFrame:
        """Trims whitespace, standardizes text casing, and formats dates."""
        res = df.copy()
        # Clean text columns
        text_cols = res.select_dtypes(include=["object", "string"]).columns
        for c in text_cols:
            res[c] = res[c].astype(str).str.strip()

        # Upper case identifiers
        for code_col in ["shop_code", "shift_code", "machine_code", "part_number", "defect_code"]:
            if code_col in res.columns:
                res[code_col] = res[code_col].str.upper()

        # Parse dates
        if date_col in res.columns:
            res[date_col] = pd.to_datetime(res[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
            # Generate calendar keys
            dt_series = pd.to_datetime(res[date_col])
            res["date_key"] = res[date_col]
            res["year_week"] = dt_series.apply(lambda d: f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}" if pd.notna(d) else "")
            res["year_month"] = dt_series.apply(lambda d: f"{d.year}-{d.month:02d}" if pd.notna(d) else "")
            res["day_name"] = dt_series.dt.day_name()

        return res

    def transform(
        self,
        raw_prod: pd.DataFrame,
        raw_rej: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Executes full transformation pipeline on raw production and rejection datasets."""
        logger.info(f"Starting transformation on {len(raw_prod)} prod rows and {len(raw_rej)} rej rows.")

        # 1. Clean
        clean_prod = self.clean_text_and_dates(raw_prod)
        clean_rej = self.clean_text_and_dates(raw_rej)

        # 2. Validate
        val_prod, prod_summary = self.validator.validate_production(clean_prod)
        val_rej, rej_summary = self.validator.validate_rejection(clean_rej)

        # Log validation audit summary
        logger.info(
            f"Validation Completed: Production {prod_summary.valid_count}/{prod_summary.total_checked} valid | "
            f"Rejection {rej_summary.valid_count}/{rej_summary.total_checked} valid"
        )

        # 3. Aggregations & KPI Calculations
        prod_fact = self.compute_production_fact(val_prod, val_rej)
        rej_fact = self.compute_rejection_fact(val_rej)

        shop_kpis = self.compute_shop_summary(prod_fact, rej_fact)
        daily_kpis = self.compute_daily_trend(prod_fact)
        shift_kpis = self.compute_shift_performance(prod_fact)
        defect_pareto = self.compute_defect_pareto(rej_fact)
        part_kpis = self.compute_part_rejections(prod_fact, rej_fact)
        machine_kpis = self.compute_machine_performance(prod_fact)

        # 4. Anomaly Detection
        anomalies = self.detect_anomalies(shop_kpis, defect_pareto, part_kpis)

        # 5. Executive Observations
        observations = self.generate_observations(shop_kpis, defect_pareto, anomalies)

        return {
            "validation_summary": {
                "production": prod_summary.to_dict(),
                "rejection": rej_summary.to_dict(),
            },
            "fact_production": prod_fact,
            "fact_rejection": rej_fact,
            "shop_kpis": shop_kpis,
            "daily_kpis": daily_kpis,
            "shift_kpis": shift_kpis,
            "defect_pareto": defect_pareto,
            "part_kpis": part_kpis,
            "machine_kpis": machine_kpis,
            "anomalies": anomalies,
            "observations": observations,
        }

    # -----------------------------------------------------------------------
    # Fact Computation
    # -----------------------------------------------------------------------
    def compute_production_fact(self, prod_df: pd.DataFrame, rej_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregates clean production records to fact_production grain and links rejection totals."""
        if prod_df.empty:
            return pd.DataFrame()

        # Group by grain: date_key, year_week, year_month, shop_code, shift_code, machine_code, part_number
        grain = ["date_key", "year_week", "year_month", "shop_code", "shift_code", "machine_code", "part_number"]
        fact_p = (
            prod_df.groupby(grain, as_index=False)
            .agg({
                "target_qty": "sum",
                "produced_qty": "sum",
                "accepted_qty": "sum",
                "gross_weight_kg": "sum",
            })
        )

        # Map rejection totals per grain
        if not rej_df.empty:
            rej_agg = (
                rej_df.groupby(grain, as_index=False)
                .agg({
                    "rejected_qty": "sum",
                    "scrap_qty": "sum",
                    "reworkable_qty": "sum",
                })
            )
            fact = pd.merge(fact_p, rej_agg, on=grain, how="left")
            fact["rejected_qty"] = fact["rejected_qty"].fillna(0).astype(int)
            fact["scrap_qty"] = fact["scrap_qty"].fillna(0).astype(int)
            fact["reworkable_qty"] = fact["reworkable_qty"].fillna(0).astype(int)
        else:
            fact = fact_p
            fact["rejected_qty"] = (fact["produced_qty"] - fact["accepted_qty"]).clip(lower=0)
            fact["scrap_qty"] = fact["rejected_qty"]
            fact["reworkable_qty"] = 0

        # Compute calculated KPIs
        fact["rejection_pct"] = np.where(
            fact["produced_qty"] > 0,
            np.round((fact["rejected_qty"] / fact["produced_qty"]) * 100, 3),
            0.0
        )
        fact["first_pass_yield_pct"] = np.where(
            fact["produced_qty"] > 0,
            np.round((fact["accepted_qty"] / fact["produced_qty"]) * 100, 3),
            100.0
        )

        return fact

    def compute_rejection_fact(self, rej_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregates clean rejection transactions to fact_rejection grain."""
        if rej_df.empty:
            return pd.DataFrame()

        grain = ["date_key", "year_week", "year_month", "shop_code", "shift_code", "machine_code", "part_number", "defect_code"]
        rej_fact = (
            rej_df.groupby(grain, as_index=False)
            .agg({
                "rejected_qty": "sum",
                "scrap_qty": "sum",
                "reworkable_qty": "sum",
                "unit_cost": "mean",
            })
        )
        rej_fact["scrap_cost"] = np.round(rej_fact["scrap_qty"] * rej_fact["unit_cost"], 2)
        return rej_fact

    # -----------------------------------------------------------------------
    # Higher Level KPI Computations
    # -----------------------------------------------------------------------
    def compute_shop_summary(self, fact_prod: pd.DataFrame, fact_rej: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Calculates shop-level executive KPIs (Foundry vs Machine Shop vs Overall Plant)."""
        summary = {}
        if fact_prod.empty:
            return summary

        shops = list(fact_prod["shop_code"].unique()) + ["TOTAL_PLANT"]
        for shop in shops:
            if shop == "TOTAL_PLANT":
                df = fact_prod
                df_r = fact_rej
            else:
                df = fact_prod[fact_prod["shop_code"] == shop]
                df_r = fact_rej[fact_rej["shop_code"] == shop] if not fact_rej.empty else pd.DataFrame()

            prod = int(df["produced_qty"].sum())
            target = int(df["target_qty"].sum())
            accepted = int(df["accepted_qty"].sum())
            rejected = int(df["rejected_qty"].sum())
            weight_mt = round(float(df["gross_weight_kg"].sum()) / 1000.0, 2)
            scrap_cost = float(df_r["scrap_cost"].sum()) if not df_r.empty and "scrap_cost" in df_r.columns else 0.0

            rej_pct = round((rejected / prod * 100), 2) if prod > 0 else 0.0
            fpy_pct = round((accepted / prod * 100), 2) if prod > 0 else 100.0
            eff_pct = round((prod / target * 100), 2) if target > 0 else 0.0

            # Status chip based on shop thresholds
            status = self._get_status(shop, rej_pct)

            summary[shop] = {
                "produced_qty": prod,
                "target_qty": target,
                "accepted_qty": accepted,
                "rejected_qty": rejected,
                "rejection_pct": rej_pct,
                "first_pass_yield_pct": fpy_pct,
                "target_adherence_pct": eff_pct,
                "total_weight_mt": weight_mt,
                "scrap_cost": scrap_cost,
                "status": status,
            }

        return summary

    def _get_status(self, shop: str, rej_pct: float) -> str:
        """Determines pastel status color key (good / warn / bad)."""
        if "FOUNDRY" in shop:
            warn_th = self.config.get("reports", {}).get("foundry", {}).get("rejection_warning_pct", 3.5)
            crit_th = self.config.get("reports", {}).get("foundry", {}).get("rejection_critical_pct", 4.5)
        else:
            warn_th = self.config.get("reports", {}).get("machine_shop", {}).get("rejection_warning_pct", 2.0)
            crit_th = self.config.get("reports", {}).get("machine_shop", {}).get("rejection_critical_pct", 2.8)

        if rej_pct <= warn_th:
            return "good"
        elif rej_pct <= crit_th:
            return "warn"
        return "bad"

    def compute_daily_trend(self, fact_prod: pd.DataFrame) -> pd.DataFrame:
        """Computes daily production, rejection and yield trend."""
        if fact_prod.empty:
            return pd.DataFrame()

        daily = (
            fact_prod.groupby(["date_key", "shop_code"], as_index=False)
            .agg({
                "target_qty": "sum",
                "produced_qty": "sum",
                "accepted_qty": "sum",
                "rejected_qty": "sum",
                "gross_weight_kg": "sum",
            })
            .sort_values("date_key")
        )
        daily["rejection_pct"] = np.where(
            daily["produced_qty"] > 0,
            np.round((daily["rejected_qty"] / daily["produced_qty"]) * 100, 2),
            0.0
        )
        return daily

    def compute_shift_performance(self, fact_prod: pd.DataFrame) -> pd.DataFrame:
        """Computes shift-wise performance variance across shops."""
        if fact_prod.empty:
            return pd.DataFrame()

        shift_df = (
            fact_prod.groupby(["shop_code", "shift_code"], as_index=False)
            .agg({
                "produced_qty": "sum",
                "accepted_qty": "sum",
                "rejected_qty": "sum",
            })
        )
        shift_df["rejection_pct"] = np.where(
            shift_df["produced_qty"] > 0,
            np.round((shift_df["rejected_qty"] / shift_df["produced_qty"]) * 100, 2),
            0.0
        )
        return shift_df

    def compute_defect_pareto(self, fact_rej: pd.DataFrame) -> pd.DataFrame:
        """Computes ranked defect Pareto distribution with cumulative percentages."""
        if fact_rej.empty:
            return pd.DataFrame()

        pareto = (
            fact_rej.groupby(["shop_code", "defect_code"], as_index=False)
            .agg({
                "rejected_qty": "sum",
                "scrap_qty": "sum",
                "reworkable_qty": "sum",
                "scrap_cost": "sum",
            })
        )

        results = []
        for shop in pareto["shop_code"].unique():
            shop_p = pareto[pareto["shop_code"] == shop].sort_values("rejected_qty", ascending=False).copy()
            total_rej = shop_p["rejected_qty"].sum()
            if total_rej > 0:
                shop_p["defect_pct"] = np.round((shop_p["rejected_qty"] / total_rej) * 100, 2)
                shop_p["cumulative_pct"] = np.round(shop_p["defect_pct"].cumsum(), 2)
                shop_p["is_vital_few"] = shop_p["cumulative_pct"] <= 85.0
            else:
                shop_p["defect_pct"] = 0.0
                shop_p["cumulative_pct"] = 0.0
                shop_p["is_vital_few"] = False
            results.append(shop_p)

        return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

    def compute_part_rejections(self, fact_prod: pd.DataFrame, fact_rej: pd.DataFrame) -> pd.DataFrame:
        """Computes part-wise rejection volumes, rates, and scrap loss."""
        if fact_prod.empty:
            return pd.DataFrame()

        prod_part = (
            fact_prod.groupby(["shop_code", "part_number"], as_index=False)
            .agg({"produced_qty": "sum", "accepted_qty": "sum", "rejected_qty": "sum"})
        )
        prod_part["rejection_pct"] = np.where(
            prod_part["produced_qty"] > 0,
            np.round((prod_part["rejected_qty"] / prod_part["produced_qty"]) * 100, 2),
            0.0
        )

        if not fact_rej.empty:
            cost_part = (
                fact_rej.groupby(["shop_code", "part_number"], as_index=False)
                .agg({"scrap_cost": "sum"})
            )
            merged = pd.merge(prod_part, cost_part, on=["shop_code", "part_number"], how="left")
            merged["scrap_cost"] = merged["scrap_cost"].fillna(0.0).round(2)
        else:
            merged = prod_part
            merged["scrap_cost"] = 0.0

        return merged.sort_values(["shop_code", "rejected_qty"], ascending=[True, False])

    def compute_machine_performance(self, fact_prod: pd.DataFrame) -> pd.DataFrame:
        """Computes machine line output and quality rates."""
        if fact_prod.empty:
            return pd.DataFrame()

        mach = (
            fact_prod.groupby(["shop_code", "machine_code"], as_index=False)
            .agg({"produced_qty": "sum", "accepted_qty": "sum", "rejected_qty": "sum"})
        )
        mach["rejection_pct"] = np.where(
            mach["produced_qty"] > 0,
            np.round((mach["rejected_qty"] / mach["produced_qty"]) * 100, 2),
            0.0
        )
        return mach.sort_values(["shop_code", "rejection_pct"], ascending=[True, False])

    # -----------------------------------------------------------------------
    # Anomaly Detection & Commentary
    # -----------------------------------------------------------------------
    def detect_anomalies(
        self,
        shop_kpis: Dict[str, Dict[str, Any]],
        pareto_df: pd.DataFrame,
        part_df: pd.DataFrame,
    ) -> List[Dict[str, Any]]:
        """Identifies operational anomalies exceeding control limits."""
        anomalies = []

        # 1. Shop Level High Rejection
        for shop, data in shop_kpis.items():
            if shop == "TOTAL_PLANT":
                continue
            if data["status"] == "bad":
                anomalies.append({
                    "severity": "CRITICAL",
                    "category": "SHOP_REJECTION_SPIKE",
                    "shop_code": shop,
                    "message": f"{shop} rejection rate of {data['rejection_pct']}% exceeds critical threshold.",
                    "metric_value": data["rejection_pct"],
                })
            elif data["status"] == "warn":
                anomalies.append({
                    "severity": "WARNING",
                    "category": "SHOP_REJECTION_ELEVATED",
                    "shop_code": shop,
                    "message": f"{shop} rejection rate is elevated at {data['rejection_pct']}%.",
                    "metric_value": data["rejection_pct"],
                })

        # 2. Defect Dominance (> 35% of shop rejection)
        if not pareto_df.empty:
            dominant = pareto_df[pareto_df["defect_pct"] >= 35.0]
            for _, row in dominant.iterrows():
                anomalies.append({
                    "severity": "MAJOR",
                    "category": "DOMINANT_DEFECT",
                    "shop_code": row["shop_code"],
                    "defect_code": row["defect_code"],
                    "message": f"Defect '{row['defect_code']}' accounts for {row['defect_pct']}% of all {row['shop_code']} rejections.",
                    "metric_value": row["defect_pct"],
                })

        # 3. Part Outlier (> 2x shop average)
        if not part_df.empty:
            for shop, data in shop_kpis.items():
                if shop == "TOTAL_PLANT":
                    continue
                shop_avg = data["rejection_pct"]
                outliers = part_df[(part_df["shop_code"] == shop) & (part_df["rejection_pct"] > (2 * shop_avg)) & (part_df["produced_qty"] > 100)]
                for _, row in outliers.iterrows():
                    anomalies.append({
                        "severity": "WARNING",
                        "category": "PART_OUTLIER",
                        "shop_code": shop,
                        "part_number": row["part_number"],
                        "message": f"Part '{row['part_number']}' rejection rate ({row['rejection_pct']}%) is more than double {shop} average ({shop_avg}%).",
                        "metric_value": row["rejection_pct"],
                    })

        return anomalies

    def generate_observations(
        self,
        shop_kpis: Dict[str, Dict[str, Any]],
        pareto_df: pd.DataFrame,
        anomalies: List[Dict[str, Any]],
    ) -> List[str]:
        """Generates clear, executive summary observations for reports and dashboard."""
        obs = []

        # Overall observation
        if "TOTAL_PLANT" in shop_kpis:
            tot = shop_kpis["TOTAL_PLANT"]
            obs.append(
                f"Plant-wide production reached {tot['produced_qty']:,} units with overall rejection at {tot['rejection_pct']}% (FPY: {tot['first_pass_yield_pct']}%)."
            )

        # Shop specific observation
        if "FOUNDRY" in shop_kpis:
            fnd = shop_kpis["FOUNDRY"]
            obs.append(
                f"Foundry Division poured {fnd['total_weight_mt']} MT of metal ({fnd['produced_qty']:,} castings) with a {fnd['rejection_pct']}% rejection rate."
            )

        if "MACHINE_SHOP" in shop_kpis:
            ms = shop_kpis["MACHINE_SHOP"]
            obs.append(
                f"Machine Shop finished {ms['produced_qty']:,} components with {ms['rejection_pct']}% machining rejections."
            )

        # Top defects
        if not pareto_df.empty:
            for shop in pareto_df["shop_code"].unique():
                top = pareto_df[pareto_df["shop_code"] == shop].head(2)
                defect_items = [f"{r['defect_code']} ({r['rejected_qty']} pcs, {r['defect_pct']}%)" for _, r in top.iterrows()]
                obs.append(f"Top {shop} defect drivers: {', '.join(defect_items)}.")

        # Anomaly callouts
        if anomalies:
            crit = [a["message"] for a in anomalies if a["severity"] in ["CRITICAL", "MAJOR"]]
            if crit:
                obs.append(f"Attention required: {crit[0]}")

        return obs
