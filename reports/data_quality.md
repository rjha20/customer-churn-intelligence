# Data quality and feature eligibility

Source: UCI Online Retail II, a 1,067,371-row workbook spanning 2009-12-01 to 2011-12-09.

## Pipeline audit

The build found 805,549 transaction lines eligible for purchase-event construction, grouped into 36,969 identified-customer invoices and 5,878 identified customers across 41 countries. The pipeline excluded 261,822 rows from the purchase-event path. Exclusion reason counts overlap: 243,007 rows have no customer ID and 19,494 lines belong to cancellation invoices; other non-qualifying conditions include invalid/missing dates, non-positive quantity, and non-positive unit price.

## Modeling eligibility

Snapshots start after six months of observed history. A customer-month episode is retained only when that customer had a positive purchase in the prior 180 days. The target window is 90 days after the snapshot. The last snapshot is restricted so the entire target window is observed by the source end date. The model feature table contains no missing values after construction.

## Known source limitations

- 243,007 source rows have no customer ID and cannot contribute to customer-level retention episodes.
- The dataset includes cancellations/returns and non-positive quantities/prices; the churn prototype excludes these lines from completed purchases.
- UCI describes the business as a UK giftware retailer with many wholesalers. Customer behavior can be seasonal and business-to-business.
- The workbook is historical, limited to one business and ends in 2011.
- The project treats missing follow-up purchase as an inactivity proxy, not verified cancellation.

Full machine-readable counts are in `data/processed/public/metrics.json`.
