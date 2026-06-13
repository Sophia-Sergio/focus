#!/usr/bin/env python3
"""Output a CSV of region,school subfolders under 2026-03/pdfs/Avance Regiones."""

import csv
import sys
from pathlib import Path

base = Path(__file__).parent.parent / "2026-03/pdfs/Avance Regiones"

writer = csv.writer(sys.stdout)
writer.writerow(["region", "school"])

for region in sorted(base.iterdir()):
    if not region.is_dir():
        continue
    for school in sorted(region.iterdir()):
        if school.is_dir():
            writer.writerow([region.name, school.name])
