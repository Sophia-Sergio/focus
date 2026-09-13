"""Draw a student's nómina data as a raw PDF content stream.

The rules are documented in `2026-09/REGLAS_LLENADO.md`.

Output is a plain operator string rather than a rendered PDF page: batches print
20k+ students off the same 16 instruments, so every cover page has to share one
copy of the form's artwork and carry only this small per-student overlay.
"""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.pdfbase.pdfmetrics import stringWidth

from form_geometry import Box, Geometry, Grid

FONT_NAME = "Helvetica-Bold"
FONT_RES = "/FocusFill"          # resource name added to the cover page's /Font
SEPARATOR_GREY = 209 / 255
ROW_GAP = 6.0                    # gap between a grid and a continuation row

SEXO_ORDER = ("Hombre", "Mujer", "Prefiero no decir")
MARCAR_SEXO = ("Hombre", "Mujer")   # "Prefiero no decir" is never pre-marked
RUT_VALIDO = "RUT VÁLIDO"

# `Diagramación 7-8A_Control.pdf` and `7-8A_Tratamiento.pdf` ship without the
# "Letra del curso" box (label and hint are there, the box is not).  On the other
# 14 forms the box sits at exactly this offset from the top "Curso" checkbox, so
# the missing one is redrawn rather than left out.
LETRA_DX = 57.0
LETRA_DY_TOP = -4.54
LETRA_W, LETRA_H = 22.5, 25.5

MIN_LEFT_MARGIN = 12.0   # pt; how far left the RUN grid may be grown


def _escape(text: str) -> str:
    out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return out.encode("cp1252", "replace").decode("cp1252")


class Ops:
    """Accumulates PDF content-stream operators."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    def fill_rect(self, x: float, y: float, w: float, h: float, grey: float) -> None:
        self.parts.append(f"{grey:.4f} {grey:.4f} {grey:.4f} rg "
                          f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def stroke_rect(self, x: float, y: float, w: float, h: float, width: float = 0.75) -> None:
        self.parts.append(f"0 0 0 RG {width} w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")

    def text_at(self, x: float, baseline: float, size: float, text: str) -> None:
        self.parts.append(f"BT 0 0 0 rg {FONT_RES} {size:.2f} Tf "
                          f"{x:.2f} {baseline:.2f} Td ({_escape(text)}) Tj ET")

    def centred_text(self, cx: float, baseline: float, size: float, text: str) -> None:
        self.text_at(cx - stringWidth(text, FONT_NAME, size) / 2, baseline, size, text)

    def right_text(self, right: float, baseline: float, size: float, text: str) -> None:
        self.text_at(right - stringWidth(text, FONT_NAME, size), baseline, size, text)

    def __str__(self) -> str:
        return "\n".join(self.parts) + "\n"


@dataclass
class Student:
    folio: str
    nombre_completo: str
    nom_est: str
    sexo: str
    curso: int
    letra: str
    rut_num: str
    rut_dv: str
    rut_valido: bool
    tipo_formulario: str
    region: str


def to_cells(text: str) -> str:
    """Uppercase, accents preserved, collapsed whitespace."""
    return " ".join(text.split()).upper()


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap. Words longer than a full row are the only ones split."""
    lines: list[str] = []
    for word in to_cells(text).split(" "):
        while len(word) > width:
            lines.append(word[:width])
            word = word[width:]
        if lines and len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] += " " + word
        elif word:
            lines.append(word)
    return lines or [""]


def free_space(geo: Geometry, frame: Box, direction: int) -> float:
    """Vertical gap between `frame` and the nearest ink above (+1) or below (-1)."""
    limit = 792.0 if direction > 0 else 0.0
    for x0, y0, x1, y1 in geo.ink:
        if x1 <= frame.x0 + 1 or x0 >= frame.x1 - 1:
            continue
        if direction > 0 and y0 >= frame.y1 - 1:
            limit = min(limit, y0)
        elif direction < 0 and y1 <= frame.y0 + 1:
            limit = max(limit, y1)
    return (limit - frame.y1) if direction > 0 else (frame.y0 - limit)


def _put_chars(ops: Ops, cells: list[Box], text: str, dy: float = 0.0) -> None:
    for cell, ch in zip(cells, text):
        if ch == " ":
            continue
        size = min(cell.h * 0.72, cell.w * 1.25)
        ops.centred_text(cell.cx, cell.cy + dy - size * 0.34, size, ch)


def _put_mark(ops: Ops, box: Box) -> None:
    size = box.h * 0.82
    ops.centred_text(box.cx, box.cy - size * 0.34, size, "X")


def _draw_row(ops: Ops, grid: Grid, dy: float) -> None:
    """Draw a copy of `grid`'s frame and cells, offset vertically by `dy`."""
    f = grid.frame
    ops.fill_rect(f.x0, f.y0 + dy, f.x1 - f.x0, f.y1 - f.y0, SEPARATOR_GREY)
    for cell in grid.cells:
        ops.fill_rect(cell.x0, cell.y0 + dy, cell.w, cell.h, 1.0)
    ops.stroke_rect(f.x0, f.y0 + dy, f.x1 - f.x0, f.y1 - f.y0)


