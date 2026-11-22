#!/usr/bin/env python3
"""Rename extracted survey PDFs (and their JSONs) to the folio printed on the form.

Usage:
    python3 scripts/extraction/rename_by_folio.py [DIR] [--nomina FILE] [--dry-run] [--allow-unknown]

DIR defaults to 2026-09/pdfs. For every survey with an extracted JSON:
  * metadata.folio (printed, read by extract_all_surveys.py) -> <folio>.pdf / <folio>.json
  * no folio printed (folio == null) -> the next maximum folio of its
    colegio/curso/letra: max number found in the nómina (and already on disk)
    for that group + 1, e.g. group 46654A with max A31 -> 46654A32.
  * JSON without a "folio" key (extracted before that feature) -> skipped; re-extract it.

Safety (nothing is overwritten, ever):
  * a printed folio that is not in the nómina, or belongs to another
    colegio/curso/letra, is reported and NOT renamed (likely misread) unless --allow-unknown
  * two surveys claiming the same folio, or a target name already taken by a file that
    is not itself being renamed, are skipped and reported
  * swaps (A6<->A27) are done in two phases through temporary names
Idempotent: already-renamed files are skipped. Every rename is recorded in
<DIR>/.renames.json (original path -> new name + sha256) so sync_itservicios.py does not
re-download the original names. JSON metadata gets: original_filename, final_folio,
folio_source ("printed" | "assigned"). original_filename is the PDF's name before
the change (also kept in the ledger); the JSON always has the same new name as the PDF.
A survey already named after its folio is only tagged (original_filename = current name).
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DIR = REPO / "2026-09" / "pdfs"
DEFAULT_NOMINA = REPO / "2026-09" / "Nomina_estudiantes_C1yC2.xlsx"
SURVEY_ID_RE = re.compile(r"^(\d+)(\d)([A-Z])(\d+)$")      # rbd, curso, letra, n
LETTER_FOLIO_RE = re.compile(r"^(\d+[A-Z])(\d+)$")           # prefix, n
FOLIO_OK_RE = re.compile(r"^[A-Z0-9]{5,14}$")
LEDGER = ".renames.json"


def nfc(s):
    return unicodedata.normalize("NFC", s)


def fold(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def folio_str(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip().upper()


def load_nomina(path):
    """-> (folio -> group, group -> [folios], name-group index)."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["Nómina pre digitacion"]
    folio_group, group_folios, by_name = {}, defaultdict(list), defaultdict(set)
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] is None or r[2] is None:
            continue
        g = (int(r[2]), int(r[5]), str(r[7]).strip().upper())
        f = folio_str(r[0])
        folio_group[f] = g
        group_folios[g].append(f)
        by_name[(fold(r[3]), g[1], g[2])].add(g)
    return folio_group, group_folios, by_name


def survey_group(meta, by_name, valid_groups):
    m = SURVEY_ID_RE.match(str(meta.get("survey_id", "")))
    if m:
        g = (int(m[1]), int(m[2]), m[3])
        if g in valid_groups:
            return g
    gf = str(meta.get("grade_folder", ""))
    m = re.match(r"^(\d)([A-Z])$", gf)
    if m:
        cands = by_name.get((fold(meta.get("school_name", "")), int(m[1]), m[2]), set())
        if len(cands) == 1:
            return next(iter(cands))
    return None


