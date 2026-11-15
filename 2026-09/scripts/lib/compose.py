"""Assemble one print batch: many students, one copy of the instrument's artwork.

A batch is every student of one region sitting one `Tipo de Formulario`, so it
can run to a thousand copies of the same 6–7 page instrument.  Appending that
many PDFs the obvious way duplicates ~400 KB of scanned artwork per student
(~6 GB for the full nómina), so instead the source pages are imported **once**
and every student's pages reference the same content streams and resources.
Only the small per-student cover overlay is written per copy.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

from form_geometry import Geometry, detect
from overlay import FONT_RES, Student, render


def _font_dict() -> DictionaryObject:
    d = DictionaryObject()
    d.update({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    })
    return d


def _stream(writer: PdfWriter, data: str):
    s = DecodedStreamObject()
    s.set_data(data.encode("latin-1"))
    return writer._add_object(s)


class BatchWriter:
    """Writes N personalised copies of one instrument into a single PDF."""

    def __init__(self, instrument: Path) -> None:
        self.reader = PdfReader(str(instrument))
        self.writer = PdfWriter()
        self.geometry: Geometry = detect(str(instrument))

        # Import every source page once; these become shared templates.
        templates = [self.writer.add_page(p) for p in self.reader.pages]
        self.page_height = float(templates[0].mediabox.height)

        self.shared = []
        for page in templates:
            resources = page.raw_get("/Resources")
            if not hasattr(resources, "idnum"):        # inline dict -> promote
                resources = self.writer._add_object(resources)
                page[NameObject("/Resources")] = resources
            self.shared.append({
                "resources": resources,
                "contents": page.raw_get("/Contents"),
                "mediabox": page.raw_get("/MediaBox"),
            })

        # The overlay's font lives in the cover page's shared resource dict.
        cover_res = self.shared[0]["resources"].get_object()
        fonts = cover_res.get("/Font")
        if fonts is None:
            fonts = DictionaryObject()
            cover_res[NameObject("/Font")] = fonts
        fonts.get_object()[NameObject(FONT_RES)] = self.writer._add_object(_font_dict())

        # The cover's content stream is not balanced (it leaves a flipped CTM in
        # place), so it is bracketed before the overlay is appended.
        self.q = _stream(self.writer, "q\n")
        self.Q = _stream(self.writer, "\nQ\n")

        # Templates were only a vehicle for importing objects; drop them from the
        # page tree, keeping the objects they point at alive through the students.
        self.kids = self.writer._pages.get_object()[NameObject("/Kids")]
        del self.kids[:]
        self._count = 0

    def _add_page(self, index: int, extra_contents=None) -> None:
        s = self.shared[index]
        base = s["contents"]
        page = DictionaryObject()
        page.update({
            NameObject("/Type"): NameObject("/Page"),
            NameObject("/Parent"): self.writer._pages,
            NameObject("/MediaBox"): s["mediabox"],
            NameObject("/Resources"): s["resources"],
            NameObject("/Contents"): (
                ArrayObject([self.q, base, self.Q, extra_contents])
                if extra_contents is not None else base),
        })
        self.kids.append(self.writer._add_object(page))
        self._count += 1

    def add_student(self, student: Student, grades: tuple[int, int]) -> list[str]:
        ops, warnings = render(self.geometry, student, grades, self.page_height)
        self._add_page(0, _stream(self.writer, ops))
        for i in range(1, len(self.shared)):
            self._add_page(i)
        return warnings

    def save(self, out_path: Path) -> None:
        self.writer._pages.get_object()[NameObject("/Count")] = NumberObject(self._count)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as fh:
            self.writer.write(fh)
