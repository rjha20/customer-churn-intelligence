# Initial findings

## Source and cohort shape

UCI Online Retail II contains 1,067,371 source lines from one UK non-store giftware retailer between 1 December 2009 and 9 December 2011. After retaining positive purchases with an identified customer and valid invoice/date, the pipeline built 36,969 invoices for 5,878 customers. Customers with at least one order in the preceding 180 days form each monthly risk set.

## Main descriptive finding

Purchase activity contains a useful historical ranking signal. On the locked later-period test, a recency-only rule reaches average precision 0.652 versus the prevalence baseline of 0.486. Combining multiple prior purchase features with regularized logistic regression reaches 0.716. In the highest-risk 10% of test episodes, 81.2% had no purchase in the next 90 days.

This is descriptive predictive evidence for one old dataset. The 90-day no-purchase outcome is not confirmed cancellation, and the high-risk group is not proven to respond to a retention action.

## Follow-up questions

1. Does the ranking remain stable across later periods and product/customer types?
2. How do the decisions change with finite contact capacity and different assumed costs?
3. Would a randomized holdout show that any support or offer actually changes repeat purchase?

For model-selection splits and calibration, see `model_evaluation.md`. For known source issues, see `data_quality.md`.
