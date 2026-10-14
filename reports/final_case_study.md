# Final case study: customer retention intelligence

## Business question

Can historical purchase behavior help a retention team prioritize which active customers to investigate first, when review capacity is limited?

## Data and target

The project uses UCI Online Retail II, a CC BY 4.0 historical transaction dataset for a single UK giftware retailer from 2009–2011. It aggregates purchases into monthly customer episodes. Eligible customers made a positive purchase during the prior 180 days; the target is no positive purchase in the next 90 days. This is an inactivity proxy, not confirmed churn.

## Approach

The pipeline validates and filters raw invoice lines, creates point-in-time recency/frequency/spend features, builds cohort and segment summaries with confidence intervals, selects between regularized logistic regression and histogram gradient boosting on validation months, then reports a later locked time holdout. It compares the selected model with test prevalence and a recency-only ranking. The Streamlit app exposes grouped data, decile performance, descriptive segments, calibration diagnostics, and a break-even scenario whose costs/lift are explicitly user assumptions.

## Result

Across 17,279 customer-month episodes from April–September 2011, the validation-selected logistic regression achieved average precision 0.716 versus a no-skill prevalence baseline of 0.486 and recency-only AP of 0.652. The highest-risk 10% had 81.2% observed 90-day inactivity (1.67× overall prevalence), capturing 16.7% of positive episodes. Brier score was 0.204 versus 0.250 for a constant-prevalence forecast. These figures support retrospective ranking in this dataset; they do not imply campaign success or current performance.

## Decision recommendation

Treat the score as a way to select a small group for human review and further research, not automatic customer contact. If a real business wants to act on retention risk, first define contact eligibility, costs, customer-protection constraints, and a measurable future outcome; then run a randomized control test to estimate incremental retention and value.

## What this demonstrates for Amex analytics roles

Point-in-time customer behavior features, SQL/Python-ready analytics structure, imbalanced ranking metrics, time-based validation, calibration comparison, segment statistics, capacity planning, and transparent model governance. This retail inactivity proxy does not model Amex card closure, credit risk, fraud, or offer response.

## Limits

The data are old, one-company, UK giftware/wholesale-heavy transactions. Customer-month windows overlap and some customers recur across splits. The source lacks verified cancellations, current behavior, contact history, offer outcomes, and margin/ROI truth. See [`model_evaluation.md`](model_evaluation.md), [`docs/model_card.md`](../docs/model_card.md), and [`docs/data_policy.md`](../docs/data_policy.md).
