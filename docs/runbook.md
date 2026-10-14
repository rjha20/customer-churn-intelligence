# Operating runbook

## First run

1. Install Python 3.12 and `uv`.
2. From the repository root run `uv sync`.
3. Run `uv run python scripts/run_pipeline.py`. The pipeline downloads UCI Online Retail II if a local workbook is not present, validates required columns, cleans purchase events, builds monthly snapshots, compares models using time-ordered splits, and writes aggregate public outputs plus local-only row-level/model artifacts.
4. Run `uv run python scripts/validate_public_artifacts.py` to confirm the published files are aggregate-only and internally consistent.
5. Preview `uv run streamlit run dashboard/app.py`.

## Routine refresh

UCI Online Retail II is a fixed historical source; there is no upstream refresh schedule. Rebuild when changing source or pipeline code. Record the source vintage, check the temporal test and baseline comparisons, review privacy/aggregation rules, and update the model card before publishing.

## Expected outputs

- `data/processed/public/metrics.json`
- `data/processed/public/monthly_performance.csv`
- `data/processed/public/segment_performance.csv`
- `data/processed/public/retention_cohorts.csv`
- `data/processed/public/risk_deciles.csv`
- `data/processed/public/country_summary.csv`
- `data/processed/public/feature_summary.csv`
- `data/processed/local/temporal_test_scored_episodes.parquet` (private local artifact)
- `data/processed/local/selected_model.joblib` (private local artifact)
- `data/processed/local/retention.sqlite` (private local row-level analytics mart for SQL practice)

## Failure handling

- Missing workbook: check network access to UCI or put the UCI workbook under `data/raw/online_retail_II.xlsx`.
- Workbook schema changes: stop the run and inspect source columns; do not silently infer new target semantics.
- Empty temporal split or missing feature rows: treat as a pipeline failure and investigate before publishing.
- Metrics regress or calibration underperforms prevalence: report it, keep the baseline comparison visible, and do not claim useful probability calibration.
- Cloud build fails: inspect Streamlit Community Cloud logs, correct the dependency/app issue in a reviewed commit, and redeploy.

## SQL review

After a successful pipeline build, run the examples in `sql/retention_review.sql` against the local `data/processed/local/retention.sqlite`. The database contains customer identifiers and episode rows, so keep it local and gitignored. The hosted app never reads this database.
