from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from availability import filter_slots, merge_busy
from booking.base import Slot
from booking.mock import MockBackend

NY = ZoneInfo("America/New_York")
PACIFIC = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
FRIDAY = date(2026, 10, 9)


def ny(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 9, hour, minute, tzinfo=NY)


def slots() -> list[Slot]:
    return MockBackend(now=lambda: NOW).get_open_slots(FRIDAY, "haircut")


def starts(kept: list[Slot]) -> set[datetime]:
    return {s.start.astimezone(timezone.utc) for s in kept}


def test_slot_inside_meeting_is_removed():
    kept = filter_slots(slots(), [(ny(10, 0), ny(11, 0))], buffer_minutes=0)
    assert ny(10, 15).astimezone(timezone.utc) not in starts(kept)
    assert ny(12, 0).astimezone(timezone.utc) in starts(kept)


def test_touching_edge_depends_on_buffer():
    # A 9:30-10:00 haircut ends exactly when a 10:00 meeting starts.
    meeting = [(ny(10, 0), ny(11, 0))]
    target = ny(9, 30).astimezone(timezone.utc)
    assert target in starts(filter_slots(slots(), meeting, buffer_minutes=0))
    assert target not in starts(filter_slots(slots(), meeting, buffer_minutes=30))


def test_all_day_event_removes_everything():
    all_day = [(ny(0, 0), datetime(2026, 10, 10, 0, 0, tzinfo=NY))]
    assert filter_slots(slots(), all_day) == []


def test_overlapping_meetings_merge():
    merged = merge_busy([(ny(10, 0), ny(11, 0))], [(ny(10, 30), ny(12, 0))])
    assert merged == [
        (ny(10, 0).astimezone(timezone.utc), ny(12, 0).astimezone(timezone.utc))
    ]


def test_pacific_meeting_blocks_right_new_york_slot():
    # 7:00-8:00 AM Pacific is 10:00-11:00 AM in New York.
    meeting = [(datetime(2026, 10, 9, 7, 0, tzinfo=PACIFIC), datetime(2026, 10, 9, 8, 0, tzinfo=PACIFIC))]
    kept = starts(filter_slots(slots(), meeting, buffer_minutes=0))
    assert ny(10, 30).astimezone(timezone.utc) not in kept
    assert ny(7 + 3, 0).astimezone(timezone.utc) not in kept
    assert ny(11, 0).astimezone(timezone.utc) in kept
    assert ny(9, 30).astimezone(timezone.utc) in kept


def test_no_busy_times_keeps_everything():
    all_slots = slots()
    assert filter_slots(all_slots, []) == all_slots
