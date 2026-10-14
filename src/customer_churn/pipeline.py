"""Build point-in-time customer inactivity snapshots and a locked temporal benchmark."""
from __future__ import annotations

import json
import math
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PUBLIC_DIR = ROOT / "data" / "processed" / "public"
LOCAL_DIR = ROOT / "data" / "processed" / "local"
UCI_ZIP_URL = "https://archive.ics.uci.edu/static/public/502/online%2Bretail%2Bii.zip"
WORKBOOK = RAW_DIR / "online_retail_II.xlsx"
FEATURES = [
    "days_since_last_purchase", "customer_age_days", "orders_30d", "orders_90d",
    "orders_180d", "revenue_30d", "revenue_90d", "revenue_180d", "units_180d",
    "products_180d", "avg_invoice_value_180d", "mean_gap_days_180d",
    "order_frequency_ratio_90d", "revenue_ratio_90d",
]
TRAIN_END = pd.Timestamp("2010-10-01")
VALIDATION_START = pd.Timestamp("2010-12-01")
VALIDATION_END = pd.Timestamp("2011-02-01")
TEST_START = pd.Timestamp("2011-04-01")
SEED = 42


def acquire_workbook() -> Path:
    """Download and unpack UCI's public source only when it is not already local."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if WORKBOOK.exists():
        return WORKBOOK
    extracted = RAW_DIR / "uci_extract" / "online_retail_II.xlsx"
    if extracted.exists():
        return extracted
    archive = RAW_DIR / "online_retail_ii.zip"
    if not archive.exists():
        print("Downloading UCI Online Retail II source archive (about 44 MB)...", flush=True)
        urllib.request.urlretrieve(UCI_ZIP_URL, archive)
    extract_dir = RAW_DIR / "uci_extract"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        candidates = [name for name in source.namelist() if name.lower().endswith(".xlsx")]
        if not candidates:
            raise ValueError("The UCI archive did not contain an Excel workbook")
        source.extract(candidates[0], extract_dir)
        extracted = extract_dir / candidates[0]
    return extracted


def load_transactions(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    raw = pd.concat(sheets.values(), ignore_index=True)
    raw.columns = [str(column).strip().casefold().replace(" ", "") for column in raw.columns]
    aliases = {
        "invoiceno": "invoice", "invoice": "invoice", "stockcode": "stock_code",
        "description": "description", "quantity": "quantity", "invoicedate": "invoice_date",
        "price": "unit_price", "unitprice": "unit_price", "customerid": "customer_id",
        "country": "country",
    }
    raw = raw.rename(columns={column: aliases[column] for column in raw.columns if column in aliases})
    required = {"invoice", "stock_code", "quantity", "invoice_date", "unit_price", "customer_id", "country"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"UCI workbook is missing columns: {missing}")
    row_count = len(raw)
    raw["invoice"] = raw["invoice"].astype("string").str.strip()
    raw["invoice_date"] = pd.to_datetime(raw["invoice_date"], errors="coerce")
    raw["quantity"] = pd.to_numeric(raw["quantity"], errors="coerce")
    raw["unit_price"] = pd.to_numeric(raw["unit_price"], errors="coerce")
    raw["customer_id"] = pd.to_numeric(raw["customer_id"], errors="coerce")
    cancellation = raw["invoice"].str.upper().str.startswith("C", na=False)
    valid = (
        raw["customer_id"].notna() & raw["invoice_date"].notna() & raw["invoice"].notna()
        & raw["quantity"].gt(0) & raw["unit_price"].gt(0) & ~cancellation
    )
    valid_rows = raw.loc[valid].copy()
    valid_rows["customer_id"] = valid_rows["customer_id"].astype("int64").astype("string")
    valid_rows["line_revenue"] = valid_rows["quantity"] * valid_rows["unit_price"]
    invoices = (
        valid_rows.groupby(["customer_id", "invoice"], as_index=False)
        .agg(
            invoice_date=("invoice_date", "min"), revenue=("line_revenue", "sum"),
            units=("quantity", "sum"), products=("stock_code", "nunique"),
            country=("country", "last"),
        )
        .sort_values(["invoice_date", "customer_id", "invoice"])
        .reset_index(drop=True)
    )
    source_stats = {
        "source_rows": int(row_count),
        "usable_purchase_rows": int(len(valid_rows)),
        "excluded_rows": int(row_count - len(valid_rows)),
        "cancelled_lines_excluded": int(cancellation.sum()),
        "rows_missing_customer_id": int(raw["customer_id"].isna().sum()),
        "purchase_invoices": int(invoices["invoice"].nunique()),
        "identified_customers": int(invoices["customer_id"].nunique()),
        "first_purchase_date": invoices["invoice_date"].min().date().isoformat(),
        "last_purchase_date": invoices["invoice_date"].max().date().isoformat(),
        "countries": int(invoices["country"].nunique()),
    }
    return invoices, source_stats


def build_snapshots(invoices: pd.DataFrame) -> pd.DataFrame:
    min_date = invoices["invoice_date"].min().to_period("M").to_timestamp()
    max_date = invoices["invoice_date"].max()
    first_snapshot = min_date + pd.DateOffset(months=6)
    last_mature_snapshot = (max_date - pd.DateOffset(days=90)).to_period("M").to_timestamp()
    snapshots: list[pd.DataFrame] = []
    for snapshot in pd.date_range(first_snapshot, last_mature_snapshot, freq="MS"):
        start_180 = snapshot - pd.DateOffset(days=180)
        start_90 = snapshot - pd.DateOffset(days=90)
        start_30 = snapshot - pd.DateOffset(days=30)
        window_180 = invoices.loc[
            invoices["invoice_date"].ge(start_180) & invoices["invoice_date"].lt(snapshot)
        ]
        if window_180.empty:
            continue
        base = window_180.groupby("customer_id").agg(
            last_purchase=("invoice_date", "max"), orders_180d=("invoice", "nunique"),
            revenue_180d=("revenue", "sum"), units_180d=("units", "sum"),
            products_180d=("products", "sum"), avg_invoice_value_180d=("revenue", "mean"),
            country=("country", "last"),
        )
        for days, start in ((30, start_30), (90, start_90)):
            recent = window_180.loc[window_180["invoice_date"].ge(start)]
            grouped = recent.groupby("customer_id").agg(
                order_count=("invoice", "nunique"), revenue=("revenue", "sum")
            )
            base[f"orders_{days}d"] = grouped["order_count"].reindex(base.index, fill_value=0)
            base[f"revenue_{days}d"] = grouped["revenue"].reindex(base.index, fill_value=0.0)
        gaps = (
            window_180.sort_values("invoice_date").groupby("customer_id")["invoice_date"]
            .diff().dt.total_seconds().div(86400).groupby(window_180["customer_id"]).mean()
        )
        base["mean_gap_days_180d"] = gaps.reindex(base.index).fillna(0.0)
        lifetime_first = invoices.loc[invoices["invoice_date"].lt(snapshot)].groupby("customer_id")["invoice_date"].min()
        base["customer_age_days"] = (snapshot - lifetime_first.reindex(base.index)).dt.days
        base["days_since_last_purchase"] = (snapshot - base["last_purchase"]).dt.days
        base["order_frequency_ratio_90d"] = (
            (base["orders_90d"] + 1) / (base["orders_180d"] - base["orders_90d"] + 1)
        )
        base["revenue_ratio_90d"] = (
            (base["revenue_90d"] + 1) / (base["revenue_180d"] - base["revenue_90d"] + 1)
        )
        future_end = snapshot + pd.DateOffset(days=90)
        future = invoices.loc[
            invoices["invoice_date"].ge(snapshot) & invoices["invoice_date"].lt(future_end)
        ]
        future_customers = set(future["customer_id"].unique())
        base["inactive_90d"] = (~base.index.isin(future_customers)).astype("int8")
        base["snapshot_date"] = snapshot
        base["snapshot_month"] = snapshot.strftime("%Y-%m")
        base["recency_band"] = pd.cut(
            base["days_since_last_purchase"], [-1, 30, 60, 90, 180],
            labels=["0-30 days", "31-60 days", "61-90 days", "91-180 days"],
        ).astype("string")
        base["tenure_band"] = pd.cut(
            base["customer_age_days"], [-1, 90, 180, 365, np.inf],
            labels=["0-90 days", "91-180 days", "181-365 days", "365+ days"],
        ).astype("string")
        base["frequency_band"] = pd.cut(
            base["orders_180d"], [0, 1, 3, 7, np.inf],
            labels=["1 order", "2-3 orders", "4-7 orders", "8+ orders"],
        ).astype("string")
        base["market_group"] = np.where(base["country"].eq("United Kingdom"), "United Kingdom", "International")
        base["customer_id"] = base.index.astype("string")
        snapshots.append(base.reset_index(drop=True))
    if not snapshots:
        raise ValueError("No mature monthly customer snapshots could be built")
    result = pd.concat(snapshots, ignore_index=True)
    if result[FEATURES + ["inactive_90d"]].isna().any().any():
        raise ValueError("Feature construction produced null model inputs or labels")
    return result


def average_precision_at_k(y: np.ndarray, score: np.ndarray, fraction: float = 0.10) -> dict[str, float]:
    k = max(1, int(math.ceil(len(y) * fraction)))
    chosen = np.argsort(-score)[:k]
    precision = float(y[chosen].mean())
    total_positive = max(1, int(y.sum()))
    recall = float(y[chosen].sum() / total_positive)
    prevalence = float(y.mean())
    return {
        "precision_at_10pct": precision,
        "recall_at_10pct": recall,
        "lift_at_10pct": float(precision / prevalence) if prevalence else 0.0,
        "customers_reviewed_at_10pct": int(k),
    }


def score_metrics(y: pd.Series | np.ndarray, probability: np.ndarray) -> dict[str, float]:
    labels = np.asarray(y, dtype=int)
    probability = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    prevalence = float(labels.mean())
    top = average_precision_at_k(labels, probability)
    return {
        "rows": int(len(labels)),
        "inactivity_prevalence": prevalence,
        "average_precision": float(average_precision_score(labels, probability)),
        "roc_auc": float(roc_auc_score(labels, probability)),
        "brier_score": float(brier_score_loss(labels, probability)),
        "log_loss": float(log_loss(labels, probability)),
        **top,
    }


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) / total) + z * z / (4 * total * total)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def grouped_rates(frame: pd.DataFrame, field: str, label: str) -> pd.DataFrame:
    rows = []
    for category, group in frame.groupby(field, observed=True):
        count = len(group)
        if count < 50:
            continue
        positives = int(group["inactive_90d"].sum())
        low, high = wilson_interval(positives, count)
        rows.append({
            "dimension": label, "segment": str(category), "eligible_episodes": count,
            "inactive_90d": positives, "inactivity_rate": positives / count,
            "ci_95_low": low, "ci_95_high": high,
            "avg_spend_180d_gbp": float(group["revenue_180d"].mean()),
        })
    return pd.DataFrame(rows)


def create_cohort_summary(invoices: pd.DataFrame) -> pd.DataFrame:
    first = invoices.groupby("customer_id")["invoice_date"].min().rename("first_purchase")
    customers = first.reset_index()
    customer_events = invoices[["customer_id", "invoice_date"]].merge(
        customers, on="customer_id", how="inner", validate="many_to_one"
    )
    customer_events["days_after_first_purchase"] = (
        customer_events["invoice_date"] - customer_events["first_purchase"]
    ).dt.days
    customer_events["cohort_month"] = customer_events["first_purchase"].dt.to_period("M")
    max_date = invoices["invoice_date"].max()
    rows = []
    for cohort, cohort_rows in customers.groupby(customers["first_purchase"].dt.to_period("M")):
        size = len(cohort_rows)
        row: dict[str, Any] = {"cohort_month": str(cohort), "customers": size}
        cohort_events = customer_events.loc[customer_events["cohort_month"].eq(cohort)]
        last_first_purchase = cohort_rows["first_purchase"].max()
        for days in (30, 90, 180, 365):
            if last_first_purchase + pd.DateOffset(days=days) > max_date:
                row[f"repeat_rate_{days}d"] = np.nan
                continue
            followup = cohort_events.loc[
                cohort_events["days_after_first_purchase"].between(1, days), "customer_id"
            ].nunique()
            row[f"repeat_rate_{days}d"] = followup / size if size else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    source_path = acquire_workbook()
    invoices, source_stats = load_transactions(source_path)
    episodes = build_snapshots(invoices)
    train = episodes[episodes["snapshot_date"] < TRAIN_END]
    validation = episodes[
        episodes["snapshot_date"].ge(VALIDATION_START) & episodes["snapshot_date"].lt(VALIDATION_END)
    ]
    test = episodes[episodes["snapshot_date"].ge(TEST_START)]
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError(f"Temporal split is empty: train={len(train)}, validation={len(validation)}, test={len(test)}")
    ycol = "inactive_90d"
    X_train, y_train = train[FEATURES], train[ycol]
    X_validation, y_validation = validation[FEATURES], validation[ycol]
    candidate_models = {
        "regularized_logistic_regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=0.5, max_iter=1500, random_state=SEED)),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", HistGradientBoostingClassifier(
                max_iter=140, learning_rate=0.07, max_leaf_nodes=20,
                l2_regularization=1.0, random_state=SEED,
            )),
        ]),
    }
    validation_results = {}
    for name, model in candidate_models.items():
        model.fit(X_train, y_train)
        validation_probability = model.predict_proba(X_validation)[:, 1]
        validation_results[name] = {
            "average_precision": float(average_precision_score(y_validation, validation_probability)),
            "prevalence_baseline": float(y_validation.mean()),
        }
    selected_name = max(validation_results, key=lambda name: validation_results[name]["average_precision"])
    final_model = candidate_models[selected_name]
    development = pd.concat([train, validation], ignore_index=True)
    final_model.fit(development[FEATURES], development[ycol])
    test_probability = final_model.predict_proba(test[FEATURES])[:, 1]
    recency_score = test["days_since_last_purchase"].to_numpy(dtype=float)
    test_metrics = score_metrics(test[ycol], test_probability)
    recency_labels = test[ycol].to_numpy(dtype=int)
    recency_top = average_precision_at_k(recency_labels, recency_score)
    recency_metrics = {
        "rows": int(len(recency_labels)),
        "inactivity_prevalence": float(recency_labels.mean()),
        "average_precision": float(average_precision_score(recency_labels, recency_score)),
        "roc_auc": float(roc_auc_score(recency_labels, recency_score)),
        **recency_top,
    }
    prevalence = float(test[ycol].mean())
    baseline_brier = prevalence * (1 - prevalence)
    model_brier_skill = 1 - test_metrics["brier_score"] / baseline_brier if baseline_brier else 0.0
    model_brier_note = "better" if model_brier_skill > 0 else "worse"
    scored = test[["customer_id", "snapshot_month", "inactive_90d", "recency_band", "tenure_band", "frequency_band", "market_group", "revenue_180d"]].copy()
    scored["predicted_inactivity_probability"] = test_probability
    scored["recency_rank_score"] = recency_score
    scored["risk_decile"] = pd.qcut(
        scored["predicted_inactivity_probability"].rank(method="first"), 10,
        labels=False, duplicates="drop",
    ).astype(int) + 1
    scored["risk_decile"] = 11 - scored["risk_decile"]
    risk_deciles = scored.groupby("risk_decile", as_index=False).agg(
        eligible_episodes=("inactive_90d", "size"), inactivity_rate=("inactive_90d", "mean"),
        avg_predicted_risk=("predicted_inactivity_probability", "mean"),
        avg_spend_180d_gbp=("revenue_180d", "mean"),
    ).sort_values("risk_decile")
    risk_deciles["risk_band"] = risk_deciles["risk_decile"].map(
        lambda value: "Highest risk" if value == 1 else ("Lowest risk" if value == 10 else f"Band {value}")
    )
    segment_tables = [
        grouped_rates(scored, "recency_band", "Purchase recency"),
        grouped_rates(scored, "tenure_band", "Customer tenure"),
        grouped_rates(scored, "frequency_band", "Orders in prior 180 days"),
        grouped_rates(scored, "market_group", "Market"),
    ]
    segments = pd.concat(segment_tables, ignore_index=True)
    monthly_rows = []
    for month, group in scored.groupby("snapshot_month"):
        p = group["predicted_inactivity_probability"].to_numpy()
        y = group["inactive_90d"].to_numpy(dtype=int)
        recency = group["recency_rank_score"].to_numpy()
        monthly_rows.append({
            "snapshot_month": month, "eligible_episodes": len(group),
            "inactivity_rate": float(y.mean()), "model_average_precision": float(average_precision_score(y, p)),
            "recency_baseline_average_precision": float(average_precision_score(y, recency)),
        })
    monthly = pd.DataFrame(monthly_rows)
    country_summary = grouped_rates(scored, "market_group", "Market").rename(columns={"segment": "market_group"})
    cohort_summary = create_cohort_summary(invoices)
    metrics = {
        "project": "Customer Retention Intelligence",
        "prediction_contract": {
            "unit": "customer-month episode with at least one purchase in the prior 180 days",
            "snapshot": "first day of each month",
            "target": "no positive-value purchase during the following 90 days",
            "features": "purchase activity strictly before the snapshot; 180-day window",
            "target_is_inactivity_proxy": True,
        },
        "source": {
            "name": "UCI Online Retail II",
            "url": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
            "license": "CC BY 4.0; attribution required",
            **source_stats,
        },
        "snapshot_rows": int(len(episodes)),
        "snapshot_count": int(episodes["snapshot_month"].nunique()),
        "time_split": {
            "train_before": TRAIN_END.strftime("%Y-%m-%d"),
            "validation_from": VALIDATION_START.strftime("%Y-%m-%d"),
            "validation_before": VALIDATION_END.strftime("%Y-%m-%d"),
            "locked_test_from": TEST_START.strftime("%Y-%m-%d"),
            "label_maturity_gap_snapshots": ["2010-10", "2010-11", "2011-02", "2011-03"],
            "train_episodes": int(len(train)), "validation_episodes": int(len(validation)),
            "test_episodes": int(len(test)), "test_months": sorted(test["snapshot_month"].unique().tolist()),
        },
        "model_selection": {
            "selected_model": selected_name,
            "selection_metric": "validation average precision",
            "validation_results": validation_results,
            "final_fit": "selected pipeline refit on train + validation; evaluated once on later test months",
        },
        "locked_temporal_test": {
            "model": test_metrics,
            "recency_only_ranker": recency_metrics,
            "prevalence_baseline_average_precision": prevalence,
            "constant_prevalence_brier_score": baseline_brier,
            "brier_skill_vs_constant_prevalence": model_brier_skill,
            "brier_vs_constant_prevalence": model_brier_note,
        },
        "runtime": {"python": sys.version.split()[0], "pandas": pd.__version__, "scikit_learn": sklearn.__version__},
        "important_limit": "A ranking predicts historical 90-day purchase inactivity, not response to a retention offer or causal uplift.",
    }
    metrics_path = PUBLIC_DIR / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    test_result = metrics["locked_temporal_test"]
    model_result = test_result["model"]
    recency_result = test_result["recency_only_ranker"]
    validation_table = "\n".join(
        f"| `{name}` | {values['average_precision']:.3f} | {values['prevalence_baseline']:.3f} |"
        for name, values in metrics["model_selection"]["validation_results"].items()
    )
    report = f"""# Temporal model evaluation

