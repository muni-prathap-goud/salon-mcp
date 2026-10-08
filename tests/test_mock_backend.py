from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from booking.base import BookingError, make_slot_id
from booking.mock import MockBackend

NY = ZoneInfo("America/New_York")
# Thursday 8 Oct 2026, 12:00 UTC = 8:00 AM in New York, before the salon opens.
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
FRIDAY = date(2026, 10, 9)
SUNDAY = date(2026, 10, 11)


def local(day: date, hour: int, minute: int = 0) -> datetime:
    """A salon-local wall-clock time as a UTC datetime."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=NY).astimezone(timezone.utc)


@pytest.fixture
def backend() -> MockBackend:
    return MockBackend(now=lambda: NOW)


# ----- open slots -----------------------------------------------------------


def test_first_slot_opens_at_nine_and_last_ends_at_six(backend):
    slots = backend.get_open_slots(FRIDAY, "haircut")
    assert slots[0].start == local(FRIDAY, 9, 0)
    assert max(s.end for s in slots) == local(FRIDAY, 18, 0)


def test_longer_service_has_fewer_slots(backend):
    assert len(backend.get_open_slots(FRIDAY, "haircut_beard")) < len(
        backend.get_open_slots(FRIDAY, "haircut")
    )


def test_sunday_is_closed(backend):
    assert backend.get_open_slots(SUNDAY, "haircut") == []


def test_past_day_raises(backend):
    with pytest.raises(BookingError):
        backend.get_open_slots(date(2026, 10, 7), "haircut")


def test_day_beyond_window_raises(backend):
    with pytest.raises(BookingError):
        backend.get_open_slots(date(2026, 10, 8) + timedelta(days=15), "haircut")


def test_unknown_service_raises(backend):
    with pytest.raises(BookingError, match="haircut"):
        backend.get_open_slots(FRIDAY, "massage")


def test_today_only_offers_future_slots():
    now = local(date(2026, 10, 8), 14, 10)
    backend = MockBackend(now=lambda: now)
    slots = backend.get_open_slots(date(2026, 10, 8), "haircut")
    assert slots[0].start == local(date(2026, 10, 8), 14, 15)


def test_opening_time_tracks_clock_change():
    backend = MockBackend(now=lambda: datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc))
    before = backend.get_open_slots(date(2026, 10, 30), "haircut")
    after = backend.get_open_slots(date(2026, 11, 2), "haircut")
    assert before[0].start == datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc)
    assert after[0].start == datetime(2026, 11, 2, 14, 0, tzinfo=timezone.utc)


# ----- booking ----------------------------------------------------------------


def test_booked_slot_disappears_for_that_staff_only(backend):
    slot_id = make_slot_id("sam", local(FRIDAY, 10, 0))
    backend.book(slot_id, "haircut", "Muni")
    ids = {s.id for s in backend.get_open_slots(FRIDAY, "haircut")}
    assert slot_id not in ids
    assert make_slot_id("alex", local(FRIDAY, 10, 0)) in ids


def test_booking_blocks_overlap_but_not_touching_edge(backend):
    backend.book(make_slot_id("sam", local(FRIDAY, 9, 0)), "haircut", "Muni")
    ids = {s.id for s in backend.get_open_slots(FRIDAY, "haircut")}
    assert make_slot_id("sam", local(FRIDAY, 9, 15)) not in ids
    assert make_slot_id("sam", local(FRIDAY, 9, 30)) in ids


def test_double_booking_raises(backend):
    slot_id = make_slot_id("sam", local(FRIDAY, 10, 0))
    backend.book(slot_id, "haircut", "Muni")
    with pytest.raises(BookingError, match="no longer open"):
        backend.book(slot_id, "haircut", "Someone else")


def test_blank_name_raises(backend):
    with pytest.raises(BookingError):
        backend.book(make_slot_id("sam", local(FRIDAY, 10, 0)), "haircut", "   ")


def test_bad_slot_ids_raise(backend):
    with pytest.raises(BookingError, match="not a valid slot id"):
        backend.book("nonsense", "haircut", "Muni")
    with pytest.raises(BookingError, match="no longer open"):
        backend.book(make_slot_id("sam", local(FRIDAY, 13, 7)), "haircut", "Muni")


def test_slot_in_the_past_raises(backend):
    with pytest.raises(BookingError):
        backend.book(make_slot_id("sam", local(date(2026, 10, 7), 10, 0)), "haircut", "Muni")


# ----- cancel and reschedule ---------------------------------------------------


def test_cancel_frees_slot(backend):
    slot_id = make_slot_id("sam", local(FRIDAY, 10, 0))
    appt = backend.book(slot_id, "haircut", "Muni")
    cancelled = backend.cancel(appt.id)
    assert cancelled.id == appt.id
    assert backend.list_appointments() == []
    assert slot_id in {s.id for s in backend.get_open_slots(FRIDAY, "haircut")}


def test_cancel_unknown_id_raises(backend):
    with pytest.raises(BookingError):
        backend.cancel("nope")


def test_reschedule_keeps_id_and_frees_old_slot(backend):
    old_slot = make_slot_id("sam", local(FRIDAY, 10, 0))
    new_slot = make_slot_id("alex", local(FRIDAY, 15, 0))
    appt = backend.book(old_slot, "haircut", "Muni")
    moved = backend.reschedule(appt.id, new_slot)
    assert moved.id == appt.id
    assert moved.staff_id == "alex"
    assert moved.start == local(FRIDAY, 15, 0)
    ids = {s.id for s in backend.get_open_slots(FRIDAY, "haircut")}
    assert old_slot in ids
    assert new_slot not in ids
    assert backend.list_appointments() == [moved]


def test_reschedule_fifteen_minutes_later_same_staff(backend):
    appt = backend.book(make_slot_id("sam", local(FRIDAY, 10, 0)), "haircut", "Muni")
    moved = backend.reschedule(appt.id, make_slot_id("sam", local(FRIDAY, 10, 15)))
    assert moved.start == local(FRIDAY, 10, 15)
    assert moved.end == local(FRIDAY, 10, 45)


def test_failed_reschedule_keeps_original(backend):
    taken = make_slot_id("sam", local(FRIDAY, 11, 0))
    backend.book(taken, "haircut", "Other person")
    appt = backend.book(make_slot_id("sam", local(FRIDAY, 10, 0)), "haircut", "Muni")
    with pytest.raises(BookingError, match="no longer open"):
        backend.reschedule(appt.id, taken)
    assert appt in backend.list_appointments()
    assert len(backend.list_appointments()) == 2


# ----- saving --------------------------------------------------------------------


def test_state_survives_restart(tmp_path):
    state = tmp_path / "state.json"
    first = MockBackend(state_file=state, now=lambda: NOW)
    appt = first.book(make_slot_id("sam", local(FRIDAY, 10, 0)), "haircut", "Muni")
    second = MockBackend(state_file=state, now=lambda: NOW)
    assert second.list_appointments() == [appt]
