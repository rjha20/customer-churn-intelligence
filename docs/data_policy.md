# Data policy and source notes

## Public source

The project uses [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), a historical transaction dataset described by UCI as a real two-year dataset for one UK-based online retailer. UCI lists the work under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Cite: Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D.

The source spans 1 December 2009 through 9 December 2011. The data contains customer IDs, but the hosted app does not display or publish customer-level records or predictions.

## Local handling

- `data/raw/` contains the downloaded source archive and workbook and is excluded from Git.
- `data/processed/local/` contains row-level holdout scores and a fitted model and is excluded from Git.
- Only reviewed aggregate files under `data/processed/public/` are published. These contain snapshot-month metrics, minimum-size segment rates, cohort summaries, score-decile summaries, and model-level feature signals.
- Raw transaction rows are never read by the deployed Streamlit app.
- Do not add customer identifiers, exact per-customer scores, secrets, or unaggregated source rows to public artifacts.

## Filters and exclusions

Purchase episodes require a numeric customer ID, a valid date and invoice, positive quantity, positive unit price, and a non-cancellation invoice. Cancellation/return lines, non-positive rows, and rows without customer IDs do not count as completed purchase events. The aggregate `excluded_rows` count is included in metrics for auditability.

## Rebuild source

Run `uv run python scripts/run_pipeline.py`. If no local workbook is present, the script downloads the public UCI ZIP archive and extracts the Excel workbook into `data/raw/`. The pipeline writes the reviewed aggregate outputs and local-only row-level/model artifacts.
