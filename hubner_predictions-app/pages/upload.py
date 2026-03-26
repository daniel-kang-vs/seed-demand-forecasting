# pages/upload.py
from __future__ import annotations

import base64
import io
import re
from pathlib import Path
from typing import Tuple, List, Optional

import dash
from dash import html, dcc, Input, Output, State, callback, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import pandas as pd

# ---------------------------------------------------------------------------
# Page registration
# ---------------------------------------------------------------------------
dash.register_page(__name__, name="Upload Data", path="/upload")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve()
APP_ROOT = HERE.parents[1]

# uploads live here
DATA_DIR = APP_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# processed output lives here
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = PROCESSED_DIR / "df_cleaned_all.csv"
OUT_CSV_ALIAS = DATA_DIR / "df_cleanedpipeline.csv"  # alias for descriptive page

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------
_ALLOWED_EXTS = {".csv"}
_OUTPUT_BASENAMES = {"df_cleaned.csv", "df_cleaned_all.csv"}  # exclude when scanning inputs

_QTY_LABELS = {"QTY", "QUANTITY", "UNITS", "UNIT", "COUNT", "TOTAL", "SUBTOTAL"}
_HYBRID_PREFIX_RE = re.compile(r"(?i)^hybrid\s*for")

# numeric extraction helpers
_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")
_INT_RE = re.compile(r"[-+]?\d+")

# ------- matrix-wide (site columns) helpers -------
_MEASURE_EXCLUDES = {
    "TOTAL UNITS", "UNITS", "TOTAL", "TOTAL INVENTORY", "AVAILABLE FOR",
    "AVAILABLE", "AVAIL", "ORDERED", "PLANNED", "SALES", "DEL MAR", "DELMAR",
}
_DATE_COL_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")  # e.g., 3/4/2025
_SITE_CODE_RE = re.compile(r"^[0-9A-Z]{1,6}$")         # e.g., 1E, 4EX, 32BX, 3110, etc.

# ------- header detection helpers (for 2024/2025 files) -------
_BASE_HEADER_SET = {"STATUS", "TRAIT", "MATURITY", "PLF"}


def _first_float_or_na(x):
    if x is None:
        return pd.NA
    s = str(x)
    m = _NUM_RE.search(s)
    if not m:
        return pd.NA
    try:
        return float(m.group(0))
    except Exception:
        return pd.NA


def _first_int_or_na(x):
    if x is None:
        return pd.NA
    s = str(x)
    m_int = _INT_RE.search(s)
    if m_int:
        try:
            return int(m_int.group(0))
        except Exception:
            pass
    m_num = _NUM_RE.search(s)
    if m_num:
        try:
            return int(float(m_num.group(0)))
        except Exception:
            return pd.NA
    return pd.NA


def _is_blankish(x):
    s = str(x).strip().upper()
    return s in {"", "NA", "N/A", "NONE", "—", "-", "–"}


def _secure_filename(name: str) -> str:
    name = name.split("/")[-1].split("\\")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:200] or "upload"


def _save_file(filename: str, contents: str) -> Tuple[bool, str]:
    try:
        _, b64 = contents.split(",", 1)
        raw = base64.b64decode(b64)
    except Exception as e:
        return False, f"Failed to decode file payload for {filename}: {e}"

    safe = _secure_filename(filename)
    ext = Path(safe).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        return False, f"Extension '{ext}' not allowed. Only: {sorted(_ALLOWED_EXTS)}"
    try:
        pd.read_csv(io.BytesIO(raw), nrows=3, engine="python")
    except Exception as e:
        return False, f"Validation failed for {safe}: {e}"
    try:
        out_path = DATA_DIR / safe
        out_path.write_bytes(raw)
        return True, f"Saved: {out_path.name}"
    except Exception as e:
        return False, f"Could not write file {safe}: {e}"


def _list_files() -> List[str]:
    return sorted(p.name for p in DATA_DIR.iterdir() if p.is_file())


def _delete_file(filename: str) -> Tuple[bool, str]:
    safe = _secure_filename(filename)
    if safe != filename:
        return False, f"Refusing to delete unexpected path: {filename}"
    target = (DATA_DIR / filename).resolve()
    if target.parent != DATA_DIR.resolve():
        return False, f"Invalid location for deletion: {filename}"
    if not target.exists() or not target.is_file():
        return False, f"File not found: {filename}"
    try:
        target.unlink()
        return True, f"Deleted: {filename}"
    except Exception as e:
        return False, f"Could not delete {filename}: {e}"

