#!/usr/bin/env python3
"""
Merge all sheets of each .xlsx in 2026-03/bd/ into a single CSV per file.

All sheets are assumed to share the same structure. The first row of each
sheet is treated as the header.

Usage:
    python3 2026-03/scripts/merge_sheets.py [bd_folder]
"""

import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install pandas openpyxl")
    import pandas as pd

DEFAULT_BD = Path(__file__).parent.parent / "bd"

RENAME_COLS = {
    "student_firstname": "nombres_ai",
    "first_name": "nombres",
    "student_lastname": "apellidos_ai",
    "last_name": "apellidos",
    "student_run": "rut_ai",
    "student_age": "edad_ai",
    "age": "edad_rev",
    "check": "check_nom",
    "check.1": "check_ape",
    "check.2": "check_rut",
    "check.3": "check_edad",
    "rut": "rut_rev",
}


def merge_file(xlsx_path: Path) -> dict:
    xl = pd.ExcelFile(xlsx_path, engine="openpyxl")
    sheets = [s for s in xl.sheet_names if not s.lower().startswith("colegio-")]

    dfs = []
    sheet_counts = {}
    for s in sheets:
        df = pd.read_excel(xl, sheet_name=s, header=0)
        df.insert(0, "sheet", s)
        dfs.append(df)
        sheet_counts[s] = sheet_counts.get(s, 0) + len(df)

    merged = pd.concat(dfs, ignore_index=True)
    merged.rename(columns=RENAME_COLS, inplace=True)
    csv_path = xlsx_path.parent / (xlsx_path.stem + ".csv")
    merged.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"  {xlsx_path.name} ({len(sheets)} sheets, {len(merged)} rows) → {csv_path.name}")
    return sheet_counts


def main():
    bd_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BD

    if not bd_dir.is_dir():
        print(f"Error: not a directory: {bd_dir}")
        sys.exit(1)

    xlsx_files = sorted(bd_dir.glob("*.xlsx"))
    if not xlsx_files:
        print(f"No .xlsx files found in {bd_dir}")
        sys.exit(0)

    print(f"Merging {len(xlsx_files)} file(s) from {bd_dir}\n")

    totals: dict = {}
    for xlsx in xlsx_files:
        counts = merge_file(xlsx)
        for name, n in counts.items():
            totals[name] = totals.get(name, 0) + n

    print("\nRows per reviewer:")
    for name, n in sorted(totals.items(), key=lambda x: -x[1]):
        print(f"  {name}: {n}")

    print("\nTotal per reviewer × 50:")
    for name, n in sorted(totals.items(), key=lambda x: -x[1]):
        print(f"  {name}: {n * 50}")
    print(f"\nDone.")


if __name__ == "__main__":
    main()
