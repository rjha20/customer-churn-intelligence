# Deployment runbook

## Live hosted app

The [public dashboard](https://customer-churn-intelligence-fqhiky64jfjrosohfmmxme.streamlit.app/) is deployed from the [rjha20/customer-churn-intelligence](https://github.com/rjha20/customer-churn-intelligence) GitHub repository, branch `main`, entry point `dashboard/app.py`, with Python 3.12. The app has no API keys, database, or write endpoint. It loads only reviewed aggregate CSV/JSON files committed under `data/processed/public/`.

## Deploy or reconnect

1. Sign in to Streamlit Community Cloud with the GitHub account `rjha20`.
2. Choose **Create app** and select `rjha20/customer-churn-intelligence`, `main`, and `dashboard/app.py`.
3. Select Python 3.12 if the deployment form requests a Python version.
4. Deploy and verify the Streamlit app URL responds successfully and all dashboard tabs load.
5. For updates, publish reviewed aggregate artifacts and code to `main`; Community Cloud rebuilds from that commit. Check deployment logs if the build fails.

No secrets should be entered for this app. The app does not download the raw workbook during startup and is not a streaming inference service.

## Local preview

```powershell
uv sync
uv run streamlit run dashboard/app.py
```

## Refresh the data and model

```powershell
uv run python scripts/run_pipeline.py
uv run python scripts/validate_public_artifacts.py
```

Review the generated metrics, segment rows, model evaluation, and data vintage before publishing. `data/processed/local/` contains customer-level holdout rows and a fitted model; confirm it remains ignored. Do not publish raw transaction data, row-level scores, or credentials.

## Current service boundary

This is a public portfolio dashboard over a fixed reviewed snapshot. It does not ingest ongoing retail events, serve a real-time scoring API, write to a customer system, schedule outreach, or provide operational alerts. “Hosted” describes the web app, not an in-production retention workflow.
