"""Build the print batches: one folder per región, one PDF per Tipo de Formulario.

    2026-09/impresion/
      Biobío/
        C1_5y6_Control_A.pdf     <- one pre-printed cover per Biobío student
        ...
      manifest.csv

A batch holds **only the cover page** of each student — one page per student.
The rest of the instrument is identical for everyone and is printed separately.
The fill rules are in `2026-09/REGLAS_LLENADO.md`.

    python3 2026-09/scripts/build/build_batches.py                     # everything
    python3 2026-09/scripts/build/build_batches.py --region Biobío     # one región
    python3 2026-09/scripts/build/build_batches.py --full-survey       # cover + pages 2+
"""

from __future__ import annotations

import argparse
import csv
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from compose import BatchWriter
from overlay import RUT_VALIDO, Student

REPO = Path(__file__).resolve().parents[3]
BASE = REPO / "2026-09"
NOMINA = BASE / "Nomina_estudiantes_C1yC2.xlsx"
SHEET = "Nómina pre digitacion"
INSTRUMENTOS = BASE / "intrumentos"
COVERS = INSTRUMENTOS / "first_pages"
OUT = BASE / "impresion"


def load_students(path: Path = NOMINA) -> list[tuple[Student, int]]:
    """Students in nómina order, each with its `rbd` for sorting."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[SHEET]
    rows = ws.iter_rows(values_only=True)
    idx = {h: i for i, h in enumerate(next(rows)) if h}

    def txt(row, col):
        v = row[idx[col]]
        return "" if v is None else str(v).strip()

    out = []
    for row in rows:
        if row[idx["folio"]] is None:
            continue
        out.append((Student(
            folio=txt(row, "folio"),
            nombre_completo=txt(row, "nombre_completo"),
            nom_est=txt(row, "nom_est"),
            sexo=txt(row, "sexo"),
            curso=int(row[idx["Curso 2026"]]),
            letra=txt(row, "letra"),
            rut_num=txt(row, "rut_num"),
            rut_dv=txt(row, "rut_dv"),
            rut_valido=txt(row, "validacion_rut") == RUT_VALIDO,
            tipo_formulario=txt(row, "Tipo de Formulario"),
            region=txt(row, "Región"),
        ), int(row[idx["rbd"]] or 0)))
    return out


def instrument_index(full_survey: bool) -> dict[str, tuple[Path, tuple[int, int]]]:
    """Map each `Tipo de Formulario` to its source PDF and its grade pair."""
    folder = INSTRUMENTOS if full_survey else COVERS
    index: dict[str, tuple[Path, tuple[int, int]]] = {}
    for pdf in folder.glob("*.pdf"):
        m = re.fullmatch(r"Diagramación (\d)-(\d)([AB])_(Control|Tratamiento)",
                         unicodedata.normalize("NFC", pdf.stem))
        if not m:
            continue
        lo, hi, tipo, grupo = m.groups()
        # Cohort is implied by the grade pair: 5y6/7y8 -> C1, 4y5/6y7 -> C2.
        cohorte = 1 if f"{lo}y{hi}" in ("5y6", "7y8") else 2
        index[f"C{cohorte}_{lo}y{hi}_{grupo}_{tipo}"] = (pdf, (int(lo), int(hi)))
    return index


def safe_dir(name: str) -> str:
    return name.replace("/", "-").strip() or "sin_region"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nomina", type=Path, default=NOMINA)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--region", action="append", help="limit to these regiones")
    ap.add_argument("--full-survey", action="store_true",
                    help="include pages 2+ of the instrument after each cover")
    ap.add_argument("--limit", type=int, help="cap students per batch (for a smoke test)")
    args = ap.parse_args()

    students = load_students(args.nomina)
    instruments = instrument_index(args.full_survey)

    batches: dict[tuple[str, str], list[tuple[Student, int]]] = defaultdict(list)
    for student, rbd in students:
        if args.region and student.region not in args.region:
            continue
        batches[(student.region, student.tipo_formulario)].append((student, rbd))

    manifest: list[dict] = []
    started = time.time()
    for (region, tipo), group in sorted(batches.items()):
        if tipo not in instruments:
            print(f"!! no instrument for {tipo}; skipping {region}")
            continue
        instrument, grades = instruments[tipo]
        # Print order: school, then course, then section, then name.
        group.sort(key=lambda sr: (sr[1], sr[0].curso, sr[0].letra, sr[0].nombre_completo))
        if args.limit:
            group = group[:args.limit]

        writer = BatchWriter(instrument)
        counts: Counter[str] = Counter()
        for student, _ in group:
            for w in writer.add_student(student, grades):
                counts[re.sub(r"\d+", "N", w.split(";")[0].split("(")[0].strip())] += 1

        dest = args.out / safe_dir(region) / f"{tipo}.pdf"
        writer.save(dest)
        size_mb = dest.stat().st_size / 1e6
        print(f"{region:12} {tipo:22} {len(group):5} students  "
              f"{len(group) * len(writer.shared):6} pages  {size_mb:7.2f} MB")
        for msg, n in counts.most_common():
            print(f"{'':12} {'':22} aviso x{n}: {msg}")
        manifest.append({
            "region": region,
            "tipo_formulario": tipo,
            "instrumento": instrument.name,
            "estudiantes": len(group),
            "paginas": len(group) * len(writer.shared),
            "archivo": str(dest.relative_to(args.out)),
            "mb": round(size_mb, 2),
            "avisos": "; ".join(f"{m} x{n}" for m, n in counts.most_common()),
        })

    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0]))
        w.writeheader()
        w.writerows(manifest)

    total = sum(m["estudiantes"] for m in manifest)
    mb = sum(m["mb"] for m in manifest)
    print(f"\n{len(manifest)} batches, {total} students, {mb:.1f} MB total, "
          f"{time.time() - started:.0f}s -> {args.out}")


if __name__ == "__main__":
    main()
