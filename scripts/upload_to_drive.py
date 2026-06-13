#!/usr/bin/env python3
"""
Upload 2026-03/pdfs/Avance Regiones to Google Drive, preserving folder structure.
Skips JSON files. Resumes safely: won't re-upload files that already exist in Drive.

Reads GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_DESKTOP (client secret) from scripts/.env
"""

import os
import sys
import json
import pickle
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ── Config ──────────────────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/drive"]
TARGET_FOLDER_ID = "1DOSF0_2dHe00cZXeV8dAETKtvnNu0XC1"
SOURCE_DIR = Path(__file__).parent.parent / "2026-03/pdfs/Avance Regiones"
SCRIPTS_DIR = Path(__file__).parent
TOKEN_FILE = SCRIPTS_DIR / "token.pickle"
# ────────────────────────────────────────────────────────────────────────────


def load_env():
    env_file = SCRIPTS_DIR / ".env"
    env = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def authenticate():
    env = load_env()
    client_id = env.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = env.get("GOOGLE_OAUTH_DESKTOP")
    if not client_id or not client_secret:
        sys.exit("Missing GOOGLE_OAUTH_CLIENT_ID or GOOGLE_OAUTH_DESKTOP in scripts/.env")

    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name, parent_id, folder_cache):
    key = (name, parent_id)
    if key in folder_cache:
        return folder_cache[key]

    # Check if folder already exists in Drive
    q = (
        f"name = {json.dumps(name, ensure_ascii=False)} "
        f"and '{parent_id}' in parents "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = service.files().list(q=q, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        folder_id = files[0]["id"]
    else:
        meta = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=meta, fields="id").execute()
        folder_id = folder["id"]

    folder_cache[key] = folder_id
    return folder_id


def file_exists_in_drive(service, name, parent_id):
    q = (
        f"name = {json.dumps(name, ensure_ascii=False)} "
        f"and '{parent_id}' in parents "
        f"and mimeType != 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = service.files().list(q=q, fields="files(id)").execute()
    return bool(results.get("files"))


def upload_file(service, local_path, parent_id):
    name = local_path.name
    media = MediaFileUpload(str(local_path), resumable=True)
    service.files().create(
        body={"name": name, "parents": [parent_id]},
        media_body=media,
        fields="id",
    ).execute()


def main():
    print("Authenticating with Google Drive...")
    service = authenticate()
    print("Authenticated.\n")

    folder_cache = {}

    all_files = [
        p for p in SOURCE_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() != ".json"
    ]
    total = len(all_files)
    print(f"Found {total} files to upload (excluding JSON).\n")

    uploaded = 0
    skipped = 0
    errors = 0

    for i, local_path in enumerate(sorted(all_files), 1):
        rel = local_path.relative_to(SOURCE_DIR)
        parts = rel.parts  # e.g. ('BioBio', 'School Name', 'grade', 'file.pdf')

        # Build / resolve the folder chain in Drive
        current_parent = TARGET_FOLDER_ID
        for part in parts[:-1]:  # all except the filename
            current_parent = get_or_create_folder(service, part, current_parent, folder_cache)

        filename = local_path.name
        prefix = f"[{i}/{total}]"

        try:
            if file_exists_in_drive(service, filename, current_parent):
                print(f"{prefix} SKIP  {rel}")
                skipped += 1
            else:
                print(f"{prefix} UP    {rel}")
                upload_file(service, local_path, current_parent)
                uploaded += 1
        except Exception as e:
            print(f"{prefix} ERROR {rel}: {e}")
            errors += 1

    print(f"\nDone. Uploaded: {uploaded}  Skipped: {skipped}  Errors: {errors}")


if __name__ == "__main__":
    main()
