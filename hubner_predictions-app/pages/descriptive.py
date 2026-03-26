from __future__ import annotations
import dash
import pandas as pd
import numpy as np
from pathlib import Path
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import dash_table as dt  # scrolling table

# ---- Safe page registration (Pages mode) ----
def _safe_register_page():
    try:
        dash.get_app()
        dash.register_page(__name__, name="Descriptive Analytics", path="/")
    except Exception:
        pass
_safe_register_page()

# ---------- Load data ----------
HERE = Path(__file__).resolve()
APP_ROOT = HERE.parents[1]
DATA_PATH = APP_ROOT / "data" / "df_cleaned.csv"
YIELD_PATH = APP_ROOT / "data" / "merged_output.csv"
print(f"[descriptive] Expecting CSV at: {DATA_PATH}")

loaded_real_file = False
try:
    df = pd.read_csv(DATA_PATH)
    loaded_real_file = True
except Exception as e:
    print(f"[descriptive] Failed to read {DATA_PATH}: {e!r}")
    # tiny fallback so the page still loads
    df = pd.DataFrame({
        "status": ["NEW", "NEW", "ILOP", "NEW"],
        "maturity": [112, 114, 103, 110],
        "trait": ["CONV", "RR2", "PWE", "CONV"],
        "company": ["1E", "1E", "39EX", "39EX"],
        "qty": [240, 109, 186, 97],
        "year": [2021, 2021, 2021, 2024],
        "plf": [2068, 1782, 1864, 1811],
    })

# ---------- Normalize headers / types ----------
df.columns = [c.strip().lower() for c in df.columns]

# If file ships PLF but not QTY, copy PLF into QTY to avoid KeyErrors elsewhere
if "plf" in df.columns and "qty" not in df.columns:
    df["qty"] = df["plf"]

for col in ("trait", "year", "qty", "company", "plf", "status", "maturity"):
    if col not in df.columns:
        df[col] = pd.NA

df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
df["qty"] = pd.to_numeric(df.get("qty"), errors="coerce").fillna(0)
if "maturity" in df.columns:
    df["maturity"] = pd.to_numeric(df.get("maturity"), errors="coerce")

# Convert PLF to string now for the multiselect filter
if "plf" in df.columns:
    df["plf"] = df["plf"].astype('str').replace('<NA>', np.nan)


year_opts = sorted([int(y) for y in df["year"].dropna().unique()]) if df["year"].notna().any() else []
# Get PLF options after conversion to string
plf_opts = sorted(df["plf"].dropna().unique().tolist()) if df["plf"].notna().any() else []


def get_yield_df():
    if not YIELD_PATH.exists():
        return pd.DataFrame()

    ydf = pd.read_csv(YIELD_PATH)

    # normalize headers but KEEP underscores
    ydf.columns = [c.strip().lower() for c in ydf.columns]

    # rename raw columns
    rename_map = {
        "sum_of_female_acres": "female_acres",
        "sum_of_actual_bushels": "actual_bushels",
        "sum_of_actual_units_bagged": "actual_units_bagged",
    }
    ydf = ydf.rename(columns=rename_map)

    # Compute yield if possible
    if "actual_bushels" in ydf.columns and "female_acres" in ydf.columns:
        ydf["yield"] = ydf["actual_bushels"] / ydf["female_acres"]

    # Clean maturity
    if "maturity" not in ydf.columns:
        for c in ydf.columns:
            if "maturity" in c:
                ydf = ydf.rename(columns={c: "maturity"})

    ydf["maturity"] = pd.to_numeric(ydf["maturity"], errors="coerce")
    ydf["yield"] = pd.to_numeric(ydf["yield"], errors="coerce")
    
    # Ensure PLF column exists and is string for filtering later
    if "plf" in ydf.columns:
        ydf["plf"] = ydf["plf"].astype('str').replace('<NA>', np.nan)
        
    return ydf


