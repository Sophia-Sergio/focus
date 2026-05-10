"""
Count PDF files per class folder inside 2026-03/pdfs/Avance Regiones.
Outputs a CSV with: region, school, class, pdf_count

Usage:
    python3 scripts/count_json_by_folder.py
    python3 scripts/count_json_by_folder.py <input_dir> <output_csv>

Defaults:
    input_dir:  2026-03/pdfs/Avance Regiones
    output_csv: scripts/output/pdfs_count_by_folder.csv
"""
import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent / "2026-03" / "pdfs" / "Avance Regiones"
OUTPUT_FILE = Path(__file__).parent / "output" / "pdfs_count_by_folder.csv"


def count_pdf_files(folder: Path) -> int:
    return sum(1 for f in folder.iterdir() if f.suffix == ".pdf" and f.is_file())


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_FILE

    rows = []
    for region_dir in sorted(base.iterdir()):
        if not region_dir.is_dir():
            continue
        for school_dir in sorted(region_dir.iterdir()):
            if not school_dir.is_dir():
                continue
            for class_dir in sorted(school_dir.iterdir()):
                if not class_dir.is_dir():
                    continue
                count = count_pdf_files(class_dir)
                rows.append({
                    "region": region_dir.name,
                    "school": school_dir.name,
                    "class": class_dir.name,
                    "pdf_count": count,
                })

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["region", "school", "class", "pdf_count"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()
