"""Shared Google Drive OAuth helpers for download scripts."""

import sys
from pathlib import Path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_PATH = Path.home() / ".credentials" / "drive_downloader.json"
ENV_FILE = Path(__file__).parent.parent / ".env"


def load_env(env_path: Path = ENV_FILE) -> dict:
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def get_credentials(credentials_file: str = "credentials.json",
                    scopes=None, token_path: Path = None) -> Credentials:
    """Defaults to the read-only token; pass scopes/token_path for e.g. uploads."""
    scopes = scopes or SCOPES
    token_path = token_path or TOKEN_PATH
    creds = None
    token_path.parent.mkdir(parents=True, exist_ok=True)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            env = load_env()
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
                flow = InstalledAppFlow.from_client_config(client_config, scopes)
            elif Path(credentials_file).exists():
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            else:
                print(f"Error: no credentials found in '{ENV_FILE}' or '{credentials_file}'")
                print("Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_DESKTOP in scripts/.env")
                sys.exit(1)

            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json())

    return creds
