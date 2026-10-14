-- Run against data/processed/local/retention.sqlite after scripts/run_pipeline.py.
-- The database contains customer-level rows. Keep it local and never commit it.

-- 1) Monthly eligible population and observed 90-day inactivity.
SELECT
    snapshot_month,
    COUNT(*) AS eligible_customer_months,
    SUM(inactive_90d) AS inactive_customer_months,
    ROUND(1.0 * SUM(inactive_90d) / COUNT(*), 4) AS inactivity_rate
FROM customer_month_snapshots
GROUP BY snapshot_month
ORDER BY snapshot_month;

-- 2) Locked temporal-test concentration by score decile (1 = highest risk).
WITH test_prevalence AS (
    SELECT AVG(inactive_90d) AS overall_inactivity_rate
    FROM temporal_test_scores
)
SELECT
    s.risk_decile,
    COUNT(*) AS eligible_episodes,
    ROUND(AVG(s.predicted_inactivity_probability), 4) AS mean_predicted_probability,
    ROUND(AVG(s.inactive_90d), 4) AS observed_inactivity_rate,
    ROUND(AVG(s.inactive_90d) / NULLIF(p.overall_inactivity_rate, 0), 3) AS lift_vs_test_prevalence,
    ROUND(AVG(s.revenue_180d), 2) AS mean_prior_180d_gross_sales_gbp
FROM temporal_test_scores AS s
CROSS JOIN test_prevalence AS p
GROUP BY s.risk_decile, p.overall_inactivity_rate
ORDER BY s.risk_decile;

-- 3) Descriptive inactivity by recency and customer tenure.
SELECT
    recency_band,
    tenure_band,
    COUNT(*) AS eligible_episodes,
    ROUND(AVG(inactive_90d), 4) AS inactivity_rate,
    ROUND(AVG(revenue_180d), 2) AS mean_prior_180d_gross_sales_gbp
FROM customer_month_snapshots
WHERE snapshot_month >= '2011-04'
GROUP BY recency_band, tenure_band
HAVING COUNT(*) >= 50
ORDER BY inactivity_rate DESC;

-- 4) Never sum segment churn counts across overlapping segment definitions.
