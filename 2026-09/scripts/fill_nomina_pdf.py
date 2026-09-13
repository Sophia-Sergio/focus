"""Pre-print one student's nómina data onto a `Diagramación *.pdf` form.

The rules this implements are documented in `2026-09/REGLAS_LLENADO.md`; they
live in `overlay.py` and are shared with `build_batches.py`.

    python3 2026-09/scripts/fill_nomina_pdf.py \\
        --pdf "2026-09/intrumentos/first_pages/Diagramación 4-5B_Control.pdf" \\
        --folio 46175A8 --out /tmp/ejemplo.pdf
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

from build_batches import NOMINA, instrument_index, load_students
from compose import BatchWriter
from overlay import Student


def form_type_of(pdf_path: Path) -> tuple[str, tuple[int, int]]:
    """`Diagramación 4-5B_Control.pdf` -> (`C2_4y5_Control_B`, (4, 5)).

    The cohort is not in the filename; it is implied by the grade pair.
    """
    m = re.fullmatch(r"Diagramación (\d)-(\d)([AB])_(Control|Tratamiento)",
                     unicodedata.normalize("NFC", pdf_path.stem))
    if not m:
        raise SystemExit(f"unexpected form filename: {pdf_path.name}")
    lo, hi, tipo, grupo = m.groups()
    cohorte = 1 if f"{lo}y{hi}" in ("5y6", "7y8") else 2
    return f"C{cohorte}_{lo}y{hi}_{grupo}_{tipo}", (int(lo), int(hi))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--nomina", type=Path, default=NOMINA)
    ap.add_argument("--folio", help="folio to print")
    ap.add_argument("--region", help="pick the first student of this región on this form")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    students = [s for s, _ in load_students(args.nomina)]
    expected, grades = form_type_of(args.pdf)

    if args.folio:
        by_folio = {s.folio: s for s in students}
        if args.folio not in by_folio:
            raise SystemExit(f"folio {args.folio} is not in the nómina")
        student: Student = by_folio[args.folio]
    else:
        pool = [s for s in students if s.tipo_formulario == expected
                and (not args.region or s.region == args.region)]
        if not pool:
            raise SystemExit(f"no student matches {expected} / region={args.region}")
        student = pool[0]

    if student.tipo_formulario != expected:
        raise SystemExit(f"folio {student.folio} belongs to {student.tipo_formulario}, "
                         f"but {args.pdf.name} is {expected}")

    writer = BatchWriter(args.pdf)
    warnings = writer.add_student(student, grades)
    writer.save(args.out)

    print(f"folio {student.folio} -> {args.out}")
    print(f"  {student.nombre_completo} | {student.nom_est} | {student.curso}{student.letra} "
          f"| {student.sexo} | RUN {student.rut_num}-{student.rut_dv} "
          f"({'válido' if student.rut_valido else 'inválido'})")
    for msg in warnings:
        print(f"  aviso: {msg}")


if __name__ == "__main__":
    main()
