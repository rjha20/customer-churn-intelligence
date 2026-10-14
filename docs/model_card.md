# Model card: Customer Retention Intelligence

## Summary

This project builds a historical customer-month ranking model for a **90-day no-purchase inactivity proxy** from UCI Online Retail II. It is a deployed portfolio demo for analytical decision support. It is not a live production retention system, a cancellation model, or a model for Amex customers.

## Intended use

- Explore purchase recency, frequency, spend, and repeat-purchase patterns.
- Compare a regularized logistic model and histogram gradient boosting against a no-skill prevalence baseline and a recency-only ranker.
- Demonstrate chronological model selection, a later-period holdout, capacity-based ranking metrics, calibration checks, and transparent limitations.
- Use aggregate evidence to define questions for a future randomized retention experiment.

## Out-of-scope use

- Making automated contact, pricing, credit, eligibility, or service decisions about real people.
- Claiming that an offer prevents churn or causes incremental revenue.
- Applying this score to Amex cardmembers or to current retail customers.
- Treating the inactivity label as confirmed cancellation.

## Data and target

- Source: Chen (2012), [UCI Online Retail II](https://doi.org/10.24432/C5CG6D), CC BY 4.0 with attribution.
- Vintage: 1 December 2009 through 9 December 2011; one UK non-store giftware retailer, with many wholesalers.
- Prediction unit: customer-month episode, where the customer made at least one positive-value purchase in the prior 180 days.
- Snapshot: first day of each month.
- Label: no positive-value purchase within the following 90 days.
- Predictors use purchases strictly before the snapshot. Customer identifiers and country are excluded from the model features.

## Evaluation

The pipeline chooses between a regularized logistic regression and histogram gradient boosting on validation months, refits the selected model on development months, then evaluates on later locked test months. Purged month gaps ensure each 90-day training or validation target window has matured before the next evaluation period starts. It reports average precision relative to prevalence and recency-only baselines, ROC-AUC, Brier score, log loss, top-decile precision/recall/lift, monthly slices, and Wilson intervals for descriptive subgroup rates. Exact results are generated in `data/processed/public/metrics.json` and summarized in `reports/model_evaluation.md`.

The 90-day prediction horizons overlap across monthly snapshots. A customer can appear in multiple months, matching repeated portfolio monitoring but reducing the independence of rows. This is a future-period test for one historical retailer, not a test on a new institution or modern economic conditions.

## Risks and limitations

- A no-purchase period is only an inactivity proxy; the source has no verified cancellation or service-end field.
- This is one old retailer, with giftware/wholesale mix; the patterns may not transfer elsewhere.
- Missing customer identifiers and cancellation/return lines are excluded when constructing purchase episodes.
- The source has no contact, offer, treatment assignment, campaign cost, margin, or intervention outcome. Model ranking does not estimate campaign uplift, saved customers, or ROI.
- Probability calibration may be weak; report Brier skill against a constant-prevalence baseline and label results accordingly.
- Monthly slices and subgroup differences are descriptive, not causal. Do not interpret coefficient or permutation importance as levers.
- The public dashboard contains only grouped metrics. Raw transactions, row-level scores, and fitted model files stay out of Git.

## Monitoring needed before any operational pilot

A real business would need recent longitudinal data, approved use and privacy controls, point-in-time feature contracts, maturity checks for outcomes, drift and calibration monitoring, capacity and cost requirements, subgroup review, and a randomized holdout test. Any operational model would require the business's own validation and governance process.
