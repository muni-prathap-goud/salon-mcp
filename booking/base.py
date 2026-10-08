"""Data shapes and the backend interface every salon booking system must implement.

All datetimes here are timezone-aware and in UTC. Conversion to the salon's local
time zone happens only at the display layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone


class BookingError(Exception):
    """A problem whose message is safe to show directly to a user."""


@dataclass(frozen=True)
class Service:
    id: str
    name: str
    minutes: int


@dataclass(frozen=True)
class Slot:
    staff_id: str
    staff_name: str
    start: datetime  # UTC
    end: datetime  # UTC

    @property
    def id(self) -> str:
        return make_slot_id(self.staff_id, self.start)


@dataclass(frozen=True)
class Appointment:
    id: str
    customer_name: str
    service_id: str
    staff_id: str
    start: datetime  # UTC
    end: datetime  # UTC


_SLOT_TIME_FORMAT = "%Y-%m-%dT%H:%MZ"


def make_slot_id(staff_id: str, start: datetime) -> str:
    """Build an opaque slot id such as ``sam|2026-10-09T13:00Z`` from a UTC start time."""
    if start.tzinfo is None:
        raise ValueError("slot start must be timezone-aware")
    utc_start = start.astimezone(timezone.utc)
    return f"{staff_id}|{utc_start.strftime(_SLOT_TIME_FORMAT)}"


def parse_slot_id(slot_id: str) -> tuple[str, datetime]:
    """Reverse ``make_slot_id``. Raises ``BookingError`` on anything malformed."""
    if not isinstance(slot_id, str) or slot_id.count("|") != 1:
        raise BookingError(f"'{slot_id}' is not a valid slot id")
    staff_id, raw_time = slot_id.split("|")
    if not staff_id:
        raise BookingError(f"'{slot_id}' is not a valid slot id")
    try:
        start = datetime.strptime(raw_time, _SLOT_TIME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        raise BookingError(f"'{slot_id}' is not a valid slot id") from None
    return staff_id, start


class BookingBackend(ABC):
    """What the MCP server needs from any salon booking system."""

    timezone_name: str

    @abstractmethod
    def list_services(self) -> list[Service]: ...

    @abstractmethod
    def get_open_slots(self, day: date, service_id: str) -> list[Slot]:
        """Open slots on a salon-local calendar day."""

    @abstractmethod
    def book(self, slot_id: str, service_id: str, customer_name: str) -> Appointment: ...

    @abstractmethod
    def cancel(self, appointment_id: str) -> Appointment: ...

    @abstractmethod
    def reschedule(self, appointment_id: str, new_slot_id: str) -> Appointment: ...

    @abstractmethod
    def list_appointments(self) -> list[Appointment]: ...
