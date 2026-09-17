# Revisión de la nómina y generación de reportes por curso

**Fecha:** 2026-09-17
**Fuente:** `Nomina_estudiantes_C1yC2.xlsx`, hoja `Nómina pre digitacion` (20.334 filas)
**Salida revisada:** `impresion/reportes/` (705 PDF)

## Resumen

| | |
|---|---|
| Reportes generados | 705 (Biobío 371, RM 181, O´Higgins 121, NUBLE 32) |
| Cohorte 1 / Cohorte 2 | 253 / 452 |
| Suma de `A · Total encuestas pre digitadas` | 20.334 = total de filas de la nómina |
| Colisiones de nombre de archivo | ninguna |

## 1. Nombre de establecimiento duplicado (corregido)

El RBD 4530 aparecía con dos escrituras del mismo colegio:

| `nom_est` | filas |
|---|---|
| `Instituto San Sebastián Básico` | 287 |
| `Instituto San Sebastián Básico.` (punto final) | 30 |

Como el agrupamiento es por `(region, rbd, nom_est, curso, letra)`, cada curso se
partía en dos reportes: 16 PDF en vez de 8. Por ejemplo 8° B quedó como 36 + 3
estudiantes en archivos distintos, en vez de los 39 reales.

Las 30 filas con punto no se distinguen en nada de las otras (misma `cohorte` 1,
`Grupo` Tratamiento, `Modelo` Intensivo); todas tienen folio de 6 dígitos `582xxx`,
lo que sugiere una carga posterior donde se retipeó el nombre.

**Corrección:** `load()` en `scripts/build_nominas_curso.py` ahora normaliza
`nom_est` (quita espacios y puntos finales). La usan tanto
`build_nominas_curso.py` como `build_reportes_curso.py`. Los 16 PDF partidos se
borraron y el RBD 4530 se regeneró: 8 reportes con 40, 39, 39, 40, 39, 40, 41 y
39 estudiantes (317 en total).

### Otras variantes revisadas: sin hallazgos

- RBD con más de un `nom_est`: sólo 4530.
- `nom_est` bajo más de un RBD: ninguno.
- Nombres que difieren sólo en acentos, mayúsculas o puntuación: sólo 4530.
- RBD con más de una región: ninguno.
- Espacios dobles, iniciales, finales o no separables en `nom_est`: sólo 4530.
- Valores de `region` (Biobío, NUBLE, O´Higgins, RM), `letra` (A–E) y `curso` (4–8): todos válidos.
- Folios duplicados: ninguno (20.334 folios únicos).

## 2. Estudiantes repetidos dentro del mismo curso (pendiente)

17 estudiantes aparecen dos veces en el mismo curso, con el mismo
`nombre_completo` y distinto folio. El script cuenta filas, así que la columna
`A` queda inflada en 16 reportes (en `10405_Liceo Esmeralda_6A` son dos casos, +2):

| reporte | A actual | A sin repetidos | RUT |
|---|---|---|---|
| Biobío/4307_Colegio San José de Cabrero_5A | 47 | 46 | igual |
| Biobío/4452_Escuela El Saber_7A | 39 | 38 | igual |
| Biobío/4762_Liceo La Asuncion_8B | 45 | 44 | igual |
| Biobío/4782_Centro Educación Evangélico De Hualpén_6A | 39 | 38 | igual |
| Biobío/4807_Escuela Isla de Pascua_7A | 25 | 24 | distinto |
| Biobío/4973_Instituto Humanidades San Francisco De Asis_6A | 42 | 41 | distinto |
| O´Higgins/2455_Colegio Inmaculada Concepcion_6B | 42 | 41 | distinto (sólo DV) |
| O´Higgins/2455_Colegio Inmaculada Concepcion_7C | 39 | 38 | distinto (sólo DV) |
| O´Higgins/15515_Colegio Particular Subv. Children School_8A | 37 | 36 | igual |
| RM/10401_Escuela Básica Santa Teresa del Carmelo_5B | 42 | 41 | igual |
| RM/10401_Escuela Básica Santa Teresa del Carmelo_7B | 42 | 41 | igual |
| RM/10401_Escuela Básica Santa Teresa del Carmelo_8B | 38 | 37 | distinto |
| RM/10405_Liceo Esmeralda_6A | 35 | 33 | igual (2 casos) |
| RM/10412_Escuela San Francisco de Asís_5A | 31 | 30 | igual |
| RM/10839_Escuela Básica g-n° 734 Las Mercedes_5A | 39 | 38 | igual |
| RM/24675_Colegio San Manuel_6A | 38 | 37 | igual |

No son todos el mismo caso:

- **12 pares con RUT idéntico** — casi seguro el mismo estudiante digitado dos veces.
- **5 pares con RUT distinto** — en `2455 6B` (`24807270-1` vs `-9`) y `2455 7C`
  (`24373634-0` vs `-k`) sólo cambia el dígito verificador, lo que parece error de
  tipeo; en `4807 7A`, `4973 6A` y `10401 8B` los números son completamente
  distintos, lo que sugiere dos personas distintas con el mismo nombre.

Quedó sin resolver a la espera del criterio a aplicar.

## 3. RUT repetidos entre cursos o colegios distintos (sin efecto en los conteos)

95 RUT se repiten en 190 filas, en cursos o establecimientos distintos y con
nombres distintos (p. ej. `23774254` en los RBD 4730 y 4782). Parecen errores de
transcripción del RUT, no estudiantes duplicados, y no afectan ningún conteo de
los reportes.

Validación del RUT en la nómina: 17.717 válidos, 2.602 inválidos, 13 `#VALUE!`,
2 vacíos.

## Cambios en los scripts

- `scripts/build_nominas_curso.py` — `load()` normaliza `nom_est` (espacios y punto final).
- `scripts/build_reportes_curso.py` — se eliminó `--out-dir`: la salida siempre
  queda en `impresion/reportes/<Región>/<rbd>_<nom_est>_<curso><letra>.pdf`.
  `title_row()` busca el título "Reporte por curso" (minúscula), según la
  plantilla vigente `intrumentos/Reporte por curso Cohorte 1_Línea salida.pdf`.

## Cómo regenerar

```sh
cd 2026-09
python3 scripts/build_reportes_curso.py                 # todos los cursos
python3 scripts/build_reportes_curso.py --rbd 4530      # un establecimiento
python3 scripts/build_reportes_curso.py --rbd 4307 --curso 5A
```

Los 705 reportes se generaron con la plantilla de Cohorte 1 / Línea salida,
incluidos los 452 cursos de cohorte 2 (que sólo llevan el sello "COHORTE 2").
Si la cohorte 2 debe imprimirse en `Reporte por curso Cohorte 2_Línea
intermedia.pdf`, falta hacer que el script elija la plantilla según la cohorte.