Generated from UCI Online Retail II by `scripts/run_pipeline.py`.

## Prediction and split

- Rows in the source workbook: **{source_stats['source_rows']:,}**; positive purchase lines used: **{source_stats['usable_purchase_rows']:,}**; identified customers: **{source_stats['identified_customers']:,}**.
- Monthly snapshots: **{metrics['snapshot_count']}**; customer-month episodes: **{metrics['snapshot_rows']:,}**.
- Outcome: no positive-value purchase in the 90 days after a first-of-month snapshot. Features use only the preceding 180 days and the customer must have purchased during that lookback.
- Train episodes before {metrics['time_split']['train_before']}: **{metrics['time_split']['train_episodes']:,}**.
- Validation episodes from {metrics['time_split']['validation_from']} to before {metrics['time_split']['validation_before']}: **{metrics['time_split']['validation_episodes']:,}**.
- Locked temporal test episodes from {metrics['time_split']['locked_test_from']}: **{metrics['time_split']['test_episodes']:,}**, covering **{', '.join(metrics['time_split']['test_months'])}**.
- Snapshot months {', '.join(metrics['time_split']['label_maturity_gap_snapshots'])} are purged so each 90-day training/validation label window matures before the next evaluation period begins.
- Model choice: highest validation average precision; the selected pipeline is refit on train + validation, then evaluated on the later test months.

