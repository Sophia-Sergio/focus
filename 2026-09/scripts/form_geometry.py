"""Detect the fillable boxes on page 1 of a `Diagramación *.pdf` cover sheet.

The cover pages carry no AcroForm fields and no extractable text: every label and
every box grid is a raster XObject.  So geometry is recovered by locating each
image on the page (via the content-stream CTM) and finding the white cell
interiors inside it.  Coordinates come back in PDF points, origin bottom-left.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from pypdf import PdfReader


@dataclass
class Box:
    """A single fillable cell, in PDF points (origin bottom-left)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0


@dataclass
class Grid:
    """A row of character cells plus the printed frame drawn around them."""

    cells: list[Box]
    frame: Box

    def __len__(self) -> int:
        return len(self.cells)


@dataclass
class Geometry:
    nombre: Grid | None = None             # 34-cell grid
    establecimiento: Grid | None = None    # 34-cell grid
    run: Grid | None = None                # 8 digits + verifier
    fecha: Grid | None = None              # dd mm yyyy
    sexo: list[Box] = field(default_factory=list)          # Hombre, Mujer, Prefiero no decir
    curso: list[Box] = field(default_factory=list)         # lower grade, upper grade
    letra: Box | None = None
    ink: list[tuple[float, float, float, float]] = field(default_factory=list)
    """Tight bounding boxes of every inked region on the page, for spacing checks."""


def _mul(a, b):
    return [
        a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5],
    ]


def _placements(page) -> list[tuple[str, list[float]]]:
    """Return (xobject name, CTM) for every image drawn on the page."""
    toks = page.get_contents().get_data().decode("latin-1").split()
    ctm, stack, nums, out = [1, 0, 0, 1, 0, 0], [], [], []
    for i, t in enumerate(toks):
        try:
            nums.append(float(t))
            continue
        except ValueError:
            pass
        if t == "q":
            stack.append(list(ctm))
        elif t == "Q":
            ctm = stack.pop() if stack else [1, 0, 0, 1, 0, 0]
        elif t == "cm":
            ctm = _mul(nums[-6:], ctm)
        elif t == "Do":
            out.append((toks[i - 1], list(ctm)))
        nums = []
    return out


