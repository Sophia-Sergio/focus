#!/usr/bin/env python3
"""Download the 'Planilla revisión encuestas' Google Sheet and add column N
("Encuestas extraídas"): number of extracted survey JSONs per colegio/curso/letra.

Usage:
    python3 2026-09/scripts/build/planilla_extracted_counts.py [--json-dir DIR] [--out FILE]
                                                            [--no-upload] [--folder-id ID]

After saving, the file is uploaded to your Google Drive (My Drive, or --folder-id)
as a NEW Google Sheet named "Planilla revisión encuestas - extraídas <date time>".
Every run creates a new file; nothing existing is overwritten. Upload uses the narrow
drive.file scope (only files this script creates) with its own token
(~/.credentials/drive_uploader.json); the first run opens a browser to authorize.

A survey file such as 46654A1.json encodes RBD=4665, curso=4, letra=A, survey #1
(RBD + curso digit + letra + number). Rows are matched on (RBD, Curso, Letra).
Only files named like surveys are counted (rosters/reports are ignored).

Auth: shared Drive OAuth helper (scripts/download/drive_auth.py, scripts/.env).
Prints rows with extracted surveys whose key is not in the sheet.
"""
import argparse
import json
from datetime import datetime
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "download"))

import openpyxl
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from drive_auth import get_credentials

FILE_ID = "1_KUUBbwbw32_9-DPpFgOmi3hdynHfaLe3YSsZNYmXXY"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SURVEY_RE = re.compile(r"^(\d+)(\d)([A-Z])(\d+)$")  # RBD, curso, letra, n
COL_N = 14
HEADER = "Encuestas extraídas"

DEFAULT_JSON_DIR = REPO / "2026-09" / "pdfs"
UPLOAD_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
UPLOAD_TOKEN = Path.home() / ".credentials" / "drive_uploader.json"
DRIVE_NAME = "Planilla revisión encuestas - extraídas"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"

DEFAULT_OUT = REPO / "2026-09" / "planilla_revision_encuestas.xlsx"


def count_extracted(json_dir: Path) -> Counter:
    counts = Counter()
    for f in json_dir.rglob("*.json"):
        # survey_id keeps the original id even after rename_by_folio.py renamed the file
        try:
            meta = json.loads(f.read_text(encoding="utf-8")).get("metadata") or {}
        except (ValueError, OSError, AttributeError):
            continue
        m = SURVEY_RE.match(str(meta.get("survey_id") or f.stem))
        if m and "student_name" in meta:
            rbd, curso, letra, _ = m.groups()
            counts[(int(rbd), int(curso), letra)] += 1
    return counts


def download_sheet(dest: Path) -> None:
    svc = build("drive", "v3", credentials=get_credentials())
    data = svc.files().export_media(fileId=FILE_ID, mimeType=XLSX_MIME).execute()
    dest.write_bytes(data)


def upload_sheet(path: Path, folder_id=None) -> str:
    """Upload the xlsx as a NEW Google Sheet (timestamped name). Returns its URL."""
    svc = build("drive", "v3", credentials=get_credentials(scopes=UPLOAD_SCOPES, token_path=UPLOAD_TOKEN))
    media = MediaFileUpload(str(path), mimetype=XLSX_MIME, resumable=False)
    meta = {"name": f"{DRIVE_NAME} {datetime.now():%Y-%m-%d %H%M}", "mimeType": SHEET_MIME}
    if folder_id:
        meta["parents"] = [folder_id]
    f = svc.files().create(body=meta, media_body=media, fields="id,webViewLink").execute()
    return f["webViewLink"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json-dir", type=Path, default=DEFAULT_JSON_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-upload", action="store_true", help="Skip the Google Drive upload")
    ap.add_argument("--folder-id", help="Drive folder to upload into (default: My Drive root)")
    args = ap.parse_args()

    counts = count_extracted(args.json_dir)
    print(f"Counted {sum(counts.values())} extracted surveys in {len(counts)} rbd/curso/letra groups")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    download_sheet(args.out)
    wb = openpyxl.load_workbook(args.out)
    ws = wb.active

    ws.cell(row=1, column=COL_N, value=HEADER)
    ws.cell(row=1, column=COL_N)._style = ws.cell(row=1, column=9)._style
    seen, total = set(), 0
    for r in range(2, ws.max_row + 1):
        rbd, curso, letra = ws.cell(r, 1).value, ws.cell(r, 7).value, ws.cell(r, 8).value
        if rbd is None or curso is None or not letra:
            continue
        key = (int(rbd), int(curso), str(letra).strip().upper())
        n = counts.get(key, 0)
        ws.cell(r, COL_N, n)
        seen.add(key)
        total += n
    wb.save(args.out)

    unmatched = {k: v for k, v in counts.items() if k not in seen}
    print(f"Saved {args.out}  (column N = '{HEADER}', total {total})")
    if unmatched:
        print(f"WARNING: {sum(unmatched.values())} extracted surveys not in the sheet:")
        for k, v in sorted(unmatched.items()):
            print(f"  RBD {k[0]} curso {k[1]} letra {k[2]}: {v}")

    if not args.no_upload:
        print(f"Drive: {upload_sheet(args.out, args.folder_id)}")


if __name__ == "__main__":
    main()