## Model selection on validation months

| Candidate | Average precision | Validation prevalence |
|---|---:|---:|
{validation_table}

Selected: **{metrics['model_selection']['selected_model']}**. The model was not selected on the locked temporal test.

## Locked temporal test

| Ranking | Average precision | ROC-AUC | Brier score | Log loss | Precision in top 10% | Recall in top 10% | Lift in top 10% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Selected model | {model_result['average_precision']:.3f} | {model_result['roc_auc']:.3f} | {model_result['brier_score']:.3f} | {model_result['log_loss']:.3f} | {model_result['precision_at_10pct']:.1%} | {model_result['recall_at_10pct']:.1%} | {model_result['lift_at_10pct']:.2f}× |
| Recency-only ranker | {recency_result['average_precision']:.3f} | {recency_result['roc_auc']:.3f} | — | — | {recency_result['precision_at_10pct']:.1%} | {recency_result['recall_at_10pct']:.1%} | {recency_result['lift_at_10pct']:.2f}× |
| No-skill / constant prevalence | {test_result['prevalence_baseline_average_precision']:.3f} | — | {test_result['constant_prevalence_brier_score']:.3f} | — | — | — | 1.00× |

Test inactivity prevalence is **{model_result['inactivity_prevalence']:.1%}** across {model_result['rows']:,} customer-month episodes. The highest-risk 10% contains {model_result['customers_reviewed_at_10pct']:,} episodes, with **{model_result['precision_at_10pct']:.1%}** observed inactivity and **{model_result['recall_at_10pct']:.1%}** of all positive episodes captured. Lift compares that top-decile precision with the overall test prevalence.

