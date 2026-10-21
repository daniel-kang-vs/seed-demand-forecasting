# Reorder Likelihood Dashboard — Hubner Seed

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python) ![Dash](https://img.shields.io/badge/Dash-Plotly-1f77b4?logo=plotly) ![pandas](https://img.shields.io/badge/pandas-ETL-150458?logo=pandas)

> **Planning problem:** seed production arrives as a different wide spreadsheet every year. Planners need one table, a view of which lines are stable, and a forecast they can compare with a baseline before they change inventory. Built with the Purdue Data Mine for Hubner Seed.

**[Live demo](https://daniel-kang-vs.github.io/seed-demand-forecasting/)** — synthetic data with the same shape as the partner file. No proprietary quantities.

---

## Project Highlights

- An ETL step that finds the real header in a messy yearly export and melts a wide company layout into one long table
- Descriptive views for mix, consistency, and product-line trends before anyone trusts a forecast
- Model comparison on holdout **R²** and **RMSE**, plus an elbow chart for how product lines are binned
- A Dash app with three jobs: describe, compare forecasts, and upload a new file

---

## Problem Statement

Overstock ties up warehouse space. Understock misses a planting window. The file a planner actually has is a yearly production export: a header that does not start on row 1, four identity columns, and then one column per company with a quantity underneath.

Those files do not share a layout across years. A forecast built on one year’s column positions breaks the next year.

---

## Data

Each yearly CSV is wide. The pipeline looks through the first 40 rows for the header that contains `STATUS`, `MATURITY`, `TRAIT`, and `PLF`, then treats the remaining columns as companies.

| Output column | Meaning |
|---------------|---------|
| `STATUS`, `MATURITY`, `TRAIT`, `PLF` | Line identity |
| `company` | Melted from the wide header |
| `qty` | That company’s quantity, coerced to a number |
| `year` | Read from the file name (`20xx`) |

Empty company cells are dropped. The public demo replaces this table with synthetic JSON in `docs/data/` that keeps the schema and not the partner’s numbers.

The app also reads a processed yield/trait table (`trait_yield.csv`) for the descriptive views.

---

## Pipeline

```
Yearly wide CSVs
      │
      ▼
Find the header row (STATUS, MATURITY, TRAIT, PLF)
      │
      ▼
Melt company columns → one row per company × line
      │
      ▼
Attach year, drop blank quantities
      │
      ├── Descriptive page     mix, consistency, line trends
      ├── Predictions page     R², RMSE, elbow, actual vs predicted by PLF bin
      └── Upload page          new file through the same cleaner
```

`pipeline.py` is the cleaner. `hubner_predictions-app/app.py` is the Dash entry point. Pages live in `pages/descriptive.py`, `pages/predictions.py`, and `pages/upload.py`.

The prediction charts on the page are the comparison the data-science pass produced for 2024: test R² by model, RMSE relative to the mean, the elbow for the number of product-line bins, and actual versus predicted quantity by bin. This README does not reprint a winning R². The charts are the comparison, and the public site is synthetic, so a single score on this page would describe the wrong dataset.

---

## Key Technical Decisions

1. **Clean the file before modeling it.** Schema drift across years was the actual blocker. A model on one tidy extract does not survive the next export.

2. **Show the series before the forecast.** Mix and trend tell a planner whether a line is stable enough to forecast. The model page is the second screen, not the first.

3. **Compare models on R² and RMSE, not on a default.** The page exists so a worse method is visible. It does not hide the baseline.

4. **Publish a synthetic mirror.** The workflow is public. The partner’s quantities are not. The live site says so on the page.

---

## Repository Structure

```
├── hubner_predictions-app/
│   ├── app.py
│   ├── pipeline.py
│   ├── pages/
│   │   ├── descriptive.py
│   │   ├── predictions.py
│   │   └── upload.py
│   ├── assets/          # Comparison charts and styles
│   └── data/            # Year files and processed tables used by the app
├── docs/                # GitHub Pages demo on synthetic data
│   ├── index.html
│   ├── js/dashboard.js
│   └── data/
└── README.md
```

---

## How to Run

```bash
pip install dash dash-bootstrap-components pandas plotly numpy openpyxl
cd hubner_predictions-app
python app.py
```

Open http://127.0.0.1:8050.

The Pages demo in `docs/` is static and does not need Dash. It is the public version, on synthetic data.

---

## Tech Stack

| Library | Purpose |
|---------|---------|
| pandas | Header detection, melt, year parse |
| Dash / Plotly | Descriptive, forecast, and upload pages |
| NumPy | Aggregations behind the charts |
| GitHub Pages | Public demo |
