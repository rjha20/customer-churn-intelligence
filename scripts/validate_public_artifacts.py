from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "processed" / "public"
EXPECTED = {
    "monthly_performance.csv": {"snapshot_month", "eligible_episodes", "inactivity_rate", "model_average_precision", "recency_baseline_average_precision"},
    "segment_performance.csv": {"dimension", "segment", "eligible_episodes", "inactive_90d", "inactivity_rate", "ci_95_low", "ci_95_high", "avg_spend_180d_gbp"},
    "retention_cohorts.csv": {"cohort_month", "customers", "repeat_rate_30d", "repeat_rate_90d", "repeat_rate_180d", "repeat_rate_365d"},
    "risk_deciles.csv": {"risk_decile", "eligible_episodes", "inactivity_rate", "avg_predicted_risk", "avg_spend_180d_gbp", "risk_band"},
    "country_summary.csv": {"dimension", "market_group", "eligible_episodes", "inactive_90d", "inactivity_rate", "ci_95_low", "ci_95_high", "avg_spend_180d_gbp"},
    "feature_summary.csv": {"feature"},
}
FORBIDDEN = {"customer_id", "customerid", "customer_identifier", "invoice", "invoice_no", "transaction_id", "predicted_inactivity_probability", "email", "phone"}


def main() -> None:
    if not (PUBLIC / "metrics.json").is_file():
        raise FileNotFoundError("Run `uv run python scripts/run_pipeline.py` before artifact validation")
    metrics = json.loads((PUBLIC / "metrics.json").read_text(encoding="utf-8-sig"))
    test = metrics["locked_temporal_test"]["model"]
    if metrics["time_split"]["train_episodes"] <= 0 or metrics["time_split"]["test_episodes"] <= 0:
        raise ValueError("Temporal split has no training or test episodes")
    if len(metrics["time_split"]["test_months"]) < 3:
        raise ValueError("Locked test should cover at least three later months")
    if test["rows"] != metrics["time_split"]["test_episodes"]:
        raise ValueError("Test row counts do not reconcile")
    for filename, expected in EXPECTED.items():
        path = PUBLIC / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing public artifact: {filename}")
        frame = pd.read_csv(path)
        columns = {str(column).casefold() for column in frame.columns}
        missing = expected - columns
        if missing:
            raise ValueError(f"{filename} missing expected columns: {sorted(missing)}")
        forbidden = columns & FORBIDDEN
        if forbidden:
            raise ValueError(f"{filename} appears to contain customer-level fields: {sorted(forbidden)}")
        if frame.empty:
            raise ValueError(f"{filename} has no rows")
    segments = pd.read_csv(PUBLIC / "segment_performance.csv")
    if (segments["eligible_episodes"] < 50).any():
        raise ValueError("A public segment is below the minimum display threshold of 50 episodes")
    deciles = pd.read_csv(PUBLIC / "risk_deciles.csv")
    if deciles["risk_decile"].nunique() < 5:
        raise ValueError("Risk decile summary contains too few score bands")
    print("Public artifacts pass schema, temporal-split, minimum-group-size, and customer-field checks.")


if __name__ == "__main__":
    main()
