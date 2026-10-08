"""Busy times from Google Calendar via the free/busy API.

Needs a Google Cloud project with the Calendar API enabled and an OAuth desktop
credentials file. First run opens a browser to sign in; the token is cached.
Both files are git-ignored.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

NAME = "google"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _credentials_path() -> Path:
    return Path(os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json"))


def _token_path() -> Path:
    return Path(os.environ.get("GOOGLE_TOKEN_FILE", "token.json"))


def is_configured() -> bool:
    return _credentials_path().exists()


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    token = _token_path()
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_credentials_path()), SCOPES)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def get_busy_times(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Busy ranges on the primary calendar between start and end, all UTC."""
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "items": [{"id": "primary"}],
    }
    response = _service().freebusy().query(body=body).execute()
    busy = response.get("calendars", {}).get("primary", {}).get("busy", [])
    return [
        (
            datetime.fromisoformat(b["start"]).astimezone(timezone.utc),
            datetime.fromisoformat(b["end"]).astimezone(timezone.utc),
        )
        for b in busy
    ]