def _fill_grid(ops: Ops, geo: Geometry, grid: Grid, text: str,
               warnings: list[str], label: str) -> None:
    """Write `text` into `grid`, adding continuation rows when it does not fit."""
    width = len(grid.cells)
    lines = wrap(text, width)
    pitch = grid.frame.y1 - grid.frame.y0 + ROW_GAP
    extra = len(lines) - 1
    if extra == 0:
        _put_chars(ops, grid.cells, lines[0])
        return

    needed = extra * pitch
    if free_space(geo, grid.frame, -1) >= needed:
        offsets = [0.0] + [-pitch * (i + 1) for i in range(extra)]
    elif free_space(geo, grid.frame, +1) >= needed:
        # No room underneath: stack the continuation rows above instead, so the
        # printed grid holds the *last* line and reading order stays top-down.
        offsets = [pitch * (extra - i) for i in range(extra)] + [0.0]
    else:
        warnings.append(f"{label}: needs {len(lines)} rows but the page has no room; "
                        f"truncated to {width} chars")
        _put_chars(ops, grid.cells, to_cells(text)[:width])
        return

    for line, dy in zip(lines, offsets):
        if dy:
            _draw_row(ops, grid, dy)
        _put_chars(ops, grid.cells, line, dy)


def letra_box(geo: Geometry) -> tuple[Box | None, bool]:
    """The "Letra del curso" box, reconstructed when the form is missing it."""
    if geo.letra:
        return geo.letra, False
    if len(geo.curso) != 2:
        return None, False
    ref = geo.curso[0]
    y1 = ref.y1 + LETRA_DY_TOP
    return Box(ref.x0 + LETRA_DX, y1 - LETRA_H, ref.x0 + LETRA_DX + LETRA_W, y1), True


def _extend_run_grid(ops: Ops, grid: Grid, extra: int) -> list[Box]:
    """Prepend `extra` cells to the left of the RUN grid, in the printed style."""
    cells = grid.cells
    pitch = cells[1].x0 - cells[0].x0
    new = [Box(cells[0].x0 - pitch * (i + 1), cells[0].y0,
               cells[0].x1 - pitch * (i + 1), cells[0].y1)
           for i in range(extra)][::-1]
    f = grid.frame
    x0 = f.x0 - pitch * extra

    # Grey padding, overlapping the old left border so it stops reading as a divider.
    ops.fill_rect(x0, f.y0, (f.x0 + 1.5) - x0, f.y1 - f.y0, SEPARATOR_GREY)
    for cell in new:
        ops.fill_rect(cell.x0, cell.y0, cell.w, cell.h, 1.0)
    ops.stroke_rect(x0, f.y0, f.x1 - x0, f.y1 - f.y0)
    return new + cells


def render(geo: Geometry, student: Student, grades: tuple[int, int],
           page_height: float = 792.0) -> tuple[str, list[str]]:
    """Return the overlay content stream for `student`, plus any warnings."""
    ops = Ops()
    warnings: list[str] = []

    # Folio, upper right corner, aligned to the right edge of the form's grids.
    right = geo.nombre.frame.x1 if geo.nombre else 562.0
    ops.right_text(right, page_height - 42, 12, student.folio)

    if geo.nombre:
        _fill_grid(ops, geo, geo.nombre, student.nombre_completo, warnings, "nombre_completo")
    if geo.establecimiento:
        _fill_grid(ops, geo, geo.establecimiento, student.nom_est, warnings, "nom_est")

    # RUN: only pre-printed when the nómina validated it.
    if geo.run:
        digit_cells = len(geo.run.cells) - 1
        cells = geo.run.cells
        pitch = cells[1].x0 - cells[0].x0
        if not (student.rut_valido and student.rut_num):
            warnings.append(f"RUN not printed (validacion_rut != '{RUT_VALIDO}')")
        else:
            extra = len(student.rut_num) - digit_cells
            if extra > 0 and geo.run.frame.x0 - pitch * extra < MIN_LEFT_MARGIN:
                warnings.append(
                    f"RUN not printed ({student.rut_num} has {len(student.rut_num)} digits; "
                    f"{extra} extra cells would run off the left edge of the page)")
            else:
                if extra > 0:
                    cells = _extend_run_grid(ops, geo.run, extra)
                    digit_cells += extra
                    warnings.append(f"RUN has {len(student.rut_num)} digits; "
                                    f"{extra} cell(s) added at the start of the grid")
                _put_chars(ops, cells[:digit_cells], student.rut_num.rjust(digit_cells))
                _put_chars(ops, cells[digit_cells:], student.rut_dv.upper()[:1])

    # Sexo: marked only for Hombre / Mujer.
    if geo.sexo and student.sexo in MARCAR_SEXO:
        _put_mark(ops, geo.sexo[SEXO_ORDER.index(student.sexo)])
    elif student.sexo not in MARCAR_SEXO:
        warnings.append(f"sexo not marked (value: {student.sexo!r})")

    if geo.curso:
        if student.curso in grades:
            _put_mark(ops, geo.curso[grades.index(student.curso)])
        else:
            warnings.append(f"curso {student.curso} is not on this form ({grades})")

    box, drawn = letra_box(geo)
    if box is None:
        warnings.append("no 'Letra del curso' box and no reference to rebuild it from")
    elif student.letra:
        if drawn:
            ops.fill_rect(box.x0, box.y0, box.w, box.h, 1.0)
            ops.stroke_rect(box.x0, box.y0, box.w, box.h)
            warnings.append("this form ships without a 'Letra del curso' box; it was drawn")
        _put_chars(ops, [box], student.letra.upper()[:1])

    # Fecha is left blank on purpose: the student writes it on the day.
    return str(ops), warnings
