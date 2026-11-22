#!/usr/bin/env python3
"""Idempotent upload of the itservicios PDFs to Google Drive, preserving the
local folder tree (REGION/Colegio/Curso/file.pdf).

Usage: upload_pdfs_to_drive.py [SRC_DIR] [--folder-id ID] [--workers N] [--only SUBDIR] [--dry-run]
  SRC_DIR   default: <repo>/2026-09/pdfs
  --folder-id  destination Drive folder (default: the project folder below)

Safe to run repeatedly (also used as the last step of sync_itservicios.sh):
  - files already in Drive with the same name and MD5 are skipped
  - a file whose content changed locally is updated in place (no duplicates)
  - a file renamed locally by rename_by_folio.py (see <src>/.renames.json) is renamed in Drive
    (matched by original name + MD5) instead of uploaded again, so no duplicate copies
  - never deletes anything in Drive
  - only one instance runs at a time (flock on logs/upload.lock); a second one exits
Only *.pdf files are uploaded (no JSON/CSV/.part).

Auth: needs full Drive scope to write into an existing folder. Token cached in
~/.credentials/drive_uploader_full.json. The first run must be interactive
(opens a browser); unattended runs (launchd) exit with an error instead of hanging.
Exit code 1 if any file failed.

Logging: timestamped lines on the console and appended to
scripts/download/itservicios/logs/upload.log (follow with `tail -f`).
"""
import argparse
import hashlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "download"))



def _reexec_with_google_libs():
    """The invoking python3 lacks the Google libs (e.g. Homebrew's). Re-launch under
    another interpreter that has them, else explain how to install."""
    import os
    import shutil
    import subprocess
    if os.environ.get("_UPLOAD_REEXEC"):
        sys.exit("google-api-python-client / google-auth-oauthlib missing. Install with:\n"
                 f"  {sys.executable} -m pip install google-api-python-client google-auth-oauthlib")
    cands = ["/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
             str(Path.home() / ".pyenv/shims/python3"), "/usr/local/bin/python3",
             shutil.which("python3") or ""]
    for c in cands:
        if c and Path(c).exists() and Path(c).resolve() != Path(sys.executable).resolve():
            ok = subprocess.run([c, "-c", "import googleapiclient, google_auth_oauthlib"],
                                capture_output=True).returncode == 0
            if ok:
                os.environ["_UPLOAD_REEXEC"] = "1"
                os.execv(c, [c, *sys.argv])
    sys.exit("No Python with google-api-python-client found. Install with:\n"
             f"  {sys.executable} -m pip install google-api-python-client google-auth-oauthlib")


try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
except ImportError:
    _reexec_with_google_libs()
from drive_auth import get_credentials

DEFAULT_FOLDER_ID = "1LJMBvUXsy5fzzTKAbeRSqlgmPPkOmp48"
DEFAULT_SRC = REPO / "2026-09" / "pdfs"
SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN = Path.home() / ".credentials" / "drive_uploader_full.json"
FOLDER_MIME = "application/vnd.google-apps.folder"

_local = threading.local()
LOG_FILE = Path(__file__).resolve().parent / "logs" / "upload.log"
_log_lock = threading.Lock()


