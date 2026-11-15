"""Build one "Nómina de estudiantes por curso" PDF per establecimiento + curso + letra.

Fills the header of `intrumentos/Formato nómina de estudiantes pre digitados por
curso.pdf` (Nombre Establecimiento, RBD, Región, Curso) and extends its single
table row into one numbered row per student of that curso, plus 15% extra blank
rows (rounded up) at the end. Rows shrink as needed so every nómina is one page.

    python3 2026-09/scripts/build/build_nominas_curso.py --sample          # one curso
    python3 2026-09/scripts/build/build_nominas_curso.py --rbd 2155 --curso 6B
    python3 2026-09/scripts/build/build_nominas_curso.py                   # all cursos

Output: `impresion/nominas/<Región>/<rbd>_<nom_est>_<curso><letra>.pdf`
"""

from __future__ import annotations

import argparse
import math
import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NOMINA = ROOT / "Nomina_estudiantes_C1yC2.xlsx"
TEMPLATE = ROOT / "intrumentos" / "Formato nómina de estudiantes pre digitados por curso.pdf"
OUT_DIR = ROOT / "impresion" / "nominas"

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"

BOTTOM = 760.0               # lowest table line (~0.44" bottom margin)
MIN_ROW_H = 10.0             # below this the list is considered unreadable
BLANK_RATIO = 0.15
LINE_W = 1.0


class Geometry:
    """Table positions read from the template's line drawings, so edits to the
    template's layout are picked up without touching this script.

    Expects two tables: a header (2 rows x label|value|label|value) and the
    student list (✓ | N° | nombre) with a column-title row and one sample row.
    """

    def __init__(self, page):
        vert, horiz = [], []
        for d in page.get_drawings():
            for item in d["items"]:
                if item[0] != "l":
                    continue
                a, b = item[1], item[2]
                if abs(a.x - b.x) < 0.1:
                    vert.append((round(a.x, 1), round(min(a.y, b.y), 1), round(max(a.y, b.y), 1)))
                elif abs(a.y - b.y) < 0.1:
                    horiz.append(round(a.y, 1))
        tops = sorted({v[1] for v in vert})
        header_top, list_top = tops[0], tops[-1]
        header_x = sorted({v[0] for v in vert if v[1] == header_top})
        list_x = sorted({v[0] for v in vert if v[1] == list_top})
        header_bottom = max(v[2] for v in vert if v[1] == header_top)
        header_y = sorted({y for y in horiz if y <= header_bottom})
        list_y = sorted({y for y in horiz if y > header_bottom})
        if len(header_x) != 5 or len(header_y) != 3 or len(list_x) != 4 or len(list_y) != 3:
            raise SystemExit(f"unexpected template layout: header x={header_x} y={header_y}, "
                             f"list x={list_x} y={list_y}")

        self.header_row1 = (header_y[0], header_y[1])
        self.header_row2 = (header_y[1], header_y[2])
        self.header_main_value = (header_x[1], header_x[2])   # Nombre Establecimiento / Región
        self.header_side_value = (header_x[3], header_x[4])   # RBD / Curso
        self.x_left, self.x_check, self.x_num, self.x_right = list_x
        self.table_top = list_y[1]            # bottom line of "Nombre completo estudiante"
        self.row_h = list_y[2] - list_y[1]    # template sample-row height


def load(nomina: Path) -> pd.DataFrame:
    df = pd.read_excel(nomina, sheet_name="Nómina pre digitacion").iloc[:, :17]
    df = df.rename(columns={"Región": "region", "Curso 2026": "curso"})
    df["rbd"] = df["rbd"].astype(int)
    df["curso"] = df["curso"].astype(int)
    # The same school can be typed with or without a trailing period ("… Básico."),
    # which would otherwise split its cursos across two sets of PDFs.
    df["nom_est"] = df["nom_est"].astype(str).str.strip().str.rstrip(".").str.strip()
    return df


def sort_key(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "", s)
    return re.sub(r"\s+", " ", s).strip()


def text_in(page, x, y_top, y_bot, text, size, font="arial"):
    """Vertically center one line of text between two horizontal lines."""
    baseline = (y_top + y_bot) / 2 + size * 0.35
    page.insert_text((x, baseline), text, fontsize=size, fontname=font, fontfile=FONT)


def text_centered(page, x0, x1, y_top, y_bot, text, size):
    w = fitz.Font(fontfile=FONT).text_length(text, fontsize=size)
    text_in(page, (x0 + x1) / 2 - w / 2, y_top, y_bot, text, size)


