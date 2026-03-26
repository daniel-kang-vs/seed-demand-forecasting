## Repo orientation for AI coding agents

This is a small Dash-based data visualization app for "Seed Demand Forecasting".
Keep instructions short and concrete so contributors can be productive immediately.

Key files
- `app.py` — app bootstrap: creates a Dash app with `use_pages=True`, a navbar, and `dash.page_container`.
- `pages/` — contains page modules. Each page registers with `dash.register_page(...)` and exposes a `layout` (and optional standalone runner block).
- `pages/descriptive.py`, `pages/predictions.py`, `pages/upload.py` — primary pages to inspect for data loading, callbacks, and upload logic.
- `data/df_cleaned.csv` — canonical dataset read by `pages/descriptive.py` (pages expect files under `data/`).
- `assets/` — static CSS and images served automatically by Dash (e.g. `assets/custom.css`, `assets/hubner_logo.png`).
- `instructions.txt` — human-maintained run/branch guidance (use as supplemental manual notes).

Big-picture architecture
- Single-process Dash app (no separate backend service). `app.py` wires the navbar and loads pages via Dash Pages.
- Pages locate data relative to their file using `Path(__file__).resolve()` and `HERE.parents[1]` → this resolves to the project root and then `data/`.
- Data flow: pages read files from `data/` (e.g. `df_cleaned.csv`) and render Plotly figures. The `upload` page writes user uploads into `data/`.

Project-specific patterns to follow (copy these exactly)
- Locate resources using the Path pattern:
  - HERE = Path(__file__).resolve(); APP_ROOT = HERE.parents[1]; DATA_PATH = APP_ROOT / "data" / "df_cleaned.csv"
- Page registration:
  - Use `dash.register_page(__name__, name="...", path="/...")` at module top. Note: some pages include a `if __name__ == "__main__":` standalone runner for quick debugging.
- Upload handling:
  - `pages/upload.py` implements a safe filename function `_secure_filename(...)`, decodes base64 payloads, validates CSV/XLSX via pandas (nrows smoke test) and writes files to `data/`.
  - Allowed extensions: `.csv`, `.xlsx` (see `_ALLOWED_EXTS`). Keep validation logic consistent when adding new upload handlers.
- Data-safe defaults:
  - Pages defensively add missing columns and coerce types (e.g., `df.columns = [c.strip().lower() ...]`, `pd.to_numeric(..., errors='coerce')`). Preserve this defensive style.

Important gotchas / repo inconsistencies
- File-to-page mapping is inconsistent: `pages/descriptive.py` currently registers the root path `/` and prints debug traces containing "[predictions]", while `pages/predictions.py` registers `/predictions`. Double-check which file to edit for a given route.
- Logging is done with print() calls. When adding features prefer adding consistent logging (or keep print statements for small debugging only).

Developer workflows & commands
- Install minimal dependencies (use project venv):
  - pip install dash dash-bootstrap-components pandas plotly openpyxl
- Run the app locally (default port 8050):
  - python app.py
- Branching / commits: `instructions.txt` recommends working on `Data-Visualization` branch; check `git status` and `git checkout Data-Visualization` before edits.

Tests / linting
- There are no test suites or linters present in the repo. If you add unit tests, place them under `tests/` and run with pytest.

What to change and where (examples)
- To add a new chart that uses `df_cleaned.csv`, modify `pages/descriptive.py` (this page reads `data/df_cleaned.csv` and contains `build_figs(...)` and callbacks wired with `@callback`).
- To change upload behavior (e.g., accept `.parquet`), update `_ALLOWED_EXTS`, add validation in `_save_file` and update UI text in `pages/upload.py`.

When modifying files
- Preserve the existing Path-based data lookup and filename sanitization logic.
- Keep pages export a top-level `layout` variable so Dash Pages can import it automatically.

If anything here is unclear or you need more repo-specific notes (CI, secrets, recommended package versions), ask for those details and I will expand this file.
