#!/usr/bin/env python3
"""Sample 25 random rows from each consolidated CSV, copy to test folder with matching PDFs."""

import csv
import random
import shutil
from pathlib import Path

BASE = Path("/Users/sergiotorres/code/personal/focus/2026-03")
AVANCE = BASE / "pdfs" / "Avance Regiones"
TEST = BASE / "test"
TEST.mkdir(parents=True, exist_ok=True)

CSVS = [
    ("4-5_consolidated.csv", 25),
    ("6-7_consolidated.csv", 25),
]

all_selected_ids = []

for csv_name, n in CSVS:
    src = AVANCE / csv_name
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    selected = random.sample(rows, n)
    selected_ids = [r["survey_id"] for r in selected]
    all_selected_ids.extend(selected_ids)

    dst = TEST / csv_name
    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected)

    print(f"{csv_name}: selected {len(selected)} rows → {dst}")
    for sid in selected_ids:
        print(f"  {sid}")

# Build a map of survey_id → pdf path from the full Avance Regiones tree
print("\nSearching for PDFs...")
pdf_map = {}
for pdf in AVANCE.rglob("*.pdf"):
    sid = pdf.stem
    pdf_map[sid] = pdf

found = 0
missing = []
for sid in all_selected_ids:
    if sid in pdf_map:
        dst_pdf = TEST / f"{sid}.pdf"
        shutil.copy2(pdf_map[sid], dst_pdf)
        found += 1
    else:
        missing.append(sid)

print(f"\nCopied {found} PDFs to {TEST}")
if missing:
    print(f"Missing PDFs for {len(missing)} survey_ids:")
    for sid in missing:
        print(f"  {sid}")
