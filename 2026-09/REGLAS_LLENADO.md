# Pre-filling rules — 2026-09 cover pages

How a student's row from `Nomina_estudiantes_C1yC2.xlsx` is printed onto page 1 of
`intrumentos/first_pages/Diagramación *.pdf`.

Implemented by `scripts/fill_nomina_pdf.py` (geometry detection in `scripts/form_geometry.py`).

```bash
python3 2026-09/scripts/fill_nomina_pdf.py \
    --pdf "2026-09/intrumentos/first_pages/Diagramación 4-5B_Control.pdf" \
    --folio 46175A8 \
    --out "2026-09/ejemplos/Diagramación 4-5B_Control__46175A8.pdf"
```

## Which form belongs to which student

The three header lines of the PDF *are* the `Tipo de Formulario` column:

```
C{cohorte}_{Curso agrupado encuesta}_{Grupo}_{Tipo 2026}
```

| PDF | `Tipo de Formulario` |
|---|---|
| `Diagramación {lo}-{hi}{A\|B}_{Control\|Tratamiento}.pdf` | `C{n}_{lo}y{hi}_{Grupo}_{A\|B}` |

`cohorte` is not in the filename because the grade pair determines it: `5y6` and
`7y8` → C1, `4y5` and `6y7` → C2. The script resolves it from the nómina rather
than hard-coding it, and refuses to print a folio onto the wrong form.

## Field rules

| Field on the form | Source column | Rule |
|---|---|---|
| **Folio** | `folio` | Printed in the **upper right corner**, right-aligned to the grids' right edge. Not part of the original layout — it is added by the script. |
| **Fecha** | — | **Left blank.** The student writes day and month; `2026` is already preprinted. |
| **Nombre completo del estudiante** | `nombre_completo` | One character per cell, see *Text rendering* and *Overflow*. |
| **RUN del estudiante** | `rut_num`, `rut_dv` | **Printed only when `validacion_rut == "RUT VÁLIDO"`.** Otherwise every cell is left empty and the run is logged as a warning. Digits are right-aligned in the 8 cells; `rut_dv` goes in the cell after the dash. Longer ids get extra cells — see *Ids longer than 8 digits*. |
| **Sexo del estudiante** | `sexo` | Marked with an **`X`**, and **only for `Hombre` or `Mujer`**. `Prefiero no decir`, blank and `0` are left unmarked. |
| **Nombre del establecimiento** | `nom_est` | One character per cell, see *Text rendering* and *Overflow*. |
| **Curso** | `Curso 2026` | Marked with an **`X`** in the box matching the grade. The two boxes are the grade pair in the filename, in order (`4-5` → top box `4°`, bottom box `5°`). |
| **Letra del curso** | `letra` | Single uppercase letter in the box. Two forms ship without the box; it is redrawn — see *Missing "Letra del curso" box*. |

`rbd`, `Región`, `Modelo`, `Grupo` and `cohorte` have no field on the form —
`Grupo` and `cohorte` are already encoded in which form is used.

## Text rendering

- **UPPERCASE, accents preserved**: `Rodríguez` → `RODRÍGUEZ`, `Zúñiga` → `ZÚÑIGA`.
- One character per cell, spaces included (a space leaves its cell empty).
- Runs of whitespace are collapsed to a single space.

## Overflow — never cut a word

Both text grids are 34 cells wide. `nombre_completo` runs to 59 characters and
`nom_est` to 56, so roughly 9% of names and 29% of school names do not fit.

- The text is **word-wrapped** into 34-character lines.
- For each extra line, a **continuation row is drawn in the same style** as the
  printed one (black outline, grey separators, white cells, identical cell
  positions and height).
- Continuation rows go **below** the printed grid when there is vertical room —
  this is what happens for `nombre_completo`, which has ~90 pt of free space.
- When there is not enough room below, they go **above** instead, so that reading
  order stays top-to-bottom and the *printed* grid holds the **last** line. This
  is what happens for `nom_est`: only ~14 pt separate its grid from the "Curso"
  label, while ~35 pt sit free under its own label.
- A single word longer than 34 characters is the only thing ever split.
- If neither direction has room, the text is truncated at 34 characters and the
  run reports a warning.

## Ids longer than 8 digits

The RUN grid has 8 digit cells, but 16 validated ids are longer (foreign
students, `100…`). **Extra cells are added at the start of the grid**, drawn in
the printed style — grey padding, white cell, black outline — with the frame
grown leftwards and the old left border painted over so it does not read as a
divider. The result is indistinguishable from the printed grid.

