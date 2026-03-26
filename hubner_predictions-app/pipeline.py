from pathlib import Path
import re
import pandas as pd

IN_DIR  = Path("datafile")
GLOB    = "*.csv"
OUT_CSV = Path(r"C:\Users\rithv\Downloads\Cleaned\df_cleaned_all.csv")

BAD_STATUS = {"", "QTY", "COMPANY", "UNITS", "UNIT", "COUNT", "TOTAL", "SUBTOTAL"}

def infer_year(name: str) -> str | None:
    m = re.search(r"(20\d{2})", name)
    return m.group(1) if m else None

def make_unique(names):
    seen, out = {}, []
    for c in map(str, names):
        c = c.strip()
        if c in seen:
            seen[c] += 1
            out.append(f"{c}.{seen[c]}")
        else:
            seen[c] = 0
            out.append(c)
    return out

def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    keep = [c for c in df.columns if not str(c).strip().upper().startswith("UNNAMED")]
    df = df[keep]
    df.columns = [str(c).strip() for c in df.columns]
    df.columns = make_unique(df.columns)
    return df

def sniff_header_row(path: Path, max_rows: int = 40) -> int | None:
    """
    Look at the first `max_rows` lines and return the row index that looks like the
    *real* header. We accept rows that contain all four base labels (any order).
    """
    try:
        probe = pd.read_csv(path, header=None, nrows=max_rows, engine="python",
                            sep=None, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except Exception:
        probe = pd.read_csv(path, header=None, nrows=max_rows, encoding="utf-8-sig",
                            dtype=str, keep_default_na=False)
    needed = {"STATUS","MATURITY","TRAIT","PLF"}
    for i in range(len(probe)):
        labels = set(str(x).strip().upper() for x in probe.iloc[i].tolist())
        if needed.issubset(labels):
            return i
    return None  # not found

def read_csv_safely(path: Path) -> pd.DataFrame:
    # 1) try to detect a later header row (handles 2024/2025)
    hdr = sniff_header_row(path)
    try:
        return pd.read_csv(path, engine="python", sep=None, encoding="utf-8-sig",
                           dtype=str, keep_default_na=False, header=hdr)
    except Exception:
        return pd.read_csv(path, encoding="utf-8-sig", dtype=str,
                           keep_default_na=False, header=hdr)

def clean_one(csv_path: Path) -> pd.DataFrame:
    raw = read_csv_safely(csv_path)
    print(f"    -> columns={len(raw.columns)} ; first5={list(map(str, raw.columns[:5]))}")

    df = normalize_cols(raw)
    if len(df.columns) < 5:
        print("    !! Skipping: <5 columns after read. Check delimiter/header lines.")
        return pd.DataFrame(columns=["STATUS","MATURITY","TRAIT","PLF","company","qty","year"])

    # Coerce the first four columns to our base names by *position*
    base_orig = list(df.columns[:4])
    df.rename(columns={base_orig[0]:"STATUS", base_orig[1]:"MATURITY",
                       base_orig[2]:"TRAIT",  base_orig[3]:"PLF"}, inplace=True)
    df.columns = make_unique(df.columns)

    companies = list(df.columns[4:])
    chunks = []
    for comp in companies:
        s = df[comp].astype(str).str.strip()
        mask = s != ""
        if not mask.any():
            continue
        block = df.loc[mask, ["STATUS","MATURITY","TRAIT","PLF"]].copy()
        block["company"] = comp
        block["qty"] = pd.to_numeric(s[mask], errors="coerce")
        chunks.append(block)

    if not chunks:
        return pd.DataFrame(columns=["STATUS","MATURITY","TRAIT","PLF","company","qty","year"])

    out = pd.concat(chunks, ignore_index=True)
    out["year"] = infer_year(csv_path.name)

    # drop section headers / totals / blanks
    mask_all_blank_base = (out[["STATUS","MATURITY","TRAIT","PLF"]]
                           .apply(lambda s: s.astype(str).str.strip() == "").all(axis=1))
    mask_bad_status = out["STATUS"].astype(str).str.strip().str.upper().isin(BAD_STATUS)
    out = out.loc[~mask_all_blank_base & ~mask_bad_status & out["qty"].notna()].copy()

    for c in ["STATUS","MATURITY","TRAIT","PLF","company"]:
        out[c] = out[c].astype(str).str.strip()

    return out[["STATUS","MATURITY","TRAIT","PLF","company","qty","year"]]

def main():
    files = sorted(IN_DIR.glob(GLOB))
    print("Files I can see:")
    for f in files:
        print("  -", f.name)
    if not files:
        print(f"\nNo CSVs found in {IN_DIR.resolve()}.")
        return

    all_df = []
    print(f"\nProcessing {len(files)} file(s):")
    for f in files:
        one = clean_one(f)
        print(f"  {f.name:40s} -> rows kept: {len(one)}")
        if not one.empty:
            all_df.append(one)

    final = pd.concat(all_df, ignore_index=True) if all_df else pd.DataFrame(
        columns=["STATUS","MATURITY","TRAIT","PLF","company","qty","year"]
    )
    final.drop_duplicates(inplace=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUT_CSV, index=False)

    # sanity: rows per year
    if not final.empty:
        per_year = final["year"].value_counts(dropna=False).sort_index()
        print("\nRows per year:")
        print(per_year.to_string())

    print("\nSummary")
    print("-------")
    print(f"Files processed : {len(files)}")
    print(f"Final rows      : {len(final)}")
    print(f"Output          : {OUT_CSV.resolve()}")

if __name__ == "__main__":
    main()
