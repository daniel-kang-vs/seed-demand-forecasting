# Seed Demand Forecasting Analytics Dashboard

An end-to-end predictive analytics platform built for **Hubner Seed** in partnership with the **Purdue Data Mine**. The system transforms raw production-line data into actionable demand forecasts, helping seed producers plan inventory with confidence.

## Live Demo

**[View the Interactive Dashboard](https://daniel-kang-vs.github.io/seed-demand-forecasting/)**

> All data on the live site is synthetic and mirrors the schema of the real dataset without exposing proprietary information.

## Features

- **Descriptive Analytics** — Interactive treemaps, donut charts, consistency analyses, and PLF-level trend tracking across multiple years
- **Predictive Modeling** — Model comparison (R², RMSE) across regression and ML approaches for seed demand forecasting
- **Data Pipeline** — Robust ETL pipeline that ingests messy, wide-format CSVs from multiple production years and normalizes them into analysis-ready DataFrames
- **Upload & Process** — Drag-and-drop interface for uploading new production data with automatic cleaning and validation

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Dashboard | Python, Dash, Plotly, Dash Bootstrap Components |
| Data Processing | Pandas, NumPy |
| Portfolio Site | HTML, CSS, Plotly.js |
| Deployment | GitHub Pages |

## Project Structure

```
├── hubner_predictions-app/    # Main Dash application
│   ├── app.py                 # Entry point
│   ├── pipeline.py            # Data pipeline
│   ├── pages/
│   │   ├── descriptive.py     # Descriptive analytics page
│   │   ├── predictions.py     # ML predictions page
│   │   └── upload.py          # Data upload page
│   ├── assets/                # CSS, images, logos
│   └── data/                  # Processed datasets
├── docs/                      # GitHub Pages portfolio site
│   ├── index.html
│   ├── css/style.css
│   ├── js/dashboard.js        # Interactive Plotly.js charts
│   └── data/                  # Synthetic JSON data
└── README.md
```

## Running Locally

```bash
pip install dash dash-bootstrap-components pandas plotly numpy openpyxl
cd hubner_predictions-app
python app.py
```

Then open http://127.0.0.1:8050 in your browser.

## Acknowledgments

Built as part of The Data Mine at Purdue University, in collaboration with Hubner Seed.
