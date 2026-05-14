#!/usr/bin/env python3
"""
Download all files from a shared Google Drive folder.

Usage:
    python3 download_drive_folder.py <folder_id_or_url> [destination]

Requirements:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Authentication:
    First run will open a browser to authorize access. Credentials are cached
    in ~/.credentials/drive_downloader.json for subsequent runs.

    To set up:
    1. Go to https://console.cloud.google.com/
    2. Create a project and enable the Google Drive API
    3. Create OAuth 2.0 credentials (Desktop app)
    4. Download the JSON and save as credentials.json in this directory
       (or pass --credentials <path>)
"""

import argparse
import io
import os
import re
import sys
from pathlib import Path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
except ImportError:
    print("Installing required libraries...")
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_PATH = Path.home() / ".credentials" / "drive_downloader.json"

GOOGLE_DOCS_EXPORT = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}


def extract_folder_id(folder_id_or_url: str) -> str:
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", folder_id_or_url)
    if match:
        return match.group(1)
    match = re.search(r"id=([a-zA-Z0-9_-]+)", folder_id_or_url)
    if match:
        return match.group(1)
    return folder_id_or_url


def load_env(env_path: Path) -> dict:
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def get_credentials(credentials_file: str) -> Credentials:
    creds = None
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Try loading from .env first, then fall back to credentials.json
            env_file = Path(__file__).parent.parent / ".env"
            env = load_env(env_file)
            client_id = env.get("GOOGLE_OAUTH_CLIENT_ID")
            client_secret = env.get("GOOGLE_OAUTH_DESKTOP")

            if client_id and client_secret:
                client_config = {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            elif Path(credentials_file).exists():
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            else:
                print(f"Error: no credentials found in '{env_file}' or '{credentials_file}'")
                print("Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_DESKTOP in scripts/.env")
                sys.exit(1)

            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def list_folder(service, folder_id: str) -> list:
    items = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageToken=page_token,
            )
            .execute()
        )
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return items


def download_file(service, file_id: str, file_name: str, mime_type: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    if mime_type in GOOGLE_DOCS_EXPORT:
        export_mime, ext = GOOGLE_DOCS_EXPORT[mime_type]
        if not file_name.endswith(ext):
            file_name += ext
        dest = dest.parent / file_name
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    elif mime_type.startswith("application/vnd.google-apps."):
        print(f"  Skipping unsupported Google type: {file_name} ({mime_type})")
        return
    else:
        request = service.files().get_media(fileId=file_id)

    if dest.exists():
        print(f"  Skipping (already exists): {dest.name}")
        return

    print(f"  Downloading: {dest.name}")
    with io.FileIO(dest, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"    {int(status.progress() * 100)}%", end="\r")
    print()


def download_folder(service, folder_id: str, dest: Path, recursive: bool) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    items = list_folder(service, folder_id)

    if not items:
        print(f"  No files found in folder.")
        return

    for item in items:
        name = item["name"]
        mime = item["mimeType"]
        fid = item["id"]

        if mime == "application/vnd.google-apps.folder":
            if recursive:
                print(f"\nEntering subfolder: {name}/")
                download_folder(service, fid, dest / name, recursive)
        else:
            download_file(service, fid, name, mime, dest / name)


def main():
    parser = argparse.ArgumentParser(description="Download files from a shared Google Drive folder.")
    parser.add_argument("folder", help="Google Drive folder ID or URL")
    parser.add_argument("destination", nargs="?", default=".", help="Local destination directory (default: current dir)")
    parser.add_argument("--credentials", default="credentials.json", help="Path to OAuth credentials JSON file")
    parser.add_argument("--recursive", "-r", action="store_true", help="Download subfolders recursively")
    args = parser.parse_args()

    folder_id = extract_folder_id(args.folder)
    dest = Path(args.destination)

    print(f"Folder ID : {folder_id}")
    print(f"Destination: {dest.resolve()}")

    creds = get_credentials(args.credentials)
    service = build("drive", "v3", credentials=creds)

    print("\nStarting download...\n")
    download_folder(service, folder_id, dest, args.recursive)
    print("\nDone.")


if __name__ == "__main__":
    main()
