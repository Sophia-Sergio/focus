#!/usr/bin/env python3
"""Idempotent sync of PDFs from box.itservicios.cl into a local folder,
preserving the server folder tree.

Usage: sync_itservicios.py [OUT_DIR]   (default: <repo>/2026-09/pdfs)
Reads IT_SERVICIOS_KEY from the environment or <repo>/.env.

Safe to run repeatedly: files already present with a matching SHA-256 are
skipped; downloads go to a .part file, are SHA-256 verified, then renamed.
Never deletes anything. Exit code 1 if any file failed.
"""
import hashlib, json, os, ssl, sys, time, urllib.error, urllib.request
from pathlib import Path

BASE = "https://box.itservicios.cl/api/v1"
REPO = Path(__file__).resolve().parents[3]


def load_key():
    key = os.environ.get("IT_SERVICIOS_KEY")
    env = REPO / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("IT_SERVICIOS_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        sys.exit("IT_SERVICIOS_KEY not found in environment or .env")
    return key


def ssl_context():
    # python.org builds on macOS often lack CA certs; fall back to system bundle.
    ctx = ssl.create_default_context()
    if not ctx.get_ca_certs() and os.path.exists("/etc/ssl/cert.pem"):
        ctx = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    return ctx


KEY = load_key()
CTX = ssl_context()


def req(url, tries=4):
    for i in range(tries):
        try:
            r = urllib.request.Request(url, headers={"Authorization": "Bearer " + KEY})
            return urllib.request.urlopen(r, timeout=120, context=CTX)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or i == tries - 1:
                raise
            time.sleep(5 * (i + 1))
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def list_files():
    files, page = [], 1
    while True:
        with req(f"{BASE}/archivos?tipo=pdf&por_pagina=100&pagina={page}") as r:
            d = json.load(r)
        files += d["archivos"]
        if not d["archivos"] or len(files) >= d["total"]:
            return files
        page += 1


def safe(s):
    return s.strip().replace("/", "_")


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("-"):
        sys.exit(__doc__)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "2026-09" / "pdfs"
    files = list_files()
    ok = skip = bad = 0
    for a in files:
        d = out.joinpath(*[safe(s) for s in a["ruta_carpeta"].split(" / ")])
        d.mkdir(parents=True, exist_ok=True)
        dest = d / safe(a["nombre"])
        if dest.exists() and sha256(dest) == a["sha256"]:
            skip += 1
            continue
        tmp = dest.with_name(dest.name + ".part")
        try:
            with req(a["descargar"]) as r, open(tmp, "wb") as f:
                while c := r.read(1 << 20):
                    f.write(c)
            if sha256(tmp) != a["sha256"]:
                raise RuntimeError("sha256 mismatch")
            os.replace(tmp, dest)  # also replaces a changed file of same name
            ok += 1
            print("downloaded", dest.relative_to(out))
        except Exception as e:
            bad += 1
            tmp.unlink(missing_ok=True)
            print(f"FAIL id={a['id']} {a['nombre']}: {e}", file=sys.stderr)
        time.sleep(0.6)  # stay under 120 req/min
    print(f"{time.strftime('%F %T')} listed={len(files)} downloaded={ok} skipped={skip} failed={bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
