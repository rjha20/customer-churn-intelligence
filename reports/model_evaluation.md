# Temporal model evaluation

Generated from UCI Online Retail II by `scripts/run_pipeline.py`.

## Prediction and split

- Rows in the source workbook: **1,067,371**; positive purchase lines used: **805,549**; identified customers: **5,878**.
- Monthly snapshots: **16**; customer-month episodes: **48,079**.
- Outcome: no positive-value purchase in the 90 days after a first-of-month snapshot. Features use only the preceding 180 days and the customer must have purchased during that lookback.
- Train episodes before 2010-10-01: **11,079**.
- Validation episodes from 2010-12-01 to before 2011-02-01: **6,894**.
- Locked temporal test episodes from 2011-04-01: **17,279**, covering **2011-04, 2011-05, 2011-06, 2011-07, 2011-08, 2011-09**.
- Snapshot months 2010-10, 2010-11, 2011-02, 2011-03 are purged so each 90-day training/validation label window matures before the next evaluation period begins.
- Model choice: highest validation average precision; the selected pipeline is refit on train + validation, then evaluated on the later test months.

## Model selection on validation months

| Candidate | Average precision | Validation prevalence |
|---|---:|---:|
| `regularized_logistic_regression` | 0.823 | 0.622 |
| `hist_gradient_boosting` | 0.816 | 0.622 |

Selected: **regularized_logistic_regression**. The model was not selected on the locked temporal test.

## Locked temporal test

| Ranking | Average precision | ROC-AUC | Brier score | Log loss | Precision in top 10% | Recall in top 10% | Lift in top 10% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Selected model | 0.716 | 0.752 | 0.204 | 0.592 | 81.2% | 16.7% | 1.67× |
| Recency-only ranker | 0.652 | 0.677 | — | — | 73.8% | 15.2% | 1.52× |
| No-skill / constant prevalence | 0.486 | — | 0.250 | — | — | — | 1.00× |

Test inactivity prevalence is **48.6%** across 17,279 customer-month episodes. The highest-risk 10% contains 1,728 episodes, with **81.2%** observed inactivity and **16.7%** of all positive episodes captured. Lift compares that top-decile precision with the overall test prevalence.

The model's Brier score is **0.204** versus **0.250** for a constant test-prevalence forecast (Brier skill 18.5%). This is a retrospective probability-quality comparison; probabilities still need calibration review before an operational threshold is considered.

## Interpretation

The selected model out-ranks the recency-only comparator on this later slice. This supports the value of combining multiple purchase-history signals for historical ranking in this one dataset. It does **not** establish an intervention effect, expected savings, causes, or performance on another retailer or current customers.

Monthly snapshots overlap in their outcome horizons and can include the same customer more than once. Test rows are customer-month episodes, not unique customers, and Wilson intervals in the segment report do not adjust for repeated episodes. The source is one UK giftware retailer from 2009–2011. Missing IDs and cancellation/return lines are excluded. There is no confirmed cancellation target, offer history, contact result, margin truth, or randomized control group.

## Reproducibility

Run `uv sync` and `uv run python scripts/run_pipeline.py`. Machine-readable metrics are in `data/processed/public/metrics.json`; the public dashboard reads only reviewed aggregate files. The local fitted pipeline and test episodes are ignored by Git.
