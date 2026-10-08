"""Busy times from iCloud Calendar over CalDAV.

Signs in with an Apple ID and an app-specific password (made in Apple account
settings), read from APPLE_ID and APPLE_APP_PASSWORD.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

NAME = "apple"
ICLOUD_CALDAV_URL = "https://caldav.icloud.com/"


def is_configured() -> bool:
    return bool(os.environ.get("APPLE_ID")) and bool(os.environ.get("APPLE_APP_PASSWORD"))


def _as_utc(value: datetime | date, local_tz: ZoneInfo) -> datetime:
    """CalDAV gives naive datetimes for floating times and plain dates for all-day events."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=local_tz)
        return value.astimezone(timezone.utc)
    return datetime.combine(value, time(0, 0), local_tz).astimezone(timezone.utc)


def get_busy_times(
    start: datetime, end: datetime, local_timezone: str = "America/New_York"
) -> list[tuple[datetime, datetime]]:
    """Busy ranges across every iCloud calendar between start and end, all UTC."""
    import caldav

    local_tz = ZoneInfo(local_timezone)
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    client = caldav.DAVClient(
        url=ICLOUD_CALDAV_URL,
        username=os.environ["APPLE_ID"],
        password=os.environ["APPLE_APP_PASSWORD"],
    )
    busy: list[tuple[datetime, datetime]] = []
    for calendar in client.principal().calendars():
        for event in calendar.search(start=start, end=end, event=True, expand=True):
            component = event.icalendar_component
            if component is None:
                continue
            if str(component.get("TRANSP", "")).upper() == "TRANSPARENT":
                continue  # marked "free" in the calendar
            if str(component.get("STATUS", "")).upper() == "CANCELLED":
                continue
            dtstart = component.get("DTSTART")
            if dtstart is None:
                continue
            ev_start = _as_utc(dtstart.dt, local_tz)
            dtend = component.get("DTEND")
            duration = component.get("DURATION")
            if dtend is not None:
                ev_end = _as_utc(dtend.dt, local_tz)
            elif duration is not None:
                ev_end = ev_start + duration.dt
            elif isinstance(dtstart.dt, datetime):
                ev_end = ev_start
            else:
                ev_end = ev_start + timedelta(days=1)  # all-day with no end
            busy.append((ev_start, ev_end))
    return busy