# ---------------------------
# Parsing helpers
# ---------------------------

def _to_int_or_na(x):
    try:
        s = str(x).strip()
        if s == "" or s.upper() in {"NA", "N/A", "NONE"}:
            return pd.NA
        s = re.sub(r"[^\d\.-]", "", s)
        return int(float(s))
    except Exception:
        return pd.NA


def _to_float_or_na(x):
    try:
        s = str(x).strip()
        if s == "" or s.upper() in {"NA", "N/A", "NONE"}:
            return pd.NA
        s = re.sub(r"[^\d\.-]", "", s)
        return float(s)
    except Exception:
        return pd.NA


def infer_year_from_filename(path_like: str | Path, default_year: Optional[int] = None) -> Optional[int]:
    text = str(path_like)
    m = re.search(r"(20\d{2})", Path(text).name)
    if not m:
        m = re.search(r"(20\d{2})", str(Path(text).parent))
    return int(m.group(1)) if m else default_year

# ---------------------------
# Legacy wide → long (flexible)
# ---------------------------

def _looks_like_legacy_wide(df: pd.DataFrame) -> bool:
    return any(_HYBRID_PREFIX_RE.match(str(c).strip()) for c in df.columns)


def _find_company_and_label_rows(df: pd.DataFrame) -> Tuple[Optional[int], Optional[int]]:
    """
    Return (company_row_idx, label_row_idx).
    Scan first 10 rows; label row has many QTY/UNITS/etc in 'Hybrid for...' columns.
    Company row is just above label row.
    """
    hybrid_cols = [c for c in df.columns if _HYBRID_PREFIX_RE.match(str(c).strip())]
    if not hybrid_cols:
        return None, None

    max_rows_to_scan = min(10, len(df))
    best_row: Optional[int] = None
    best_hits = -1

    for r in range(1, max_rows_to_scan):  # start at 1 so we can look at r-1
        hits = 0
        row = df.iloc[r]
        for c in hybrid_cols:
            val = str(row[c]).strip().upper()
            if val in _QTY_LABELS:
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best_row = r

    if best_row is None or best_hits <= 0:
        return None, None

    company_row = best_row - 1
    if company_row < 0:
        return None, None
    return company_row, best_row