def _components(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Connected components of a boolean mask, as (x0, y0, x1, y1) pixel boxes."""
    parent: dict[int, int] = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    prev_runs: list[tuple[int, int, int]] = []
    runs: list[tuple[int, int, int, int]] = []  # label, row, x0, x1
    label = 0
    for y in range(mask.shape[0]):
        row = mask[y]
        cur: list[tuple[int, int, int]] = []
        x = 0
        while x < len(row):
            if row[x]:
                x0 = x
                while x < len(row) and row[x]:
                    x += 1
                label += 1
                parent[label] = label
                lab = label
                for plab, px0, px1 in prev_runs:
                    if px0 <= x - 1 and x0 <= px1:
                        union(plab, lab)
                cur.append((lab, x0, x - 1))
                runs.append((lab, y, x0, x - 1))
            else:
                x += 1
        prev_runs = cur

    agg: dict[int, list[int]] = {}
    for lab, y, x0, x1 in runs:
        r = find(lab)
        b = agg.setdefault(r, [x0, y, x1, y])
        b[0] = min(b[0], x0)
        b[1] = min(b[1], y)
        b[2] = max(b[2], x1)
        b[3] = max(b[3], y)
    return [tuple(v) for v in agg.values()]


def _has_visible_frame(lum: np.ndarray, alpha: np.ndarray, cell) -> bool:
    """True if the cell is fenced above and below by ink that will actually print.

    Some cover pages carry white-on-white grids left over from the layout tool;
    they look like fillable cells but are invisible, so they must be discarded.
    """
    x0, y0, x1, y1 = cell
    structure = (alpha > 0.5) & (lum < 240)
    for band in (structure[max(y0 - 3, 0):y0, x0:x1 + 1],
                 structure[y1 + 1:y1 + 4, x0:x1 + 1]):
        if not band.size or band.mean() < 0.5:
            return False
    return True


def _to_gray_alpha(img: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    a = np.array(img.convert("RGBA"))
    alpha = a[..., 3] / 255.0
    lum = a[..., :3].mean(axis=2)
    return lum, alpha


def detect(pdf_path: str) -> Geometry:
    reader = PdfReader(pdf_path)
    page = reader.pages[0]
    # pypdf reports XObject names with a synthetic extension ("X6.png"); the
    # content stream refers to them as "/X6".
    images = {"/" + im.name.rsplit(".", 1)[0]: im.image for im in page.images}

    geo = Geometry()
    grids: list[Grid] = []           # horizontal runs of >= 5 cells
    squares: list[Box] = []          # checkbox outlines

    for name, m in _placements(page):
        img = images.get(name)
        if img is None:
            continue
        lum, alpha = _to_gray_alpha(img)
        ih, iw = lum.shape
        px_w, px_h = abs(m[0]) / iw, abs(m[3]) / ih
        x_left, y_top = m[4], max(m[5], m[5] + m[3])

        def to_page(x0, y0, x1, y1) -> Box:
            return Box(
                x_left + x0 * px_w,
                y_top - (y1 + 1) * px_h,
                x_left + (x1 + 1) * px_w,
                y_top - y0 * px_h,
            )

        inked = (alpha > 0.5) & (lum < 250)
        if inked.any():
            ys, xs = np.nonzero(inked)
            b = to_page(xs.min(), ys.min(), xs.max(), ys.max())
            geo.ink.append((b.x0, b.y0, b.x1, b.y1))

        # Grid cells are opaque white areas fenced in by grey separators.
        white = (alpha > 0.5) & (lum > 248)
        rows: dict[float, list[Box]] = {}
        for c in _components(white):
            if c[2] - c[0] < 6 or c[3] - c[1] < 6:
                continue
            if not _has_visible_frame(lum, alpha, c):
                continue  # white-on-white artwork, invisible on the printed page
            b = to_page(*c)
            if b.w < 5 or b.h < 5:
                continue
            key = next((k for k in rows if abs(k - b.cy) <= b.h * 0.5), None)
            rows.setdefault(b.cy if key is None else key, []).append(b)
        for row in rows.values():
            row.sort(key=lambda b: b.x0)
            if len(row) < 5:
                continue
            # The frame is the ink surrounding this band of cells: the black
            # outline plus the grey padding the cells sit in.
            top = int(round((y_top - row[0].y1) / px_h)) - 6
            bot = int(round((y_top - row[0].y0) / px_h)) + 6
            band = inked[max(top, 0):min(bot, ih), :]
            ys, xs = np.nonzero(band)
            frame = to_page(xs.min(), max(top, 0) + ys.min(),
                            xs.max(), max(top, 0) + ys.max())
            grids.append(Grid(row, frame))

        # Checkboxes are drawn as outlines over a transparent interior, so they
        # show up as roughly square rings of dark pixels rather than white cells.
        dark = (alpha > 0.5) & (lum < 160)
        for x0, y0, x1, y1 in _components(dark):
            w, h = x1 - x0 + 1, y1 - y0 + 1
            if not (10 <= w <= 40 and 10 <= h <= 40 and 0.8 <= w / h <= 1.25):
                continue
            inner = dark[y0 + 3:y1 - 2, x0 + 3:x1 - 2]
            if inner.size and inner.mean() > 0.2:
                continue
            edges = (dark[y0, x0:x1 + 1], dark[y1, x0:x1 + 1],
                     dark[y0:y1 + 1, x0], dark[y0:y1 + 1, x1])
            if min(e.mean() for e in edges) < 0.8:
                continue  # a glyph that merely happens to be square-ish
            squares.append(to_page(x0, y0, x1, y1))

    grids.sort(key=lambda g: -g.cells[0].cy)
    for grid in grids:
        if len(grid) >= 20:
            if geo.nombre is None:
                geo.nombre = grid
            elif geo.establecimiento is None:
                geo.establecimiento = grid
        elif len(grid) == 9:
            geo.run = grid
        elif len(grid) == 8:
            geo.fecha = grid

    singles = sorted(squares, key=lambda b: -b.cy)
    # Checkbox stacks: consecutive same-size squares sharing a left edge.
    stacks: list[list[Box]] = []
    for b in singles:
        for s in stacks:
            if abs(s[-1].x0 - b.x0) < 2 and abs(s[-1].w - b.w) < 2 and s[-1].y0 - b.y1 < b.h:
                s.append(b)
                break
        else:
            stacks.append([b])
    for s in stacks:
        if len(s) == 3:
            geo.sexo = s
        elif len(s) == 2:
            geo.curso = s
        elif len(s) == 1 and geo.letra is None:
            geo.letra = s[0]
    return geo


if __name__ == "__main__":
    import sys

    g = detect(sys.argv[1])
    for f in ("nombre", "establecimiento", "run", "fecha"):
        v = getattr(g, f)
        print(f"{f:16} n={len(v) if v else 0:2}  " + (
            f"y={v.cells[0].cy:6.1f} x={v.cells[0].x0:6.1f}..{v.cells[-1].x1:6.1f} "
            f"cell={v.cells[0].w:.1f}x{v.cells[0].h:.1f} "
            f"frame=({v.frame.x0:.1f},{v.frame.y0:.1f})-({v.frame.x1:.1f},{v.frame.y1:.1f})" if v else ""))
    for f in ("sexo", "curso"):
        v = getattr(g, f)
        print(f"{f:16} n={len(v):2}  " + (f"y={v[0].cy:6.1f} x={v[0].x0:6.1f}..{v[-1].x1:6.1f} "
              f"cell={v[0].w:.1f}x{v[0].h:.1f}" if v else ""))
    print(f"{'letra':16} n={1 if g.letra else 0:2}  " +
          (f"y={g.letra.cy:6.1f} x={g.letra.x0:6.1f} cell={g.letra.w:.1f}x{g.letra.h:.1f}" if g.letra else ""))