def fit_size(text: str, max_w: float, size: float, min_size: float = 7.0) -> float:
    font = fitz.Font(fontfile=FONT)
    while size > min_size and font.text_length(text, fontsize=size) > max_w:
        size -= 0.25
    return size


def draw_rows(page, geo: Geometry, names: list[str], row_h: float):
    """Remove the template's sample row, then draw `len(names)` rows ("" = blank row)."""
    top, xl, xr = geo.table_top, geo.x_left, geo.x_right
    page.add_redact_annot(fitz.Rect(xl + 1, top + 1, xr - 1, top + geo.row_h - 1))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    # Hide the sample row's lines, keeping the column-title row's bottom line intact.
    page.draw_rect(fitz.Rect(xl - 1, top + LINE_W / 2, xr + 1, top + geo.row_h + 1.5),
                   color=None, fill=(1, 1, 1))
    bottom = top + row_h * len(names)
    shape = page.new_shape()
    for x in (xl, geo.x_check, geo.x_num, xr):
        shape.draw_line((x, top - LINE_W / 2), (x, bottom + LINE_W / 2))
    for i in range(0, len(names) + 1):
        y = top + row_h * i
        shape.draw_line((xl - LINE_W / 2, y), (xr + LINE_W / 2, y))
    shape.finish(color=(0, 0, 0), width=LINE_W)
    shape.commit()

    name_w = xr - geo.x_num - 8
    size = min(9.5, row_h * 0.75)
    for i, name in enumerate(names):
        y0 = top + row_h * i
        y1 = y0 + row_h
        text_centered(page, geo.x_check, geo.x_num, y0, y1, str(i + 1), size)
        if name:
            text_in(page, geo.x_num + 4, y0, y1, name, fit_size(name, name_w, size))


def fill_header(page, geo: Geometry, nom_est: str, rbd: int, region: str, curso: str):
    cells = [
        (geo.header_row1, geo.header_main_value, nom_est),
        (geo.header_row1, geo.header_side_value, str(rbd)),
        (geo.header_row2, geo.header_main_value, region),
        (geo.header_row2, geo.header_side_value, curso),
    ]
    for (y0, y1), (x0, x1), value in cells:
        text_in(page, x0 + 5, y0, y1, value, fit_size(value, x1 - x0 - 10, 10.5))


def build_one(template: Path, out: Path, nom_est, rbd, region, curso, names):
    n_blank = math.ceil(len(names) * BLANK_RATIO)
    rows = names + [""] * n_blank
    doc = fitz.open()
    doc.insert_pdf(fitz.open(template), from_page=0, to_page=0)
    page = doc[0]
    geo = Geometry(page)

    row_h = min(geo.row_h, (BOTTOM - geo.table_top) / len(rows))
    if row_h < MIN_ROW_H:
        raise SystemExit(f"{out.name}: {len(rows)} rows do not fit on one page")

    fill_header(page, geo, nom_est, rbd, region, curso)
    draw_rows(page, geo, rows, row_h)

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.subset_fonts()
    doc.save(out, garbage=4, deflate=True)
    return n_blank, row_h


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nomina", type=Path, default=NOMINA)
    ap.add_argument("--template", type=Path, default=TEMPLATE)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--sample", action="store_true", help="build only the largest curso")
    ap.add_argument("--rbd", type=int)
    ap.add_argument("--curso", help="e.g. 6B")
    args = ap.parse_args()

    df = load(args.nomina)
    missing = df[df["nombre_completo"].isna()]
    df = df[df["nombre_completo"].notna()]

    groups = list(df.groupby(["region", "rbd", "nom_est", "curso", "letra"]))
    if args.rbd:
        groups = [g for g in groups if g[0][1] == args.rbd]
    if args.curso:
        groups = [g for g in groups if f"{g[0][3]}{g[0][4]}" == args.curso.upper()]
    if args.sample:
        groups = [max(groups, key=lambda g: len(g[1]))]
    if not groups:
        raise SystemExit("no curso matches")

    for (region, rbd, nom_est, curso, letra), g in groups:
        names = sorted((" ".join(str(n).split()) for n in g["nombre_completo"]), key=sort_key)
        label = f"{curso}{letra}"
        out = args.out_dir / region / safe_filename(f"{rbd}_{nom_est}_{label}.pdf")
        n_blank, row_h = build_one(args.template, out, nom_est, rbd, region, label, names)
        print(f"{out.relative_to(ROOT)}  ({len(names)} estudiantes + {n_blank} en blanco, "
              f"fila {row_h:.1f}pt, 1 pág.)")

    if len(missing):
        print(f"aviso: {len(missing)} filas sin nombre_completo omitidas "
              f"(folios {', '.join(missing['folio'].astype(str))})")


if __name__ == "__main__":
    main()