def _legacy_transform_wide_to_long(input_csv: str, year: Optional[int] = None) -> pd.DataFrame:
    df = pd.read_csv(input_csv, dtype=str)

    hybrid_cols = [c for c in df.columns if _HYBRID_PREFIX_RE.match(str(c).strip())]
    company_row, label_row = _find_company_and_label_rows(df)
    if not hybrid_cols or company_row is None or label_row is None:
        return pd.DataFrame(columns=["STATUS", "MATURITY", "TRAIT", "PLF", "qty", "company", "year"])

    # Build map of hybrid col -> company, only if there's any usable qty below label row
    company_map: dict[str, str] = {}
    for c in hybrid_cols:
        company = str(df.at[company_row, c]).strip()
        label = str(df.at[label_row, c]).strip().upper()
        if not company or label not in _QTY_LABELS:
            continue
        col_after = df[c].iloc[label_row + 1:]
        any_qty = any(not _is_blankish(v) and _first_int_or_na(v) is not pd.NA for v in col_after)
        if any_qty:
            company_map[c] = company

    if not company_map:
        return pd.DataFrame(columns=["STATUS", "MATURITY", "TRAIT", "PLF", "qty", "company", "year"])

    # Descriptor columns: prefer Unnamed:0..3, else first 4 columns
    def _pick_fallback(pos: int) -> Optional[str]:
        return df.columns[pos] if pos < len(df.columns) else None

    col_status = "Unnamed: 0" if "Unnamed: 0" in df.columns else _pick_fallback(0)
    col_mat = "Unnamed: 1" if "Unnamed: 1" in df.columns else _pick_fallback(1)
    col_trait = "Unnamed: 2" if "Unnamed: 2" in df.columns else _pick_fallback(2)
    col_plf = "Unnamed: 3" if "Unnamed: 3" in df.columns else _pick_fallback(3)

    if col_status in df.columns:
        df[col_status] = df[col_status].ffill()

    start_row = label_row + 1

    rows = []
    for idx in range(start_row, len(df)):
        mat = df.at[idx, col_mat] if col_mat in df.columns else None
        trait = df.at[idx, col_trait] if col_trait in df.columns else None
        plf = df.at[idx, col_plf] if col_plf in df.columns else None
        status = df.at[idx, col_status] if col_status in df.columns else None

        if (
            (mat is None or str(mat).strip() == "")
            and (trait is None or str(trait).strip() == "")
            and (plf is None or str(plf).strip() == "")
        ):
            continue

        for c, company in company_map.items():
            if c not in df.columns:
                continue
            qty_raw = df.at[idx, c]
            if _is_blankish(qty_raw):
                continue

            mat_val = _first_float_or_na(mat)
            plf_val = _first_int_or_na(plf)
            qty_val = _first_int_or_na(qty_raw)

            rows.append(
                {
                    "STATUS": (str(status).strip() if status is not None else None),
                    "MATURITY": mat_val,
                    "TRAIT": (str(trait).strip() if trait is not None else None),
                    "PLF": plf_val,
                    "company": str(company).strip() if company is not None else None,
                    "qty": qty_val,
                    "year": int(year) if year is not None else None,
                }
            )

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["STATUS", "MATURITY", "TRAIT", "PLF", "qty", "company", "year"])

    out = out.dropna(subset=["PLF", "qty", "company", "TRAIT"], how="any")
    if out.empty:
        return pd.DataFrame(columns=["STATUS", "MATURITY", "TRAIT", "PLF", "qty", "company", "year"])

    out["qty"] = out["qty"].astype(int)
    out["PLF"] = out["PLF"].astype(int)
    if "MATURITY" in out.columns:
        out["MATURITY"] = out["MATURITY"].astype("Float64")

    if year is not None:
        out["year"] = int(year)
    else:
        out["year"] = infer_year_from_filename(input_csv)

    for col in ["STATUS", "TRAIT", "company"]:
        out[col] = out[col].astype(str).str.strip()
    out.loc[out["company"].isin(["None", "nan", "NaN"]), "company"] = None

    return out.reset_index(drop=True)

# ---------------------------
# Matrix-wide detector (NEW)
# ---------------------------

def _looks_like_matrix_wide(df: pd.DataFrame) -> bool:
    """STATUS/TRAIT/MATURITY/PLF present, and many short all-cap columns after PLF."""
    base = ["STATUS", "TRAIT", "MATURITY", "PLF"]
    if any(c not in df.columns for c in base):
        return False
    candidates = [
        c for c in df.columns
        if c not in base
        and c not in _MEASURE_EXCLUDES
        and not _DATE_COL_RE.fullmatch(str(c))
        and _SITE_CODE_RE.fullmatch(str(c).replace(" ", ""))
    ]
    return len(candidates) >= 5

# ---------------------------
# Header detection loader (NEW)
# ---------------------------

def _detect_header_row_raw(df: pd.DataFrame, max_scan: int = 12) -> Optional[int]:
    """
    Look at the first `max_scan` rows of a no-header read (header=None) to find
    a row that contains STATUS/TRAIT/MATURITY/PLF. Return that row index, else None.
    """
    scan = min(len(df), max_scan)
    for r in range(scan):
        vals = (
            pd.Series(df.iloc[r].tolist())
            .astype(str)
            .str.strip()
            .str.upper()
            .tolist()
        )
        if _BASE_HEADER_SET.issubset(set(vals)):
            return r
    return None


def _load_csv_with_header_detection(csv_path: str) -> pd.DataFrame:
    """
    Robust CSV load that:
      1) reads with header=None,
      2) finds the row that looks like the real header (STATUS/PLF present),
      3) promotes that row to columns and drops the rows above it.
    Falls back to a normal read if detection fails.
    """
    read_kwargs = dict(engine="python", dtype=str, keep_default_na=False, na_values=["", "NA", "N/A"])
    df_try = pd.DataFrame()

    for attempt in (dict(sep=None), dict(sep=","), dict(sep=",", quoting=3)):
        try:
            df_try = pd.read_csv(csv_path, header=None, **read_kwargs, **attempt)
            break
        except Exception:
            df_try = pd.DataFrame()

    if df_try.empty:
        # last ditch standard read
        try:
            return pd.read_csv(csv_path, **read_kwargs)
        except Exception:
            return pd.DataFrame()

    hdr_row = _detect_header_row_raw(df_try)
    if hdr_row is None:
        return df_try  # downstream will try to normalize

    new_cols = (
        pd.Series(df_try.iloc[hdr_row].tolist())
        .astype(str)
        .str.strip()
        .str.replace(r"[\u200b\u200c\u200d\ufeff]", "", regex=True)
    )
    df = df_try.iloc[hdr_row + 1:].copy()
    df.columns = new_cols
    df = df.reset_index(drop=True)
    return df

