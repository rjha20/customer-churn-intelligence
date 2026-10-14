# Customer Retention Intelligence

A reproducible customer analytics portfolio project that ranks **historical 90-day purchase inactivity risk** and helps a retention team reason about investigation capacity. It combines transactional data engineering, descriptive statistics, temporal ML validation, model governance, an interactive dashboard, and an assumptions-based decision scenario.

> **Decision boundary:** This is a public portfolio prototype built from one historical UK giftware retailer (2009–2011). “Churn” is defined as no positive-value purchase in the next 90 days; it is not verified cancellation. The model does not estimate campaign response, causal uplift, or ROI, and it does not represent Amex/cardmember data.

## Project status

- Reproducible local pipeline: implemented.
- Time-aware holdout and aggregate-only Streamlit dashboard: implemented.
- Publication target: public `rjha20/customer-churn-intelligence` repository with a Streamlit Community Cloud app. The exact URLs are added here after publication.

## Dashboard

The app presents later-period model performance, purchase-recency and tenure segments, repeat-purchase cohorts, a model review, and an editable break-even scenario. The hosted app reads reviewed grouped metrics only. Raw transactions, row-level scores, and fitted model weights are excluded from Git.

## Results

Generated from UCI Online Retail II by `scripts/run_pipeline.py` and stored in `data/processed/public/metrics.json`.

| Measure | Result |
|---|---:|
| Source transaction rows | 1,067,371 |
| Historical customer-month episodes | 48,079 across 16 snapshots |
| Selected model | Regularized logistic regression |
| Later-period test average precision | 0.716 |
| No-skill prevalence AP / recency-only AP | 0.486 / 0.652 |
| Precision / recall / lift in highest-risk 10% | 81.2% / 16.7% / 1.67× |
| Brier score vs constant-prevalence forecast | 0.204 vs 0.250 (18.5% Brier skill) |

The locked temporal test contains 17,279 customer-month episodes from April through September 2011. Training and validation windows are separated by label-maturity gaps so each 90-day outcome is fully observed before the next scoring period. Use `reports/model_evaluation.md` for exact split dates, candidate comparisons, metric values, calibration diagnostics, and interpretation. The top-decile metric is a historical ranking/capacity measure, not savings from a retention campaign.

## Data source and attribution

The source is Chen, D. (2012), [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), UCI Machine Learning Repository, [DOI 10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). UCI describes a real two-year transaction set from a UK online retailer, with many wholesale customers. UCI lists the dataset under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); attribution is included here and in the app. The source covers 1 December 2009 through 9 December 2011.

The source workbook is downloaded into `data/raw/` when needed and is not committed. The pipeline excludes rows without customer IDs, cancellation invoices, and non-positive quantity/price lines from purchase events. Check the data policy for exact handling.

## Reproduce from source

Requirements: Windows, macOS, or Linux; Python 3.12; network access to UCI on first run; `uv`.

```powershell
uv sync
uv run python scripts/run_pipeline.py
uv run python scripts/validate_public_artifacts.py
uv run python scripts/run_sql_review.py
uv run streamlit run dashboard/app.py
```

The first command installs the locked environment. The pipeline fetches and extracts the UCI workbook if absent, builds point-in-time monthly feature snapshots, selects between two model families using validation months, refits on development months, evaluates once on later periods, and writes aggregate dashboard data. The full raw file and row-level test outputs remain local and gitignored.

## Prediction contract

- **Unit:** customer-month episode, restricted to customers with at least one positive purchase in the previous 180 days.
- **Snapshot:** first calendar day of each month.
- **Features:** recency, order frequency, gross spend, invoice value, units/products, customer age, and purchase gaps, all computed strictly before the snapshot.
- **Outcome:** no positive purchase during the following 90 days.
- **Model selection:** validation average precision across earlier months; selected model refit on train + validation before the later temporal holdout.
- **Comparators:** test prevalence baseline and recency-only ranking.
- **Capacity metrics:** top-decile precision, recall, and lift; probability quality uses Brier score and log loss with a constant-prevalence comparison.

The monthly snapshots overlap in their 90-day outcome windows and may include the same customer at different dates. This resembles repeated batch monitoring but means episode rows are not independent. The temporal test assesses later months from this same retailer only.

## Repository map

```text
customer-churn-intelligence/
├── dashboard/app.py
├── data/
│   ├── raw/                         # ignored: downloaded UCI source
│   └── processed/
│       ├── public/                  # reviewed aggregate app artifacts
│       └── local/                   # ignored: test scores and fitted model
├── docs/
│   ├── data_policy.md
│   ├── deployment.md
│   ├── model_card.md
│   └── runbook.md
├── reports/
│   ├── data_quality.md
│   ├── final_case_study.md
│   └── model_evaluation.md
├── scripts/
│   ├── run_pipeline.py
│   ├── run_sql_review.py
│   └── validate_public_artifacts.py
├── sql/retention_review.sql
├── src/customer_churn/pipeline.py
├── PROJECT_PLAN.md
├── pyproject.toml
└── requirements.txt
```

## Deployment

The app is designed for Streamlit Community Cloud, with `dashboard/app.py` as the entry point. It has no credentials, database, live transaction feed, scoring API, or write endpoint. After publication, the exact public repo and live app URL will appear below. See [`docs/deployment.md`](docs/deployment.md).

## Model and data governance

- [Model card](docs/model_card.md): intended use, temporal evaluation design, limits, and required controls before any operational pilot.
- [Data policy](docs/data_policy.md): UCI attribution, local-only data, filters, and aggregate-publication rules.
- [Operating runbook](docs/runbook.md): rebuild and failure handling.
- [Full project plan](PROJECT_PLAN.md): end-to-end scope and completion criteria.

## Amex relevance and resume framing

This project demonstrates transferable methods used in customer analytics and risk decision support: behavioral feature construction, SQL segment analysis, imbalanced ranking, temporal holdout validation, capacity-based prioritization, cost-sensitivity, and model governance. It is **not** a credit-risk, fraud, card-closure, or financial-services model.

A truthful resume bullet after reviewing the generated metrics:

> Built a reproducible retention analytics pipeline on 1.07M historical retail transactions, engineered point-in-time customer-month features for a 90-day repeat-purchase inactivity proxy, and compared logistic regression and gradient boosting on a later-period holdout using average precision, top-decile lift, calibration, and a recency baseline; deployed an aggregate-only Streamlit dashboard.

Replace generic metric references with the actual values in `reports/model_evaluation.md`; include the baseline so the result is interpretable. Do not claim prevented churn, revenue saved, or campaign uplift.

## Scope limits

The dataset is old and comes from one giftware/wholesale-heavy retailer. It does not include a verified churn label, recent customer behavior, offer/contact history, intervention outcome, cost/margin truth, current market conditions, or Amex data. Hosting this app does not turn the model into a production customer-retention system. Any business pilot would require current approved data, outcome maturity, monitoring, governance, and a randomized holdout experiment.