- 14 ids need **one** extra cell (9 digits). The grid's left edge moves from
  29.2 pt to 14.2 pt, i.e. a 5 mm page margin — printable, but worth a look on
  the real printer.
- 2 ids are 10 and 11 digits (`1006941843`, `10097688340`, both of which look
  like data-entry damage). Two or three extra cells would run off the left edge
  of the page, so the RUN is left blank and the run reports a warning. The limit
  is `MIN_LEFT_MARGIN = 12 pt`.

## Missing "Letra del curso" box

**`Diagramación 7-8A_Control.pdf` and `Diagramación 7-8A_Tratamiento.pdf` ship
without the box** — the label and the hint text are there, the box is not. On the
other 14 forms the box sits at exactly the same offset from the top "Curso"
checkbox (dx +57.0 pt, top edge −4.54 pt, 22.5 × 25.5 pt), so **the box is drawn
at that offset** and then filled. The run reports that it was drawn.

## Other quirks

- Cover pages carry a leftover white-on-white grid under the establecimiento
  field (invisible when printed). `form_geometry.py` discards it by requiring a
  cell to be fenced by ink that will actually print.

## Print batches

`scripts/build_batches.py` writes one folder per región and, inside it, one PDF
per `Tipo de Formulario`. **A batch holds only the cover page of each student —
one page per student, never the rest of the instrument.** Pages 2+ are identical
for everybody and get printed separately. Students are ordered by school (`rbd`),
then curso, letra and name — the order they get handed out in.

```
2026-09/impresion/
  Biobío/  NUBLE/  O´Higgins/  RM/
    C1_5y6_Control_A.pdf ...
  manifest.csv          # region, tipo, students, pages, size, warning counts
```

```bash
python3 2026-09/scripts/build_batches.py                  # all 56 batches
python3 2026-09/scripts/build_batches.py --region Biobío
python3 2026-09/scripts/build_batches.py --full-survey    # opt in to pages 2+
```

Covers come from `intrumentos/first_pages/`; `--full-survey` switches the source
to the complete instruments in `intrumentos/` and appends pages 2+ after each
cover. That flag is the exception, not the default.

NUBLE has 8 batches rather than 16: it has no cohort-1 students.

The cover's artwork is imported **once per batch** and every student's page
references the same content streams and resources, so only the small overlay is
written per copy — 20,334 covers come to 94 MB instead of the ~1.2 GB a plain
merge would produce, in about 10 s.

## Worked examples

In `ejemplos/`, one per rule worth eyeballing:

| File | Shows |
|---|---|
| `Diagramación 4-5B_Control__46175A8.pdf` | the normal case, plus both wrap directions (name wraps down, school wraps up) |
| `edge_nombre-2-filas__4-5B_Control.pdf` | a name that wraps to two rows while the school still fits on one |
| `edge_nombre-3-filas__4-5B_Tratamiento.pdf` | the longest name in the nómina, three rows (the only one) |
| `edge_run-9-digitos__4-5B_Tratamiento.pdf` | a 9-digit RUN with one cell added at the start of the grid |
| `edge_run-11-digitos__6-7A_Control.pdf` | an 11-digit RUN that cannot fit: RUN left blank |
| `edge_sin-caja-letra__7-8A_Control.pdf` | the "Letra del curso" box drawn on a form that lacks it |
| `edge_rut-invalido-y-prefiero-no-decir__4-5B_Control.pdf` | invalid RUN and `Prefiero no decir`: both left blank |

## Verification

`scripts/verify_batches.py` reconciles `impresion/` against the nómina and writes
`VERIFICACION.md`. It pulls each page's overlay content stream back out of the PDF
and compares it byte-for-byte with what the rules produce for the student that
page claims to be, so a lost student, a duplicate, a page on the wrong form or any
drift between these rules and what was printed all show up.

```bash
python3 2026-09/scripts/verify_batches.py
```

## How the geometry is found

The cover pages have no AcroForm fields and no extractable text: every label and
every grid is a raster image. So `form_geometry.py` walks the content stream to
get each image's placement matrix, then finds the cells inside each image:

- **Grid cells** are opaque white areas fenced in by grey separators.
- **Checkboxes** are square rings of dark pixels over a transparent interior.

This runs per file, so the small vertical differences between the 16 variants
(the grids sit 0–30 pt apart depending on the form) need no per-file constants.
