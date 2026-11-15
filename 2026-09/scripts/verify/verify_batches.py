"""Reconcile `2026-09/impresion/` against the nómina, and write the summary.

Every page in every batch is checked end to end: its overlay content stream is
pulled back out of the PDF and compared byte-for-byte with what the rules produce
for the student it claims to be. That catches a lost student, a duplicated one, a
page written against the wrong form, and any drift between the rules and what was
actually printed.

    python3 2026-09/scripts/verify/verify_batches.py [--out 2026-09/VERIFICACION.md]
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from pypdf import PdfReader

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
from build_batches import NOMINA, OUT, instrument_index, load_students, safe_dir
from form_geometry import detect
from overlay import ROW_GAP, free_space, render, to_cells, wrap

TJ = re.compile(rb"\((.*?)\) Tj")


def overlay_streams(pdf: Path) -> list[bytes]:
    """The per-page overlay content stream of every page in a batch."""
    reader = PdfReader(str(pdf))
    out = []
    for page in reader.pages:
        contents = page["/Contents"]   # resolves the indirect reference
        # Cover pages are [q, artwork, Q, overlay]; anything else has no overlay.
        out.append(contents[-1].get_object().get_data()
                   if isinstance(contents, list) and len(contents) == 4 else b"")
    return out


def folio_of(stream: bytes) -> str:
    m = TJ.search(stream)
    return m.group(1).decode("cp1252") if m else ""


def classify(geo, student, grades) -> list[str]:
    """Which rule branches this student exercises, for the coverage table."""
    tags = []
    for label, text, grid in (("nombre", student.nombre_completo, geo.nombre),
                              ("establecimiento", student.nom_est, geo.establecimiento)):
        lines = wrap(text, len(grid.cells))
        if len(lines) == 1:
            tags.append(f"{label}: 1 fila")
        else:
            needed = (len(lines) - 1) * (grid.frame.y1 - grid.frame.y0 + ROW_GAP)
            where = "abajo" if free_space(geo, grid.frame, -1) >= needed else "arriba"
            tags.append(f"{label}: {len(lines)} filas ({where})")

    if not student.rut_valido or not student.rut_num:
        tags.append("RUN: en blanco (no válido)")
    else:
        extra = len(student.rut_num) - (len(geo.run.cells) - 1)
        tags.append("RUN: impreso" if extra <= 0 else
                    f"RUN: +{extra} casilla(s)" if extra <= 1 else
                    "RUN: en blanco (no cabe)")

    tags.append(f"sexo: {'marcado' if student.sexo in ('Hombre', 'Mujer') else 'sin marcar'}")
    tags.append("letra: caja dibujada" if geo.letra is None else "letra: impresa")
    tags.append(f"curso: {'marcado' if student.curso in grades else 'fuera del formulario'}")
    return tags


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--impresion", type=Path, default=OUT)
    ap.add_argument("--nomina", type=Path, default=NOMINA)
    ap.add_argument("--out", type=Path, default=NOMINA.parent / "VERIFICACION.md")
    args = ap.parse_args()

    students = [s for s, _ in load_students(args.nomina)]
    by_folio = {s.folio: s for s in students}
    instruments = instrument_index(full_survey=False)

    expected: dict[tuple[str, str], set[str]] = defaultdict(set)
    for s in students:
        expected[(s.region, s.tipo_formulario)].add(s.folio)

    geo_cache: dict[Path, object] = {}
    problems: list[str] = []
    seen: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    rows: list[dict] = []

    found_files = {p.resolve() for p in args.impresion.glob("*/*.pdf")}
    for (region, tipo), folios in sorted(expected.items()):
        pdf = args.impresion / safe_dir(region) / f"{tipo}.pdf"
        if not pdf.exists():
            problems.append(f"missing batch: {region} / {tipo} ({len(folios)} students)")
            continue
        found_files.discard(pdf.resolve())

        instrument, grades = instruments[tipo]
        if instrument not in geo_cache:      # 16 instruments, 56 batches
            geo_cache[instrument] = detect(str(instrument))
        geo = geo_cache[instrument]

        streams = overlay_streams(pdf)
        in_pdf = [folio_of(s) for s in streams]
        seen.update(in_pdf)

        mismatched = 0
        for folio, stream in zip(in_pdf, streams):
            student = by_folio.get(folio)
            if student is None:
                problems.append(f"{pdf.name}: page folio {folio!r} is not in the nómina")
                continue
            if student.tipo_formulario != tipo or student.region != region:
                problems.append(f"{pdf.name}: folio {folio} belongs to "
                                f"{student.region}/{student.tipo_formulario}")
                continue
            ops, _ = render(geo, student, grades)
            if ops.encode("latin-1") != stream:
                mismatched += 1
            for t in classify(geo, student, grades):
                tags[t] += 1

        if mismatched:
            problems.append(f"{pdf.name}: {mismatched} page(s) differ from the rules")
        missing = folios - set(in_pdf)
        if missing:
            problems.append(f"{pdf.name}: {len(missing)} student(s) missing, "
                            f"e.g. {sorted(missing)[:3]}")

        rows.append({
            "region": region, "tipo": tipo, "esperados": len(folios),
            "paginas": len(streams), "instrumento": instrument.name,
            "mb": round(pdf.stat().st_size / 1e6, 2),
        })

    for extra in sorted(found_files):
        problems.append(f"unexpected batch file: {extra.relative_to(args.impresion)}")
    for folio, n in seen.items():
        if n > 1:
            problems.append(f"folio {folio} appears {n} times")
    for s in students:
        if s.folio not in seen:
            problems.append(f"folio {s.folio} ({s.region}/{s.tipo_formulario}) never printed")

    write_report(args.out, args.impresion, rows, tags, problems, len(students), len(seen))
    print(f"{len(rows)} batches, {sum(r['paginas'] for r in rows)} pages, "
          f"{len(seen)}/{len(students)} folios accounted for")
    print(("OK: no problems found" if not problems
           else f"{len(problems)} problem(s):\n  " + "\n  ".join(problems[:20])))
    print(f"-> {args.out}")


def write_report(out: Path, impresion: Path, rows, tags, problems, total, seen) -> None:
    by_region: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_region[r["region"]].append(r)

    L = [f"# Verificación de `{impresion.name}/`", "",
         f"> Generado el {date.today().isoformat()} por `scripts/verify/verify_batches.py`.", "",
         "## Resultado", ""]
    L.append(f"- **{len(rows)} lotes** (una carpeta por región, un PDF por `Tipo de Formulario`).")
    L.append(f"- **{sum(r['paginas'] for r in rows)} páginas**, una por estudiante.")
    L.append(f"- **{seen} de {total} folios** de la nómina impresos, cada uno exactamente una vez.")
    L.append(f"- **{sum(r['mb'] for r in rows):.1f} MB** en total.")
    L.append("")
    L.append("Cada página se verificó de extremo a extremo: se extrajo su *content stream* "
             "del PDF y se comparó byte a byte contra lo que las reglas producen para ese "
             "estudiante. " + ("**Sin diferencias.**" if not problems else
                               f"**{len(problems)} problema(s), ver abajo.**"))
    L += ["", "## Por región", "",
          "| Región | Lotes | Estudiantes | Páginas | MB |", "|---|---:|---:|---:|---:|"]
    for region in sorted(by_region):
        rs = by_region[region]
        L.append(f"| {region} | {len(rs)} | {sum(r['esperados'] for r in rs)} | "
                 f"{sum(r['paginas'] for r in rs)} | {sum(r['mb'] for r in rs):.1f} |")
    L.append(f"| **Total** | **{len(rows)}** | **{sum(r['esperados'] for r in rows)}** | "
             f"**{sum(r['paginas'] for r in rows)}** | **{sum(r['mb'] for r in rows):.1f}** |")

    L += ["", "## Por lote", "",
          "| Región | Tipo de Formulario | Instrumento | Estudiantes | Páginas | MB |",
          "|---|---|---|---:|---:|---:|"]
    for r in rows:
        L.append(f"| {r['region']} | `{r['tipo']}` | {r['instrumento']} | "
                 f"{r['esperados']} | {r['paginas']} | {r['mb']:.2f} |")

    L += ["", "## Casos cubiertos", "",
          "Cuántos estudiantes ejercitan cada rama de las reglas "
          "(ver `REGLAS_LLENADO.md`).", "",
          "| Caso | Estudiantes |", "|---|---:|"]
    for tag, n in sorted(tags.items()):
        L.append(f"| {tag} | {n} |")

    L += ["", "## Problemas", ""]
    L.append("Ninguno." if not problems else "\n".join(f"- {p}" for p in problems))
    out.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
