# Project plan: from blank folder to hosted demo

## Phase 1 — Frame the decision

Define the use case as prioritizing historical customer groups for retention investigation. Set the unit (customer-month), decision time (month start), feature lookback (180 days), target horizon (90 days), and stop conditions. Do not call inactivity a confirmed cancellation.

## Phase 2 — Source and govern data

Acquire UCI Online Retail II under CC BY 4.0, record attribution and date range, and exclude the raw source from Git. Audit missing customer IDs, cancellations, returns, quantities, prices, and dates. Publish only aggregate artifacts; retain row-level test scores and fitted weights locally.

## Phase 3 — Build point-in-time features

Aggregate invoices, then construct monthly snapshots using purchases before the snapshot only. Include purchase recency, transaction frequency, gross spend, order size, customer age, and historical gaps. Exclude identifiers and future transactions. Label no positive-value purchase in the next 90 days; drop immature snapshots.

## Phase 4 — Analyze and model

Build repeat-purchase cohorts and descriptive segment rates with confidence intervals. Compare a constant-prevalence baseline, recency-only ranking, regularized logistic regression, and histogram gradient boosting. Select on validation months, refit on development history, and evaluate once on later months. Report average precision, ROC-AUC, Brier/log loss, top-decile lift, capacity metrics, and subgroup slices.

## Phase 5 — Decision support

Build an interactive Streamlit dashboard that communicates data vintage and decision limits before results. Include an assumptions-based break-even scenario tool, with editable costs and contribution assumptions, while stating that no treatment data exists to estimate uplift or ROI.

## Phase 6 — Publish and operate

Run the reproducible pipeline and aggregate-artifact guard. Review reports and exact Git diff. Publish code and safe aggregate files to the public `rjha20` repository. Deploy `dashboard/app.py` on Streamlit Community Cloud. Verify the live route and all tabs. Record deployment evidence and remaining boundaries.

## Completion criteria

- Reproducible build from public source, pinned dependencies, and documented commands.
- Point-in-time features and a locked temporal evaluation with explicit baselines.
- Public app uses no row-level data, API keys, or write endpoints.
- Model card, data policy, evaluation report, deployment runbook, project README, and case study agree on target and limitations.
- Repository/app are under the `rjha20` account, with no ERP checkout changes.