def get_df() -> pd.DataFrame:
    """Load base df_cleaned.csv only — no merging with yield data."""
    try:
        d = pd.read_csv(DATA_PATH)
    except Exception as e:
        print(f"[descriptive] get_df() failed: {e!r}")
        return df.copy()

    # normalize headers
    d.columns = [c.strip().lower() for c in d.columns]

    # ensure required columns exist
    needed = {"status", "maturity", "trait", "company", "qty", "year", "plf"}
    for col in needed:
        if col not in d.columns:
            d[col] = pd.NA

    # numeric casting
    for col in ["maturity", "qty", "year"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    
    # Special casting for PLF (numeric for table logic, string for filtering)
    if "plf" in d.columns:
        # Note: We don't need a separate numeric column for this logic, just ensure string conversion for filtering
        d["plf"] = d["plf"].astype('str').replace('<NA>', np.nan)

    # drop rows missing year
    d = d.dropna(subset=["year"])

    return d

# ---------- PLF × Year table (wide counts) ----------
def build_plf_year_wide(d: pd.DataFrame):
    """
    Wide table:
      KEY (PLF → TRAIT → COMPANY), columns for each year,
      plus appearance_counts_yr and total_count.
    Each cell = count of rows for (key, year).
    """
    d = d.copy()
    key_col = "plf" if ("plf" in d.columns and d["plf"].notna().any()) else ("trait" if "trait" in d.columns else "company")
    d = d.dropna(subset=["year", key_col])

    wide = (
        d.groupby([key_col, "year"])
         .size()
         .unstack(fill_value=0)
         .reset_index()
    )
    wide.columns.name = None

    year_cols = [c for c in wide.columns if c != key_col]
    year_cols = sorted([int(c) for c in year_cols])

    wide["appearance_counts_yr"] = (wide[year_cols] > 0).sum(axis=1)
    wide["total_count"] = wide[year_cols].sum(axis=1)

    header_map = {"plf": "PLF", "trait": "TRAIT", "company": "COMPANY"}
    display_key = header_map.get(key_col, key_col.upper())
    wide = wide.rename(columns={key_col: display_key})

    # Restore PLF column type to string for table display
    if display_key == "PLF":
        wide[display_key] = wide[display_key].astype(str).replace('-1', '')

    wide = wide.sort_values(["appearance_counts_yr", "total_count"], ascending=[False, False], ignore_index=True)
    return wide, display_key, year_cols

# ---------- Consistency (PLF-based) helpers ----------
def _yearly_totals(d: pd.DataFrame, key_col: str = "plf", year_col: str = "year", val_col: str = "qty"):
    """Sum qty per (key, year). Returns tidy frame with columns [key_col, year, qty_sum]."""
    t = (
        d.dropna(subset=[key_col, year_col])
         .groupby([key_col, year_col], as_index=False)[val_col]
         .sum()
         .rename(columns={val_col: "qty_sum"})
    )
    t[year_col] = pd.to_numeric(t[year_col], errors="coerce").astype("Int64")
    return t

def _consistency_suite(tidy: pd.DataFrame, key_col: str = "plf", min_years: int = 3):
    """
    Input tidy: [key_col, 'year', 'qty_sum'] (one row per year per key).
    Output: per-key metrics: n_years, mean, sd, cv, slope_per_year, intercept.
    Keeps only keys with >= min_years active years.
    """
    from numpy.linalg import lstsq

    out = []
    for k, g in tidy.groupby(key_col, dropna=False):
        g = g.sort_values("year")
        years = g["year"].to_numpy(dtype=float)
        y = g["qty_sum"].to_numpy(dtype=float)

        n_years = (~np.isnan(y)).sum()
        if n_years < min_years:
            continue

        mean = float(np.nanmean(y))
        sd   = float(np.nanstd(y, ddof=0))
        cv   = float(sd / mean) if mean > 0 else np.nan

        X = np.vstack([years, np.ones_like(years)]).T
        try:
            a, b = lstsq(X, y, rcond=None)[0]  # slope, intercept
        except Exception:
            a, b = np.nan, np.nan

        out.append({
            key_col: k,
            "n_years": int(n_years),
            "mean": mean,
            "sd": sd,
            "cv": cv,
            "slope_per_year": a,
            "intercept": b,
        })

    return pd.DataFrame(out).sort_values(["cv", "mean"], ascending=[True, False], ignore_index=True)

# -------------------------------------------------------------------------------------
# FIX: Moved this block here to ensure functions are defined before being called.
# ---------- Build initial table data so it shows immediately ----------
_initial_wide, _initial_key, _initial_year_cols = build_plf_year_wide(df.copy())
_initial_ren = _initial_wide.rename(columns={y: str(y) for y in _initial_year_cols})
_year_labels = [str(y) for y in _initial_year_cols]
# only keep years that actually exist after rename
_year_labels = [c for c in _year_labels if c in _initial_ren.columns]
_INITIAL_VIEW = _initial_ren[[_initial_key] + _year_labels + ["appearance_counts_yr", "total_count"]]

_INITIAL_COLUMNS = [{"name": c, "id": c} for c in _INITIAL_VIEW.columns]
_INITIAL_DATA = _INITIAL_VIEW.to_dict("records")
# -------------------------------------------------------------------------------------

# ---------- Layout (MODIFIED for PLF filter) ----------
layout = dbc.Container([
    html.H1("Descriptive Analytics"),

    dbc.Alert(
        f"Loaded: {DATA_PATH}" if loaded_real_file
        else f"Could not read {DATA_PATH}. Showing sample data.",
        color="success" if loaded_real_file else "warning",
        className="mb-3"
    ),

    # Global year slicer and NEW PLF SLICER
    dbc.Row([
        # Existing Year Filter
        dbc.Col([
            dbc.Label("Year", style={"color": "black"}),
            dcc.Dropdown(
                id="year-filter",
                options=[{"label": "All years", "value": "ALL"}] +
                        [{"label": str(y), "value": int(y)} for y in year_opts],
                value="ALL",
                clearable=False,
                style={"maxWidth": 160, "color": "black"}
            )
        ], md=2),

        # NEW: PLF Filter
        dbc.Col([
            dbc.Label("PLF Filter", style={"color": "black"}),
            dcc.Dropdown(
                id="plf-filter",
                options=[{"label": p, "value": p} for p in plf_opts],
                value=plf_opts, # Default to all PLFs
                multi=True,     # Allow multiple selections
                placeholder="Select PLFs (default: All)",
                style={"color": "black"}
            )
        ], md=4)
    ], className="mb-3"),

    # Treemap on top
    dcc.Graph(id="g-trait-treemap", style={"height": "62vh"}),

    html.Hr(),

    html.H3("Descriptive Statistics"),
    dbc.Row([
        # LEFT: scrolling PLF × Year table
        dbc.Col([
            html.H5("PLF × Year", className="mb-2"),
            dt.DataTable(
                id="tbl-plf-year",
                columns=_INITIAL_COLUMNS,
                data=_INITIAL_DATA,
                sort_action="native",
                page_action="none",
                fixed_rows={"headers": True},

                # --- visuals ---
                style_table={
                    "height": "540px",
                    "overflowY": "auto",
                    "backgroundColor": "#ffffff",
                    "border": "1px solid #d9d9d9",
                    "borderRadius": "8px",
                },
                style_cell={
                    "textAlign": "center",
                    "minWidth": 70, "maxWidth": 140,
                    "padding": "6px 8px",
                    "color": "#212529",            # dark text
                    "backgroundColor": "#ffffff",  # white cells
                    "border": "1px solid #eeeeee",
                    "fontSize": "14px",
                },
                style_header={
                    "fontWeight": "700",
                    "backgroundColor": "#f8f9fa",  # light gray header
                    "color": "#212529",
                    "borderBottom": "2px solid #dee2e6",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fc"},
                ],
                css=[{"selector": ".dash-table .column-header--sort", "rule": "color: #212529 !important;"}],
            )
        ], md=6),

        # RIGHT: Company share (resized to match table height)
        dbc.Col(
            dcc.Graph(id="g-company-share", style={"height": "540px"}),
            md=6
        )
    ], className="mb-5"),

    html.Hr(),

    html.H3("Consistency & 50% Plan (PLF-based)"),
    dbc.Row([
        dbc.Col(dcc.Graph(id="fig-consistency-trait"), md=6),   # Stability by PLF (CV)
        dbc.Col(dcc.Graph(id="fig-consistency-status"), md=6),  # Trend by PLF (slope)
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(dcc.Graph(id="fig-50-plan-kpi"), md=6),
        dbc.Col(dcc.Graph(id="fig-qty-hist"), md=6),
    ], className="mb-4"),

    html.Hr(),

    html.H3("Yield by Relative Maturity"),
    dbc.Row([
        dbc.Col(dcc.Graph(id="fig-yield-by-maturity"), md=12),
    ], className="mb-5"),

    dcc.Store(id="refresh-key"),
    html.Div(id="file-list", style={"display": "none"}),
], fluid=True)

# ---------- Charts helper (MODIFIED to accept plf_sel) ----------
def build_figs(year_sel, plf_sel):
    
    # 1. Start with the initial year filter
    if year_sel == "ALL" or year_sel is None:
        dff = df.copy()
    else:
        dff = df[df["year"] == pd.to_numeric(year_sel, errors="coerce")]
    
    # 2. APPLY NEW PLF FILTER
    if plf_sel is not None and len(plf_sel) > 0 and len(dff) > 0:
        # Check if the PLF column exists and apply filter
        if "plf" in dff.columns:
            # The PLF column is already a string due to initial processing
            dff = dff[dff["plf"].isin(plf_sel)]
    
    # --- INITIAL EMPTY CHECK ---
    if dff.empty:
        empty_title = f"No data available for filters selected."
        fig_treemap = go.Figure().update_layout(title=empty_title)
        fig_company = go.Figure().update_layout(title=empty_title)
        return fig_treemap, fig_company

    # =========================================================================
    # Treemap (Year -> PLF) using the Stitched Solution
    # =========================================================================
    
    # 1. Prepare data for the treemap (need year and plf counts)
    vc = (
        dff.groupby(["year", "plf"])
           .size()
           .reset_index(name="count")
           .dropna(subset=["year"])
    )

    chart_title = ("PLF Distribution by Year (colored by count)"
                   if year_sel == "ALL" else f"PLF Distribution — {year_sel}")
    
    if vc.empty:
        fig_treemap = go.Figure().update_layout(title=chart_title + " (No PLF data)")
    else:
        # Define strict year order for the columns
        years_ordered = sorted(vc["year"].unique().tolist(), reverse=True)
        num_years = len(years_ordered)
        
        # Create subplots
        fig_treemap = make_subplots(
            rows=1, cols=num_years,
            subplot_titles=[str(y) for y in years_ordered],
            horizontal_spacing=0.005, 
            specs=[[{"type": "domain"}] * num_years]
        )

        # Determine global max for consistent color scaling
        max_count = vc["count"].max()
        
        # Fill each column with a separate treemap trace
        for i, year in enumerate(years_ordered):
            year_data = vc[vc["year"] == year]
            
            if year_data.empty:
                continue
            
            # Use px to easily generate the trace (defaults to squarify inside the domain)
            temp_fig = px.treemap(
                year_data, 
                path=["plf"],
                values="count",
                color="count",
                color_continuous_scale="Blues",
                range_color=[0, max_count] # Lock the color scale range
            )
            
            trace = temp_fig.data[0]
            trace.update(
                textinfo="label+value",
                texttemplate="%{label}<br>%{value}",
                hovertemplate="%{label}: %{value}<extra></extra>",
                insidetextfont=dict(size=14)
            )
            
            fig_treemap.add_trace(trace, row=1, col=i+1)

        # Finalize layout
        fig_treemap.update_layout(
            title=chart_title,
            margin=dict(l=20, r=20, t=60, b=20),
            coloraxis=dict(colorscale="Blues", cmin=0, cmax=max_count),
        )

        # Hide color bars for all traces (using the corrected property)
        fig_treemap.update_traces(marker_showscale=False)

        # Show color bar only for the last trace
        if fig_treemap.data:
            fig_treemap.data[-1].marker.showscale = True

    # =========================================================================
    # END TREEMAP CODE
    # =========================================================================

    # Company Contribution (Donut)
    company_share = (
        dff.dropna(subset=["company"])
           .groupby("company", as_index=False)["qty"].sum()
           .sort_values("qty", ascending=False)
    )
    
    # --- COMPANY SHARE EMPTY CHECK ---
    if company_share["qty"].sum() == 0 or company_share.empty:
        fig_company = go.Figure().update_layout(title="Quantity Share by Company (No data)")
    else:
        # (rest of the company share logic) ...
        if len(company_share) > 8:
            top8 = company_share.head(8)
            other_sum = company_share["qty"].iloc[8:].sum()
            company_share = pd.concat(
                [top8, pd.DataFrame([{"company": "Other", "qty": other_sum}])],
                ignore_index=True
            )

        fig_company = px.pie(
            company_share, names="company", values="qty", hole=0.45,
            title=("Quantity Share by Company"
                   if year_sel == "ALL" else f"Quantity Share by Company — {year_sel}")
        )
        fig_company.update_traces(textposition="inside", textinfo="percent+label")
        fig_company.update_layout(margin=dict(l=40, r=40, t=60, b=40))

    return fig_treemap, fig_company


def build_yield_by_maturity(d: pd.DataFrame, year_sel, plf_sel):
    """Mean yield (or qty proxy) by relative maturity, with 95% CI band when possible."""
    d = d.copy()

    # APPLY NEW PLF FILTER
    if plf_sel is not None and len(plf_sel) > 0 and len(d) > 0 and "plf" in d.columns:
        d = d[d["plf"].isin(plf_sel)]

    # need maturity + yield
    if "maturity" not in d.columns or "yield" not in d.columns or d.empty:
        fig = go.Figure().update_layout(title="Yield by Relative Maturity — no usable data")
        return fig

    d = d.dropna(subset=["maturity", "yield"])
    if d.empty:
        fig = go.Figure().update_layout(title="Yield by Relative Maturity — no usable data")
        return fig

    # ... (rest of build_yield_by_maturity logic remains unchanged) ...
    # aggregate: mean yield by maturity
    g = (
        d.assign(maturity=lambda x: pd.to_numeric(x["maturity"], errors="coerce"))
         .dropna(subset=["maturity"])
         .groupby("maturity", as_index=False)
         .agg(mean_yield=("yield", "mean"),
              n=("yield", "size"),
              sd=("yield", "std"))
         .sort_values("maturity")
    )
    g["se"] = g["sd"] / np.sqrt(g["n"])
    g["ci_lo"] = g["mean_yield"] - 1.96 * g["se"]
    g["ci_hi"] = g["mean_yield"] + 1.96 * g["se"]

    title_suffix = "All Years (mean per RM)" if year_sel == "ALL" else f"Year {year_sel} (mean per RM)"
    y_label = "Yield (bu/acre)" if {"actual_bushels", "female_acres"}.issubset(d.columns) else "Yield (proxy: qty)"

    fig = go.Figure()

    # CI band (only where defined)
    ci_ok = g["se"].notna()
    if ci_ok.any():
        fig.add_trace(go.Scatter(
            x=g.loc[ci_ok, "maturity"],
            y=g.loc[ci_ok, "ci_hi"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=g.loc[ci_ok, "maturity"],
            y=g.loc[ci_ok, "ci_lo"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            name="95% CI"
        ))

    # mean line with markers
    fig.add_trace(go.Scatter(
        x=g["maturity"], y=g["mean_yield"],
        mode="lines+markers",
        name="Mean"
    ))

    fig.update_layout(
        title=f"Yield by Relative Maturity — {title_suffix}",
        xaxis_title="Relative Maturity",
        yaxis_title=y_label,
        margin=dict(l=40, r=20, t=60, b=40)
    )
    return fig


# ---------- Callbacks (MODIFIED to include plf_filter) ----------

@callback(
    Output("g-trait-treemap", "figure"),
    Output("g-company-share", "figure"),
    Input("year-filter", "value"),
    Input("plf-filter", "value") # <-- NEW INPUT
)
def update_all_figs(year_sel, plf_sel): # <-- NEW ARGUMENT
    return build_figs(year_sel, plf_sel)

@callback(
    Output("tbl-plf-year", "columns"),
    Output("tbl-plf-year", "data"),
    Input("year-filter", "value"),   # not used to filter the summary; kept for future
    Input("plf-filter", "value") # <-- NEW INPUT
)
def update_plf_year_table(_year_sel, plf_sel): # <-- NEW ARGUMENT
    dfx = get_df()
    
    # APPLY NEW PLF FILTER TO TABLE DATA
    if plf_sel is not None and len(plf_sel) > 0 and len(dfx) > 0 and "plf" in dfx.columns:
        dfx = dfx[dfx["plf"].isin(plf_sel)]

    if dfx.empty:
        return _INITIAL_COLUMNS, _INITIAL_DATA

    wide, display_key, year_cols = build_plf_year_wide(dfx) # Pass filtered dfx
    
    ren = wide.rename(columns={y: str(y) for y in year_cols})
    year_labels = [str(y) for y in year_cols if str(y) in ren.columns]
    cols_order = [display_key] + year_labels + ["appearance_counts_yr", "total_count"]
    view = ren[cols_order]

    columns = [{"name": c, "id": c} for c in view.columns]
    data = view.to_dict("records")
    return columns, data


@callback(
    Output("fig-consistency-trait", "figure"),   # Stability by PLF (CV)
    Output("fig-consistency-status", "figure"),  # Trend by PLF (slope)
    Output("fig-50-plan-kpi", "figure"),
    Output("fig-qty-hist", "figure"),
    Input("year-filter", "value"),
    Input("plf-filter", "value"), # <-- NEW INPUT
)
def update_consistency_figs(year_sel, plf_sel): # <-- NEW ARGUMENT
    dfx = get_df()
    
    # APPLY NEW PLF FILTER
    if plf_sel is not None and len(plf_sel) > 0 and len(dfx) > 0 and "plf" in dfx.columns:
        dfx = dfx[dfx["plf"].isin(plf_sel)]

    # ---------- PLF-based consistency ----------
    if "plf" not in dfx.columns or dfx["plf"].isna().all():
        empty_msg = "No PLF data available"
        fig_stability = go.Figure().update_layout(title=empty_msg)
        fig_trend = go.Figure().update_layout(title=empty_msg)
        pct_stable = 0.0
    else:
        # ... (rest of consistency logic remains unchanged, operating on filtered dfx) ...
        plf_yearly = _yearly_totals(dfx, key_col="plf")        # sum qty per PLF-year
        plf_cons   = _consistency_suite(plf_yearly, "plf", 3)  # require ≥3 active years

        # Stability bar (lowest CV is best) — top 25
        top_stable = plf_cons.dropna(subset=["cv"]).nsmallest(25, "cv").copy()
        top_stable["plf"] = top_stable["plf"].astype(str)
        fig_stability = px.bar(
            top_stable,
            x="plf", y="cv",
            title="Stability by PLF (lower CV = steadier) — ≥3 active years",
            labels={"plf": "PLF", "cv": "Coefficient of Variation (sd/mean)"},
        )
        fig_stability.update_yaxes(tickformat=".2f")
        fig_stability.update_layout(xaxis_tickangle=-35, margin=dict(l=40, r=20, t=60, b=80))

        # Trend bar — top 25 by absolute slope
        trend = (
            plf_cons.dropna(subset=["slope_per_year"])
                    .reindex(plf_cons["slope_per_year"].abs().sort_values(ascending=False).index)
                    .head(25)
                    .copy()
        )
        trend["plf"] = trend["plf"].astype(str)
        fig_trend = px.bar(
            trend,
            x="plf", y="slope_per_year",
            title="Trend by PLF (slope of yearly totals; + rising, − falling)",
            labels={"plf": "PLF", "slope_per_year": "Slope (qty per year)"},
        )
        fig_trend.update_layout(xaxis_tickangle=-35, margin=dict(l=40, r=20, t=60, b=80))

        # KPI: % of PLFs that meet stability rule (CV ≤ 0.40 and ≥3 years)
        if not plf_cons.empty:
            stable_mask = (plf_cons["cv"] <= 0.40) & (plf_cons["n_years"] >= 3)
            pct_stable = 100.0 * stable_mask.mean()
        else:
            pct_stable = 0.0

    # KPI gauge
    fig_kpi = go.Figure(go.Indicator(
        mode="gauge+number",
        value=float(pct_stable),
        number={"suffix": "%", "valueformat": ".1f"},
        title={"text": "PLFs meeting stability rule (CV ≤ 0.40, ≥3 yrs)"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"thickness": 0.4}},
    ))

    # Context histogram on raw qty
    threshold = 0.5 * dfx["qty"].mean()
    fig_hist = px.histogram(
        dfx, x="qty", nbins=30,
        title=f"Quantity Distribution (dashed = 50% of mean = {threshold:.0f})"
    )
    fig_hist.add_vline(x=float(threshold), line_width=2, line_dash="dash")
    fig_hist.update_layout(bargap=0.05)

    return fig_stability, fig_trend, fig_kpi, fig_hist

@callback(
    Output("fig-yield-by-maturity", "figure"),
    Input("year-filter", "value"),
    Input("plf-filter", "value"), # <-- NEW INPUT
)
def update_yield_by_maturity(year_sel, plf_sel): # <-- NEW ARGUMENT
    dfx = get_yield_df()
    return build_yield_by_maturity(dfx, year_sel, plf_sel)

# ---------- Standalone Runner (optional) ----------
if __name__ == "__main__":
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    app.layout = layout
    app.run(debug=True)