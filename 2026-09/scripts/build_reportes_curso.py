"""Build one "Reporte por Curso" PDF per establecimiento + curso + letra.

Pre-fills `intrumentos/Reporte por curso Cohorte 1_Línea salida.pdf`:
Nombre establecimiento, RBD, Región, Grupo (Control/Tratamiento, from
`Tipo de Formulario`), and in the table row Nivel (e.g. 5A) and
A · Total encuestas pre digitadas (number of students in the nómina for that curso).

    python3 2026-09/scripts/build_reportes_curso.py --rbd 4576 --curso 7C
    python3 2026-09/scripts/build_reportes_curso.py                   # all cursos

Output: `impresion/reportes/<Región>/<rbd>_<nom_est>_<curso><letra>.pdf`
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz  # PyMuPDF

from build_nominas_curso import NOMINA, ROOT, fit_size, load, safe_filename, text_centered, text_in

TEMPLATE = ROOT / "intrumentos" / "Reporte por curso Cohorte 1_Línea salida.pdf"
OUT_DIR = ROOT / "impresion" / "reportes"


class Geometry:
    """Cell boxes located from the template's labels and ruling lines, so layout
    edits to the template are picked up without touching this script."""

    def __init__(self, page):
        self.vert, self.horiz = [], []
        for d in page.get_drawings():
            for item in d["items"]:
                if item[0] != "l":
                    continue
                a, b = item[1], item[2]
                if abs(a.x - b.x) < 0.1:
                    self.vert.append((a.x, min(a.y, b.y), max(a.y, b.y)))
                elif abs(a.y - b.y) < 0.1:
                    self.horiz.append((a.y, min(a.x, b.x), max(a.x, b.x)))
        self.spans = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
                      for s in l["spans"] if s["text"].strip()]

    def _label(self, text: str) -> fitz.Rect:
        hits = [fitz.Rect(s["bbox"]) for s in self.spans if s["text"].strip() == text]
        if not hits:
            raise SystemExit(f"template label not found: {text!r}")
        return hits[0]

    def _lines_around(self, x: float, y: float) -> tuple[float, float, float, float]:
        """Innermost ruled cell (x0, y0, x1, y1) containing point (x, y)."""
        ys = [h[0] for h in self.horiz if h[1] <= x <= h[2]]
        xs = [v[0] for v in self.vert if v[1] <= y <= v[2]]
        above, below = [v for v in ys if v < y], [v for v in ys if v > y]
        left, right = [v for v in xs if v < x], [v for v in xs if v > x]
        if not (above and below and left and right):
            raise SystemExit(f"no ruled cell around ({x:.0f}, {y:.0f}) in template")
        return max(left), max(above), min(right), min(below)

    def header_value(self, label: str) -> tuple[float, float, float, float]:
        """The cell to the right of a header label, on the same row."""
        r = self._label(label)
        _, y0, label_x1, y1 = self._lines_around(r.x0 + 1, (r.y0 + r.y1) / 2)
        x0, _, x1, _ = self._lines_around(label_x1 + 2, (y0 + y1) / 2)
        return x0, y0, x1, y1

    def data_cell(self, column_label: str) -> tuple[float, float, float, float]:
        """The bottom (data) row cell of the column under a title label."""
        r = self._label(column_label)
        cx = (r.x0 + r.x1) / 2
        cell = self._lines_around(cx, (r.y0 + r.y1) / 2)
        while any(h[0] > cell[3] + 1 and h[1] <= cx <= h[2] for h in self.horiz):
            cell = self._lines_around(cx, cell[3] + 2)
        return cell


def build_one(template: Path, out: Path, nom_est, rbd, region, grupo, nivel, total):
    doc = fitz.open()
    doc.insert_pdf(fitz.open(template), from_page=0, to_page=0)
    page = doc[0]
    geo = Geometry(page)

    for label, value in [("Nombre establecimiento", nom_est), ("RBD", str(rbd)),
                         ("Región", region), ("Grupo", grupo)]:
        x0, y0, x1, y1 = geo.header_value(label)
        text_in(page, x0 + 5, y0, y1, value, fit_size(value, x1 - x0 - 10, 10.5))

    for column, value in [("Nivel", nivel), ("A", str(total))]:
        x0, y0, x1, y1 = geo.data_cell(column)
        size = fit_size(value, x1 - x0 - 4, 10.5)
        text_centered(page, x0, x1, y0, y1, value, size)

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.subset_fonts()
    doc.save(out, garbage=4, deflate=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nomina", type=Path, default=NOMINA)
    ap.add_argument("--template", type=Path, default=TEMPLATE)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--rbd", type=int)
    ap.add_argument("--nom-est", help="exact nom_est (disambiguates RBDs shared by several schools)")
    ap.add_argument("--curso", help="e.g. 6B")
    args = ap.parse_args()

    df = load(args.nomina)
    df["grupo"] = df["Tipo de Formulario"].astype(str).str.split("_").str[2]
    if not df["grupo"].isin(["Control", "Tratamiento"]).all():
        raise SystemExit("Tipo de Formulario has values without Control/Tratamiento")

    groups = list(df.groupby(["region", "rbd", "nom_est", "curso", "letra"]))
    if args.rbd:
        groups = [g for g in groups if g[0][1] == args.rbd]
    if args.nom_est:
        groups = [g for g in groups if g[0][2] == args.nom_est]
    if args.curso:
        groups = [g for g in groups if f"{g[0][3]}{g[0][4]}" == args.curso.upper()]
    if not groups:
        raise SystemExit("no curso matches")

    for (region, rbd, nom_est, curso, letra), g in groups:
        grupos = g["grupo"].unique()
        if len(grupos) != 1:
            raise SystemExit(f"{nom_est} {curso}{letra}: mixed grupos {list(grupos)}")
        nivel = f"{curso}{letra}"
        out = args.out_dir / region / safe_filename(f"{rbd}_{nom_est}_{nivel}.pdf")
        build_one(args.template, out, nom_est, rbd, region, grupos[0], nivel, len(g))
        print(f"{out.relative_to(ROOT)}  (grupo {grupos[0]}, {len(g)} encuestas pre digitadas)")


if __name__ == "__main__":
    main()