def next_folio(group, group_folios, taken):
    """Next maximum folio of the group, not colliding with anything known."""
    nums, prefix = [], None
    for f in list(group_folios.get(group, [])) + [t for t in taken if t.startswith(f"{group[0]}{group[1]}{group[2]}")]:
        m = LETTER_FOLIO_RE.match(f)
        if m:
            prefix = m[1]
            nums.append(int(m[2]))
    if prefix:
        n = max(nums) + 1
        return f"{prefix}{n}"
    numeric = [int(f) for f in group_folios.get(group, []) if f.isdigit()]
    n = (max(numeric) if numeric else 0) + 1
    while str(n) in taken:
        n += 1
    return str(n)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", nargs="?", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--nomina", type=Path, default=DEFAULT_NOMINA)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-unknown", action="store_true",
                    help="also rename printed folios that are not in the nómina / other group")
    args = ap.parse_args()
    root = args.dir.resolve()

    folio_group, group_folios, by_name = load_nomina(args.nomina)
    valid_groups = set(group_folios)
    ledger_path = root / LEDGER
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    renamed_targets = {nfc(k): v for k, v in ledger.items()}

    # every survey-ish stem already on disk (taken names) + ledger targets
    on_disk = {nfc(str(p.relative_to(root))) for p in root.rglob("*") if p.is_file()}
    taken_by_dir = defaultdict(set)
    for rel in on_disk:
        pr = Path(rel)
        taken_by_dir[pr.parent].add(pr.stem.upper())
    all_taken = set().union(*taken_by_dir.values()) if taken_by_dir else set()

    plan, report = [], []   # plan: dict(src_json, src_pdf, folio, source, meta)
    for jp in sorted(root.rglob("*.json")):
        if jp.name == LEDGER:
            continue
        rel = nfc(str(jp.relative_to(root)))
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            meta = data["metadata"]
            data["responses"]
        except Exception:
            continue                                         # not a survey JSON
        pdf = jp.with_suffix(".pdf")
        if not pdf.exists():
            report.append((rel, "SKIP", "no PDF next to JSON"))
            continue
        if meta.get("final_folio"):
            continue                                         # already renamed
        if "folio" not in meta:
            report.append((rel, "SKIP", "no 'folio' key: extracted before folio support, re-extract"))
            continue
        folio = meta["folio"]
        group = survey_group(meta, by_name, valid_groups)
        if folio:
            folio = folio_str(folio)
            if not FOLIO_OK_RE.match(folio):
                report.append((rel, "REVIEW", f"printed folio '{folio}' is not a valid folio"))
                continue
            known = folio_group.get(folio)
            if not args.allow_unknown and (known is None or (group and known != group)):
                why = "not in the nómina" if known is None else f"belongs to another colegio/curso/letra {known}"
                report.append((rel, "REVIEW", f"printed folio {folio} {why}"))
                continue
            plan.append(dict(jp=jp, pdf=pdf, folio=folio, source="printed", meta=meta, data=data, group=group))
        else:
            if group is None:
                report.append((rel, "REVIEW", "no folio printed and colegio/curso/letra not found in the nómina"))
                continue
            plan.append(dict(jp=jp, pdf=pdf, folio=None, source="assigned", meta=meta, data=data, group=group))

    # assign next-max folios (sequentially, so several unprinted surveys get distinct ones)
    taken = set(all_taken) | set(folio_group)
    for item in plan:
        if item["source"] == "printed":
            continue
        item["folio"] = next_folio(item["group"], group_folios, taken)
        taken.add(item["folio"])

    # conflicts
    by_target = defaultdict(list)
    for it in plan:
        by_target[(it["pdf"].parent, it["folio"])].append(it)
    moving = {it["pdf"] for it in plan}
    final, noop = [], []
    for (d, folio), items in by_target.items():
        if len(items) > 1:
            for it in items:
                report.append((nfc(str(it["jp"].relative_to(root))), "CONFLICT",
                               f"{len(items)} surveys claim folio {folio}: " + ", ".join(i["pdf"].name for i in items)))
            continue
        it = items[0]
        tgt = d / f"{folio}.pdf"
        if it["pdf"] == tgt:
            noop.append(it)      # name already equals its folio: nothing to rename, but record it
            continue
        if tgt.exists() and tgt not in moving:
            report.append((nfc(str(it["jp"].relative_to(root))), "CONFLICT",
                           f"target {tgt.name} already exists (another survey; not overwritten)"))
            continue
        final.append(it)

    # execute (two-phase through temp names so swaps work)
    done = 0
    if not args.dry_run:
        for it in final:
            tmp_pdf = it["pdf"].with_name(it["pdf"].stem + ".__renaming__.pdf")
            tmp_json = it["jp"].with_name(it["jp"].stem + ".__renaming__.json")
            it["pdf"].rename(tmp_pdf)
            it["jp"].rename(tmp_json)
            it["tmp"] = (tmp_pdf, tmp_json)
    for it in final:
        d = it["pdf"].parent
        new_pdf, new_json = d / f"{it['folio']}.pdf", d / f"{it['folio']}.json"
        orig_rel = nfc(str(it["pdf"].relative_to(root)))
        msg = f"{it['pdf'].name} -> {new_pdf.name}  [{it['source']}]"
        report.append((orig_rel, "WOULD RENAME" if args.dry_run else "RENAMED", msg))
        if args.dry_run:
            continue
        tmp_pdf, tmp_json = it["tmp"]
        sha = sha256(tmp_pdf)
        meta = it["meta"]
        meta["original_filename"] = it["pdf"].name
        meta["final_folio"] = it["folio"]
        meta["folio_source"] = it["source"]
        tmp_json.write_text(json.dumps(it["data"], ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_pdf.rename(new_pdf)
        tmp_json.rename(new_json)
        ledger[orig_rel] = {"renamed_to": nfc(str(new_pdf.relative_to(root))), "sha256": sha,
                            "folio": it["folio"], "source": it["source"]}
        done += 1
    if done:
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    for it in noop:
        rel = nfc(str(it["jp"].relative_to(root)))
        report.append((rel, "WOULD TAG" if args.dry_run else "TAGGED",
                       f"{it['pdf'].name} already named after its folio [{it['source']}]"))
        if not args.dry_run:
            it["meta"].update(original_filename=it["pdf"].name, final_folio=it["folio"],
                              folio_source=it["source"])
            it["jp"].write_text(json.dumps(it["data"], ensure_ascii=False, indent=2), encoding="utf-8")

    for rel, kind, msg in report:
        print(f"{kind:12} {rel}: {msg}")
    counts = defaultdict(int)
    for _, k, _ in report:
        counts[k] += 1
    print("\n" + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "nothing to do")


if __name__ == "__main__":
    main()