# ---------------------------
# Tidy-first with legacy/matrix fallback (uses header detection)
# ---------------------------

def transform_pl_csv_flex(csv_path: str, year_hint: int | None = None) -> pd.DataFrame:
    # First peek: if legacy wide, route directly
    try:
        peek = pd.read_csv(csv_path, nrows=8, engine="python", dtype=str)
        if _looks_like_legacy_wide(peek):
            y = year_hint if year_hint is not None else infer_year_from_filename(csv_path)
            return _legacy_transform_wide_to_long(csv_path, y)
    except Exception:
        pass

    # Robust reader with header detection (handles 2024/2025)
    df = _load_csv_with_header_detection(csv_path)

    # If still range-index columns (no header detected), fabricate temp names
    if isinstance(df.columns, pd.RangeIndex):
        df.columns = [f"C{i}" for i in range(len(df.columns))]

    if df.empty:
        y = year_hint if year_hint is not None else infer_year_from_filename(csv_path)
        return _legacy_transform_wide_to_long(csv_path, y)

    # header fixups
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(map(str, col)).strip() for col in df.columns.values]
    df.columns = (
        pd.Series(df.columns)
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.replace(r"[\u200b\u200c\u200d\ufeff]", "", regex=True)
        .str.upper()
        .str.replace(r"\.+$", "", regex=True)
    )
    df = df.drop(columns=[c for c in df.columns if str(c).startswith("UNNAMED")], errors="ignore")

    # aliases
    normalized = {}
    for c in df.columns:
        k = str(c).replace(" ", "")
        if k in ("QTY", "QUANTITY"):
            normalized[c] = "QTY"
        elif k in ("PLF",):
            normalized[c] = "PLF"
        elif k in ("STATUS",):
            normalized[c] = "STATUS"
        elif k in ("MATURITY",):
            normalized[c] = "MATURITY"
        elif k in ("TRAIT",):
            normalized[c] = "TRAIT"
        elif k in ("COMPANY", "SITE", "UNIT"):
            normalized[c] = "COMPANY"
        else:
            normalized[c] = c
    df = df.rename(columns=normalized)

    # ---------- matrix-wide route if no COMPANY ----------
    required = ["STATUS", "MATURITY", "TRAIT", "PLF", "COMPANY"]
    if any(c not in df.columns for c in required):
        if _looks_like_matrix_wide(df):
            base = ["STATUS", "TRAIT", "MATURITY", "PLF"]
            site_cols = [
                c for c in df.columns
                if c not in base
                and c not in _MEASURE_EXCLUDES
                and not _DATE_COL_RE.fullmatch(str(c))
                and _SITE_CODE_RE.fullmatch(str(c).replace(" ", ""))
            ]
            keep_cols = base + site_cols
            slim = df[keep_cols].copy()

            long = slim.melt(id_vars=base, var_name="company", value_name="qty")

            for c in ["STATUS", "TRAIT", "company"]:
                long[c] = long[c].astype(str).str.strip()
            long["STATUS"] = long["STATUS"].str.replace(r"\s+", "", regex=True)
            long["PLF"] = long["PLF"].apply(_to_int_or_na)
            long["MATURITY"] = long["MATURITY"].apply(_to_float_or_na)
            long["qty"] = long["qty"].apply(_to_int_or_na)

            # drop unusable rows (keep zeros)
            long = long.dropna(subset=["PLF", "TRAIT", "company"], how="any")
            long = long[long["qty"].notna()]

            year = year_hint if year_hint is not None else infer_year_from_filename(csv_path)
            long["year"] = int(year) if year is not None else pd.NA

            return (
                long[["STATUS", "MATURITY", "TRAIT", "PLF", "qty", "company", "year"]]
                .drop_duplicates()
                .reset_index(drop=True)
            )

        # If not matrix-wide, fall back to legacy
        y = year_hint if year_hint is not None else infer_year_from_filename(csv_path)
        return _legacy_transform_wide_to_long(csv_path, y)

    # ---------- tidy path with COMPANY present ----------
    keep = ["STATUS", "MATURITY", "TRAIT", "PLF", "COMPANY"] + (["QTY"] if "QTY" in df.columns else [])
    df = df[[c for c in keep if c in df.columns]].copy()

    for c in ["STATUS", "TRAIT", "COMPANY"]:
        df[c] = df[c].astype(str).str.strip()
    df["STATUS"] = df["STATUS"].str.replace(r"\s+", "", regex=True)

    df["PLF"] = df["PLF"].apply(_to_int_or_na)
    df["MATURITY"] = df["MATURITY"].apply(_to_float_or_na)
    if "QTY" in df.columns:
        df["QTY"] = df["QTY"].apply(_to_int_or_na)
    else:
        df["QTY"] = pd.NA

    kept = df[
        df["PLF"].notna()
        & df["TRAIT"].astype(str).str.len().ge(1)
        & df["COMPANY"].astype(str).str.len().ge(1)
    ].copy()

    if kept.empty:
        y = year_hint if year_hint is not None else infer_year_from_filename(csv_path)
        return _legacy_transform_wide_to_long(csv_path, y)

    kept = kept.rename(columns={"QTY": "qty", "COMPANY": "company"})
    kept["company"] = kept["company"].astype(str).str.strip()
    kept = kept[["STATUS", "MATURITY", "TRAIT", "PLF", "qty", "company"]]

    year = year_hint if year_hint is not None else infer_year_from_filename(csv_path)
    kept["year"] = int(year) if year is not None else pd.NA

    return kept.drop_duplicates()

