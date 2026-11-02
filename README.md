# Seed Planning Dashboard

> Which product lines are stable enough to plan around, and which need a closer look?

**Industry project · synthetic public demo**

A Python cleaning workflow and interactive dashboard turn inconsistent yearly exports into a view of product mix, stability, and trends.

[Case study](https://daniel-kang-vs.github.io/projects/seed-demand.html) · [Source evidence](https://github.com/daniel-kang-vs/seed-demand-forecasting/blob/main/hubner_predictions-app/pipeline.py) · [Live dashboard](https://daniel-kang-vs.github.io/seed-demand-forecasting/)

## Highlights

- **Multi-year ETL**
- **Interactive Plotly views**
- **Synthetic public data**

## The problem

Yearly production exports use inconsistent headers and wide company columns. A planner needs comparable history before making an inventory or forecasting decision.

## Data & scope

The public dashboard uses synthetic JSON with the partner schema. Each cleaned row represents a company, product line and year, with quantity and trait identifiers. Public demo figures do not describe partner performance.

## How it works

1. Detect the header and normalize identity columns in yearly exports.
2. Reshape company columns into rows, attach the year, and combine cleaned files.
3. Explore mix and quantity distributions; compare multi-year variation and slopes by product line.
4. Keep forecast comparisons separate from the synthetic descriptive demo.

## Key technical decision

Make data preparation and exploratory analysis visible before showing model comparisons. The browser demo needs no private file or Python server.

## Results & interpretation

The public deliverable is an inspectable workflow and interactive planning interface. It demonstrates how a planner can narrow a product group, inspect its history, and question a forecast; it does not establish an inventory reduction or realized revenue lift.

## Limitations & next steps

Synthetic data demonstrates functionality, not business impact. Archived prediction images are separate artifacts, not metrics calculated from the synthetic filter selections. A deployment needs input-schema checks, configurable paths, and a time-based forecast evaluation.

## Evidence & reproducibility

docs/data/synthetic_cleaned.json and docs/data/synthetic_merged.json power the hosted descriptive dashboard.

## Repository guide

- [`hubner_predictions-app/pipeline.py`](hubner_predictions-app/pipeline.py) — analysis implementation.
- [`docs/`](docs/) — static dashboard, styles, and browser-side analysis.

## Run or inspect

Preview the synthetic dashboard with no Python package installation:

```bash
python3 -m http.server 8000 --directory docs
```

Open http://localhost:8000.

## Technology

Python · pandas · Dash · Plotly

---

## Technical appendix

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

