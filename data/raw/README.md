# Raw data acquisition

The analysis uses the UCI Online Retail II transaction workbook. Download it from the official UCI page: https://archive.ics.uci.edu/dataset/502/online+retail+ii . The project pipeline downloads the UCI ZIP archive when the local workbook is absent. The 43.5 MB source archive and extracted workbook are intentionally excluded from Git; UCI lists the dataset under CC BY 4.0 and requires attribution.

For an offline/manual run, place `online_retail_II.xlsx` under `data/raw/` or extract the UCI archive there. Do not commit customer-level transaction rows or identifiers.