# ---------------------------
# Build + process
# ---------------------------

def build_cleaned_master(data_dir: str | Path, pattern: str = "*.[cC][sS][vV]", out_csv: str | Path | None = None) -> pd.DataFrame:
    data_dir = Path(data_dir)
    paths = sorted(p for p in data_dir.rglob(pattern) if p.name not in _OUTPUT_BASENAMES)
    if not paths:
        raise FileNotFoundError(f"No files matched {pattern} under {data_dir}")

    frames = []
    for p in paths:
        yr = infer_year_from_filename(p)
        try:
            part = transform_pl_csv_flex(str(p), yr)
        except Exception:
            continue
        if not part.empty:
            frames.append(part)

    if not frames:
        df_empty = pd.DataFrame(columns=["STATUS", "MATURITY", "TRAIT", "PLF", "qty", "company", "year"])
        if out_csv:
            Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
            df_empty.to_csv(out_csv, index=False)
            try:
                OUT_CSV_ALIAS.parent.mkdir(parents=True, exist_ok=True)
                df_empty.to_csv(OUT_CSV_ALIAS, index=False)
            except Exception:
                pass
        return df_empty

    df_all = pd.concat(frames, ignore_index=True).drop_duplicates()
    if out_csv:
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        df_all.to_csv(out_csv, index=False)
        try:
            OUT_CSV_ALIAS.parent.mkdir(parents=True, exist_ok=True)
            df_all.to_csv(OUT_CSV_ALIAS, index=False)
        except Exception:
            pass
    return df_all


def process_all(input_dir: Path) -> Tuple[bool, str, int]:
    try:
        df = build_cleaned_master(input_dir, pattern="*.[cC][sS][vV]", out_csv=OUT_CSV)
    except FileNotFoundError:
        return False, f"No CSV files found in {input_dir.resolve()}.", 0
    except Exception as e:
        return False, f"Processing failed: {e}", 0

    rows = 0 if df is None or df.empty else len(df)
    return (rows > 0), f"Processed CSVs; wrote {rows} rows to {OUT_CSV.name} and {OUT_CSV_ALIAS.name}.", rows


