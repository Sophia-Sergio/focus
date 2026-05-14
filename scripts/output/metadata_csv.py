#!/usr/bin/env python3
"""
Usage:
    python3 metadata_csv.py <folder>

Recursively finds all JSON files in <folder>, extracts metadata fields, and
writes metadata.csv into that same folder.
"""

import csv
import json
import sys
from pathlib import Path

FIELDS = ["survey_id", "student_name", "student_run", "valid_rut", "student_age"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python metadata_csv.py <folder>")
        sys.exit(1)

    folder = Path(sys.argv[1])
    if not folder.is_dir():
        print(f"Error: not a directory: {folder}")
        sys.exit(1)

    rows = []
    for json_file in sorted(folder.rglob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            meta = data.get("metadata", {})
            rows.append({f: meta.get(f, "") for f in FIELDS})
        except Exception as e:
            print(f"Skipping {json_file.name}: {e}")

    if not rows:
        print("No JSON files found.")
        sys.exit(0)

    output = folder / "metadata.csv"
    with open(output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ {len(rows)} rows → {output}")


if __name__ == "__main__":
    main()