def log(msg, err=False):
    """Timestamped line to the console (flushed) and to logs/upload.log."""
    line = f"{time.strftime('%F %T')} {msg}"
    with _log_lock:
        print(line, file=sys.stderr if err else sys.stdout, flush=True)
        try:
            LOG_FILE.parent.mkdir(exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def credentials():
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
        if not creds.valid and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                TOKEN.write_text(creds.to_json())
            except Exception:
                creds = None
    if creds and creds.valid:
        return creds
    if not sys.stdin.isatty():
        sys.exit("Drive upload: no valid token and not interactive. Run "
                 "upload_pdfs_to_drive.py once by hand to authorize.")
    return get_credentials(scopes=SCOPES, token_path=TOKEN)


def service(creds):
    """One Drive client per thread (httplib2 is not thread-safe)."""
    if not hasattr(_local, "svc"):
        _local.svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _local.svc


def call(fn, tries=6):
    for i in range(tries):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status not in (403, 429, 500, 502, 503, 504) or i == tries - 1:
                raise
            time.sleep(2 ** i)
        except (ConnectionError, TimeoutError, OSError):
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def list_children(svc, parent_id):
    """{name: [ {'id','md5','folder'}, ... ]} for non-trashed children of a folder
    (Drive allows several files with the same name, so each name maps to a list)."""
    out, token = {}, None
    while True:
        r = call(lambda: svc.files().list(
            q=f"'{parent_id}' in parents and trashed = false",
            fields="nextPageToken, files(id,name,mimeType,md5Checksum)",
            pageSize=1000, pageToken=token).execute())
        for f in r["files"]:
            out.setdefault(f["name"], []).append({"id": f["id"], "md5": f.get("md5Checksum"),
                                                  "folder": f["mimeType"] == FOLDER_MIME})
        token = r.get("nextPageToken")
        if not token:
            return out


def ensure_folders(svc, src, files, root_id):
    """Create the Drive folder chain for every local dir; returns {rel_dir: id}
    and {folder_id: children} listings (one list call per folder)."""
    ids = {Path("."): root_id}
    listings = {root_id: list_children(svc, root_id)}
    for d in sorted({f.relative_to(src).parent for f in files}, key=lambda p: len(p.parts)):
        cur = Path(".")
        for part in d.parts:
            nxt = cur / part
            if nxt not in ids:
                parent = ids[cur]
                hit = next((e for e in listings[parent].get(part, []) if e["folder"]), None)
                if hit:
                    fid = hit["id"]
                else:
                    fid = call(lambda: svc.files().create(
                        body={"name": part, "mimeType": FOLDER_MIME, "parents": [parent]},
                        fields="id").execute())["id"]
                    listings[parent].setdefault(part, []).append({"id": fid, "md5": None, "folder": True})
                ids[nxt] = fid
                listings[fid] = list_children(svc, fid)
            cur = nxt
    return ids, listings


def load_ledger(src):
    """rename_by_folio.py ledger: {original rel path: {'renamed_to': rel path, ...}} -> {new rel: original rel}."""
    import unicodedata
    f = src / ".renames.json"
    if not f.exists():
        return {}
    nfc = lambda x: unicodedata.normalize("NFC", x)
    return {nfc(v["renamed_to"]): nfc(k) for k, v in json.loads(f.read_text(encoding="utf-8")).items()}


def plan_actions(files, src, ids, listings, ledger, md5_of=md5):
    """Decide what to do for each local file. Returns (skipped, renames, todo):
      skipped: count already in Drive (same name + MD5)
      renames: [(drive_entry, new_name, rel)] -- the file was renamed locally by rename_by_folio.py;
               rename the existing Drive copy (found by original name + MD5) instead of re-uploading
      todo:    [(path, parent_id, existing_entry_or_None)] uploads / in-place updates
    The in-memory listing is updated as renames are planned, so swaps (A4->A1 while A1->A21) resolve
    by content hash and never confuse one file with another."""
    import unicodedata
    skipped, renames, todo = 0, [], []
    for p in files:
        rel = unicodedata.normalize("NFC", p.relative_to(src).as_posix())
        parent = ids[p.relative_to(src).parent]
        entries = [e for e in listings[parent].get(p.name, []) if not e["folder"]]
        h = md5_of(p)
        if any(e["md5"] == h for e in entries):
            skipped += 1
            continue
        orig = ledger.get(rel)
        if orig:
            old_name = unicodedata.normalize("NFC", Path(orig).name)
            lst = listings[parent].get(old_name, [])
            cand = next((e for e in lst if not e["folder"] and e["md5"] == h), None)
            if cand:
                lst.remove(cand)
                listings[parent].setdefault(p.name, []).append(cand)
                renames.append((cand, p.name, rel))
                continue
        todo.append((p, parent, entries[0] if len(entries) == 1 else None))
    return skipped, renames, todo


def upload_one(creds, path, parent_id, existing):
    svc = service(creds)
    media = MediaFileUpload(str(path), mimetype="application/pdf", resumable=True)
    if existing:
        call(lambda: svc.files().update(fileId=existing["id"], media_body=media, fields="id").execute())
        return "updated"
    call(lambda: svc.files().create(body={"name": path.name, "parents": [parent_id]},
                                    media_body=media, fields="id").execute())
    return "uploaded"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--folder-id", default=DEFAULT_FOLDER_ID)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", action="append", metavar="SUBDIR",
                    help="only upload PDFs under this folder, relative to SRC_DIR (repeatable), e.g. "
                         "'BIOBÍO/Colegio Edward/4A'; the folder structure above it is still created")
    ap.add_argument("--dry-run", action="store_true", help="Only count local PDFs; no auth, no upload")
    args = ap.parse_args()

    src = args.src.resolve()
    roots = [src / o for o in args.only] if args.only else [src]
    for r in roots:
        if not r.is_dir():
            sys.exit(f"--only folder not found: {r}")
    files = sorted(p for r in roots for p in r.rglob("*.pdf") if p.is_file())
    size_mb = sum(p.stat().st_size for p in files) / 1e6
    # One upload at a time (manual + daily runs share this lock; released on exit/crash).
    import fcntl
    LOG_FILE.parent.mkdir(exist_ok=True)
    lock = open(LOG_FILE.parent / "upload.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another upload is already running; exiting without doing anything")
        return
    log(f"START {len(files)} local PDFs ({size_mb:,.0f} MB) in {src} -> Drive folder {args.folder_id}")
    if args.dry_run or not files:
        return

    log("authenticating with Google Drive...")
    creds = credentials()
    svc = service(creds)
    log("reading Drive folder tree (creating missing folders)...")
    ids, listings = ensure_folders(svc, src, files, args.folder_id)
    log(f"Drive folders ready: {len(ids)} (listed {sum(len(v) for v in listings.values())} existing entries)")

    log("comparing local files with Drive (MD5)...")
    skipped, renames, todo = plan_actions(files, src, ids, listings, load_ledger(src))
    log(f"already in Drive: {skipped}  |  rename in Drive: {len(renames)}  |  to upload/update: {len(todo)}")
    renamed = 0
    for entry, new_name, rel in renames:
        try:
            call(lambda: svc.files().update(fileId=entry["id"], body={"name": new_name}, fields="id").execute())
            renamed += 1
            log(f"RENAMED  (in Drive) -> {rel}")
        except Exception as e:
            log(f"FAIL     rename -> {rel}: {e}", err=True)
            sys.exit(1)

    up = upd = bad = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(upload_one, creds, p, parent, ex): p for p, parent, ex in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            p = futs[fut]
            rel = p.relative_to(src)
            try:
                r = fut.result()
                up += r == "uploaded"
                upd += r == "updated"
                log(f"[{i}/{len(todo)}] {r.upper():8} {rel}")
            except Exception as e:
                bad += 1
                log(f"[{i}/{len(todo)}] FAIL     {rel}: {e}", err=True)
            if i % 50 == 0 or i == len(todo):
                rate = i / (time.time() - t0)
                eta = (len(todo) - i) / rate if rate else 0
                log(f"PROGRESS {i}/{len(todo)} ({i/len(todo):.0%})  {rate:.1f} files/s  ETA {eta/60:.0f} min  "
                    f"uploaded={up} updated={upd} failed={bad}")
    log(f"DONE uploaded={up} updated={upd} renamed={renamed} skipped={skipped} failed={bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