def diagnose_inputs(data_dir: Path) -> pd.DataFrame:
    records = []
    for p in sorted(Path(data_dir).rglob("*.[cC][sS][vV]")):
        if p.name in _OUTPUT_BASENAMES:
            continue
        info = {"file": p.name, "parser_used": "", "rows_out": 0, "note": ""}
        try:
            peek = pd.read_csv(p, nrows=8, engine="python", dtype=str)
            if _looks_like_legacy_wide(peek):
                info["parser_used"] = "legacy_wide_to_long"
                out = _legacy_transform_wide_to_long(str(p), infer_year_from_filename(p))
            else:
                info["parser_used"] = "tidy_or_matrix_or_fallback"
                out = transform_pl_csv_flex(str(p), infer_year_from_filename(p))
            info["rows_out"] = 0 if out is None else len(out)
            if info["rows_out"] == 0:
                info["note"] = "No rows produced (check headers, site columns, or numeric cells)"
        except Exception as e:
            info["note"] = f"Error: {e}"
        records.append(info)
    return pd.DataFrame.from_records(records)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = dbc.Container(
    [
        html.H1("Upload Data"),
        html.P("Add CSV files to the app's data/ folder. Click Process to build a unified CSV."),
        dbc.Alert(
            [
                html.Div([html.Strong("Uploads folder: "), html.Code(str(DATA_DIR))]),
                html.Div([html.Strong("Processed output: "), html.Code(str(OUT_CSV))]),
                html.Div([html.Strong("Alias for descriptive page: "), html.Code(str(OUT_CSV_ALIAS))]),
            ],
            color="info",
            className="mb-3",
        ),
        dcc.Upload(
            id="upload-input",
            children=html.Div(["Drag & Drop or ", html.A("Select Files"), " (CSV)"]),
            multiple=True,
            style={
                "width": "100%",
                "height": "120px",
                "lineHeight": "120px",
                "borderWidth": "2px",
                "borderStyle": "dashed",
                "borderRadius": "12px",
                "textAlign": "center",
                "cursor": "pointer",
            },
        ),
        html.Div(id="upload-status", className="mt-3"),
        dbc.Row(
            [
                dbc.Col(dbc.Button("Process uploaded files", id="process-btn", color="primary", className="mt-2", n_clicks=0), width="auto"),
                dbc.Col(
                    dbc.Button(
                        "Download processed CSV",
                        id="download-btn",
                        color="success",
                        className="mt-2",
                        n_clicks=0,
                        disabled=not (OUT_CSV.exists() or OUT_CSV_ALIAS.exists()),
                    ),
                    width="auto",
                ),
                dbc.Col(dbc.Button("Reset processed file", id="reset-btn", color="warning", className="mt-2", n_clicks=0), width="auto"),
            ],
            className="g-2",
        ),
        html.Div(id="process-status", className="mt-3"),
        html.Div(id="delete-status", className="mt-2"),
        dcc.Download(id="download-csv"),
        html.Hr(),
        html.H4("Files in data/"),
        html.Div(id="file-list"),
        dcc.Store(id="has-output", data=(OUT_CSV.exists() or OUT_CSV_ALIAS.exists())),
    ],
    fluid=True,
)

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("upload-status", "children"),
    Input("upload-input", "contents"),
    State("upload-input", "filename"),
    prevent_initial_call=True,
)
def handle_upload(contents_list, filenames):
    if not contents_list or not filenames:
        return no_update
    messages = []
    for contents, fn in zip(contents_list, filenames):
        ok, msg = _save_file(fn, contents)
        color = "success" if ok else "danger"
        messages.append(dbc.Alert(msg, color=color, className="mb-2"))
    return messages


@callback(
    Output("file-list", "children"),
    Input("upload-status", "children"),
    Input("delete-status", "children"),
    Input("process-status", "children"),
    prevent_initial_call=False,
)
def refresh_list(_up, _del, _proc):
    files = _list_files()
    if not files:
        return html.P("No files yet.")
    items = []
    for f in files:
        items.append(
            dbc.ListGroupItem(
                dbc.Row(
                    [
                        dbc.Col(html.Code(f), md=True),
                        dbc.Col(
                            dbc.Button("Delete", id={"type": "delete-file", "name": f}, color="danger", size="sm", n_clicks=0, className="float-end"),
                            width="auto",
                        ),
                    ],
                    className="align-items-center",
                    justify="between",
                ),
            )
        )
    return dbc.ListGroup(items, flush=True)


