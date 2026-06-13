#!/usr/bin/env python3
"""
Download specific Google Sheets files as .xlsx into 2026-03/bd/.

Usage:
    python3 2026-03/scripts/download_sheets.py [destination] [--replace]

Reads credentials from scripts/.env (GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_DESKTOP).
Cached token stored at ~/.credentials/drive_downloader.json.
"""

import argparse
import io
import os
import sys
from pathlib import Path

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
except ImportError:
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "download"))
from drive_auth import get_credentials

DEFAULT_DEST = REPO_ROOT / "2026-03" / "bd"

FILE_IDS = [
    "1iQguOff5_BWBRHw1vVYKWKgk-lwx-gSXhQzuin00ZN0",
    "1jB3J_6ilauK40GGh0ApQIpMyyYGPjw1xsTBhFiu0-Js",
]

SPREADSHEET_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def download_sheet(service, file_id: str, dest_dir: Path, replace: bool = False) -> None:
    meta = service.files().get(fileId=file_id, fields="name").execute()
    name = meta["name"]
    if not name.endswith(".xlsx"):
        name += ".xlsx"
    dest = dest_dir / name

    if dest.exists() and not replace:
        print(f"  Skipping (already exists): {dest.name}")
        return

    print(f"  Downloading: {dest.name}")
    request = service.files().export_media(fileId=file_id, mimeType=SPREADSHEET_MIME)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with io.FileIO(dest, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"    {int(status.progress() * 100)}%", end="\r")
    print(f"  Done: {dest}")


def main():
    parser = argparse.ArgumentParser(description="Download Google Sheets as .xlsx.")
    parser.add_argument("destination", nargs="?", default=str(DEFAULT_DEST), help="Destination folder")
    parser.add_argument("--replace", action="store_true", help="Re-download even if file already exists")
    args = parser.parse_args()

    dest_dir = Path(args.destination)
    dest_dir.mkdir(parents=True, exist_ok=True)

    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)

    for file_id in FILE_IDS:
        download_sheet(service, file_id, dest_dir, replace=args.replace)

    print("\nAll done.")


if __name__ == "__main__":
    main()