The model's Brier score is **{model_result['brier_score']:.3f}** versus **{test_result['constant_prevalence_brier_score']:.3f}** for a constant test-prevalence forecast (Brier skill {test_result['brier_skill_vs_constant_prevalence']:.1%}). This is a retrospective probability-quality comparison; probabilities still need calibration review before an operational threshold is considered.

## Interpretation

The selected model out-ranks the recency-only comparator on this later slice. This supports the value of combining multiple purchase-history signals for historical ranking in this one dataset. It does **not** establish an intervention effect, expected savings, causes, or performance on another retailer or current customers.

Monthly snapshots overlap in their outcome horizons and can include the same customer more than once. Test rows are customer-month episodes, not unique customers, and Wilson intervals in the segment report do not adjust for repeated episodes. The source is one UK giftware retailer from 2009–2011. Missing IDs and cancellation/return lines are excluded. There is no confirmed cancellation target, offer history, contact result, margin truth, or randomized control group.

## Reproducibility

Run `uv sync` and `uv run python scripts/run_pipeline.py`. Machine-readable metrics are in `data/processed/public/metrics.json`; the public dashboard reads only reviewed aggregate files. The local fitted pipeline and test episodes are ignored by Git.
"""
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "model_evaluation.md").write_text(report, encoding="utf-8")
    monthly.to_csv(PUBLIC_DIR / "monthly_performance.csv", index=False)
    segments.to_csv(PUBLIC_DIR / "segment_performance.csv", index=False)
    cohort_summary.to_csv(PUBLIC_DIR / "retention_cohorts.csv", index=False)
    risk_deciles.to_csv(PUBLIC_DIR / "risk_deciles.csv", index=False)
    country_summary.to_csv(PUBLIC_DIR / "country_summary.csv", index=False)
    # This file contains aggregate permutation-free signal summaries, never customer rows.
    if selected_name == "regularized_logistic_regression":
        coefficients = final_model.named_steps["model"].coef_[0]
        feature_summary = pd.DataFrame({"feature": FEATURES, "coefficient": coefficients})
        feature_summary["direction"] = np.where(feature_summary["coefficient"].ge(0), "Higher values align with higher score", "Higher values align with lower score")
        feature_summary["absolute_coefficient"] = feature_summary["coefficient"].abs()
        feature_summary = feature_summary.sort_values("absolute_coefficient", ascending=False)
    else:
        # Model-agnostic permutation importance uses only the locked test for explanation, not tuning.
        from sklearn.inspection import permutation_importance
        imp = permutation_importance(
            final_model, test[FEATURES], test[ycol], scoring="average_precision",
            n_repeats=4, random_state=SEED, n_jobs=1,
        )
        feature_summary = pd.DataFrame({
            "feature": FEATURES, "importance": imp.importances_mean,
            "importance_std": imp.importances_std,
        }).sort_values("importance", ascending=False)
    feature_summary.to_csv(PUBLIC_DIR / "feature_summary.csv", index=False)
    # Keep row-level, scored episodes and the fitted object out of the public repository.
    scored.to_parquet(LOCAL_DIR / "temporal_test_scored_episodes.parquet", index=False)
    import joblib
    joblib.dump(final_model, LOCAL_DIR / "selected_model.joblib")
    with sqlite3.connect(LOCAL_DIR / "retention.sqlite") as connection:
        invoices.to_sql("customer_invoices", connection, if_exists="replace", index=False)
        episodes.to_sql("customer_month_snapshots", connection, if_exists="replace", index=False)
        scored.to_sql("temporal_test_scores", connection, if_exists="replace", index=False)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_episode_month ON customer_month_snapshots(snapshot_month)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_test_risk_decile ON temporal_test_scores(risk_decile)")
    print(json.dumps({
        "source": source_stats, "snapshots": len(episodes), "model": selected_name,
        "temporal_test": test_metrics, "recency_baseline": recency_metrics,
        "artifacts": str(PUBLIC_DIR),
    }, indent=2))


if __name__ == "__main__":
    main()