@callback(
    Output("process-status", "children"),
    Output("has-output", "data"),
    Output("download-btn", "disabled"),
    Input("process-btn", "n_clicks"),
    Input("reset-btn", "n_clicks"),
    prevent_initial_call=True,
)
def process_or_reset(process_clicks, reset_clicks):
    trig = getattr(ctx, "triggered_id", None)
    if not trig:
        if ctx.triggered and len(ctx.triggered) > 0:
            trig = ctx.triggered[0]["prop_id"].split(".")[0]
        else:
            return no_update, no_update, no_update
    try:
        if trig == "process-btn":
            paths = sorted(p for p in DATA_DIR.rglob("*.[cC][sS][vV]") if p.name not in _OUTPUT_BASENAMES)
            file_list = [p.name for p in paths]
            preface = dbc.Alert(
                f"Process clicked. Found {len(file_list)} CSVs under {DATA_DIR}. Files: {file_list}",
                color="info",
                className="mb-2",
            )
            ok, msg, rows = process_all(DATA_DIR)
            if not ok:
                diag = diagnose_inputs(DATA_DIR)
                try:
                    table = dbc.Table.from_dataframe(diag, striped=True, bordered=True, hover=True, size="sm") if not diag.empty else html.P("No diagnostics available.")
                except Exception:
                    table = html.Pre(diag.to_string(index=False)) if not diag.empty else html.P("No diagnostics available.")
                alert = dbc.Alert(msg, color="danger", className="mb-2")
                return html.Div([preface, alert, html.Hr(), html.H5("Why 0 rows? Diagnostic report"), table]), False, True
            alert = dbc.Alert(msg, color="success", className="mb-2")
            return html.Div([preface, alert]), True, False

        if trig == "reset-btn":
            preface = dbc.Alert("Reset clicked.", color="warning", className="mb-2")
            if OUT_CSV.exists() or OUT_CSV_ALIAS.exists():
                try:
                    msgs = []
                    if OUT_CSV.exists():
                        OUT_CSV.unlink()
                        msgs.append(OUT_CSV.name)
                    if OUT_CSV_ALIAS.exists():
                        OUT_CSV_ALIAS.unlink()
                        msgs.append(OUT_CSV_ALIAS.name)
                    alert = dbc.Alert(
                        f"Deleted: {', '.join(msgs)}. Uploads in {DATA_DIR} were preserved.",
                        color="warning",
                        className="mb-2",
                    )
                    return html.Div([preface, alert]), False, True
                except Exception as e:
                    alert = dbc.Alert(f"Could not delete processed files: {e}", color="danger", className="mb-2")
                    disabled = not (OUT_CSV.exists() or OUT_CSV_ALIAS.exists())
                    return html.Div([preface, alert]), (OUT_CSV.exists() or OUT_CSV_ALIAS.exists()), disabled
            else:
                alert = dbc.Alert("No processed file to delete.", color="info", className="mb-2")
                return html.Div([preface, alert]), False, True

        return no_update, no_update, no_update
    except Exception as e:
        err = dbc.Alert(f"Unexpected error in process/reset: {e}", color="danger", className="mb-2")
        return err, (OUT_CSV.exists() or OUT_CSV_ALIAS.exists()), not (OUT_CSV.exists() or OUT_CSV_ALIAS.exists())


@callback(
    Output("delete-status", "children"),
    Input({"type": "delete-file", "name": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def delete_one_file(n_clicks_list):
    if not n_clicks_list or all((not n or n == 0) for n in n_clicks_list):
        return no_update
    trig = ctx.triggered_id
    if not isinstance(trig, dict) or trig.get("type") != "delete-file":
        return no_update
    filename = trig.get("name")
    ok, msg = _delete_file(filename)
    return dbc.Alert(msg, color=("success" if ok else "danger"), className="mb-2")


@callback(
    Output("download-csv", "data"),
    Input("download-btn", "n_clicks"),
    State("has-output", "data"),
    prevent_initial_call=True,
)
def trigger_download(n_clicks, has_output):
    if not n_clicks or not has_output:
        return no_update
    target = OUT_CSV if OUT_CSV.exists() and OUT_CSV.is_file() else OUT_CSV_ALIAS
    if not target.exists() or not target.is_file():
        return no_update
    from dash import dcc as _dcc
    return _dcc.send_file(str(target))
