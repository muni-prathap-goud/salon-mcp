"""Pure logic for fitting salon slots around a personal calendar. No network."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from booking.base import Slot

Busy = tuple[datetime, datetime]


def _utc(when: datetime) -> datetime:
    if when.tzinfo is None:
        raise ValueError("busy times must be timezone-aware")
    return when.astimezone(timezone.utc)


def merge_busy(*lists: Iterable[Busy]) -> list[Busy]:
    """Combine busy ranges from any number of calendars, sorted, overlaps merged."""
    ranges = sorted((_utc(s), _utc(e)) for lst in lists for s, e in lst)
    merged: list[Busy] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def filter_slots(slots: Iterable[Slot], busy: Iterable[Busy], buffer_minutes: int = 30) -> list[Slot]:
    """Keep a slot only if slot.start - buffer .. slot.end + buffer touches no busy range.

    Same overlap rule as the salon: two ranges overlap when each starts before
    the other ends.
    """
    pad = timedelta(minutes=buffer_minutes)
    busy_ranges = merge_busy(busy)
    kept: list[Slot] = []
    for slot in slots:
        start = slot.start - pad
        end = slot.end + pad
        if not any(b_start < end and start < b_end for b_start, b_end in busy_ranges):
            kept.append(slot)
    return kept
