# Customer retention: model and evaluation walkthrough

## Prediction contract

Each row is a customer-month episode with a purchase in the preceding 180 days. Features use transactions strictly before the monthly snapshot. The label is no positive-value purchase during the next 90 days. The model ranks future inactivity; it does not measure the effect of a retention offer.

## Features

The 14 predictors in `src/customer_churn/pipeline.py::FEATURES` cover recency, customer age, orders and revenue over 30/90/180 days, units, distinct products, average invoice value, mean purchase gap, and recent order/revenue ratios. Ratios capture changes in engagement alongside total activity. Missing-value handling and scaling are fitted within the model pipeline.

## Time splits and model selection

Training ends before October 2010, validation uses December 2010 through January 2011, and the locked test uses April through September 2011. October/November 2010 and February/March 2011 snapshots are purged so labels have matured before the next period. Random row splitting would mix repeated customer episodes and future label windows.

Regularized logistic regression achieved validation AP 0.8229 vs 0.8155 for histogram gradient boosting, so it was selected and refitted on training plus validation data. The result shows which candidate performed better on this validation set. It does not prove a general advantage of linear models. A plausible explanation is that the engineered behavioral features already capture much of the useful structure; test this with controlled ablations and repeated time-based evaluation before asserting it.

## Locked test results

From `data/processed/public/metrics.json`, 17,279 test episodes have inactivity prevalence 0.4859. Model AP is 0.7156, compared with 0.6518 for recency-only ranking. Top-decile precision is 0.8125 and lift is 1.6721. These metrics evaluate ranking at a fixed review capacity, not campaign revenue or incremental response.

The Brier score is 0.20356 vs 0.24980 for the constant-prevalence baseline. Brier skill is `1 - model_brier / baseline_brier = 18.51%`. This measures relative probabilistic prediction error; it does not by itself establish calibration. Reliability plots and group/time checks remain necessary.

## Reproduction and further analysis

Follow the root README to reproduce the source processing and benchmark. Keep the current test set locked when choosing new models. If comparing XGBoost or adding feature ablations, select settings using earlier development periods, record an experiment manifest, and report both improvements and regressions. No XGBoost result is currently claimed.

For an interview, trace one customer's snapshot, explain the 90-day label maturity gap, distinguish AP from top-decile lift, and show why predictive inactivity risk cannot establish causal retention uplift.
