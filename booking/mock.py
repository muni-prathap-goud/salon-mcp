"""A fake salon that runs anywhere, with optional JSON persistence."""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from booking.base import Appointment, BookingBackend, BookingError, Service, Slot, parse_slot_id

SERVICES: dict[str, Service] = {
    "haircut": Service("haircut", "Haircut", 30),
    "beard": Service("beard", "Beard trim", 15),
    "haircut_beard": Service("haircut_beard", "Haircut and beard trim", 45),
}
STAFF: dict[str, str] = {"sam": "Sam", "alex": "Alex"}
OPENS = time(9, 0)
CLOSES = time(18, 0)
CLOSED_WEEKDAYS = {6}  # Sunday
SLOT_STEP = timedelta(minutes=15)
MAX_DAYS_AHEAD = 14


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MockBackend(BookingBackend):
    def __init__(
        self,
        timezone_name: str = "America/New_York",
        state_file: str | Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.timezone_name = timezone_name
        self._tz = ZoneInfo(timezone_name)
        self._now = now or _utc_now
        self._state_file = Path(state_file) if state_file else None
        self._appointments: dict[str, Appointment] = {}
        self._load()

    # ----- persistence -------------------------------------------------

    def _load(self) -> None:
        if self._state_file is None or not self._state_file.exists():
            return
        raw = json.loads(self._state_file.read_text())
        for item in raw:
            appt = Appointment(
                id=item["id"],
                customer_name=item["customer_name"],
                service_id=item["service_id"],
                staff_id=item["staff_id"],
                start=datetime.fromisoformat(item["start"]).astimezone(timezone.utc),
                end=datetime.fromisoformat(item["end"]).astimezone(timezone.utc),
            )
            self._appointments[appt.id] = appt

    def _save(self) -> None:
        if self._state_file is None:
            return
        data = [
            {
                "id": a.id,
                "customer_name": a.customer_name,
                "service_id": a.service_id,
                "staff_id": a.staff_id,
                "start": a.start.isoformat(),
                "end": a.end.isoformat(),
            }
            for a in self.list_appointments()
        ]
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(data, indent=2))

    # ----- helpers -----------------------------------------------------

    def _today(self) -> date:
        return self._now().astimezone(self._tz).date()

    def _service(self, service_id: str) -> Service:
        try:
            return SERVICES[service_id]
        except KeyError:
            valid = ", ".join(SERVICES)
            raise BookingError(f"Unknown service '{service_id}'. Valid services: {valid}") from None

    def _is_free(self, staff_id: str, start: datetime, end: datetime) -> bool:
        """True when no appointment for this staff member overlaps [start, end).

        Two ranges overlap when each starts before the other ends. Touching
        edges do not overlap, so a 9:00-9:30 booking leaves 9:30 open.
        """
        for a in self._appointments.values():
            if a.staff_id == staff_id and a.start < end and start < a.end:
                return False
        return True

    def _find_slot(self, slot_id: str, service_id: str) -> Slot:
        """Validate a slot id for booking and return the matching open Slot."""
        staff_id, start = parse_slot_id(slot_id)
        if staff_id not in STAFF:
            raise BookingError(f"Unknown staff member '{staff_id}'. Valid staff: {', '.join(STAFF)}")
        if start <= self._now():
            raise BookingError("That time has already passed")
        day = start.astimezone(self._tz).date()
        for slot in self.get_open_slots(day, service_id):
            if slot.id == slot_id:
                return slot
        raise BookingError("That slot is no longer open")

    # ----- interface ---------------------------------------------------

    def list_services(self) -> list[Service]:
        return list(SERVICES.values())

    def get_open_slots(self, day: date, service_id: str) -> list[Slot]:
        service = self._service(service_id)
        today = self._today()
        if day < today:
            raise BookingError(f"{day.isoformat()} is in the past")
        if day > today + timedelta(days=MAX_DAYS_AHEAD):
            raise BookingError(f"Bookings open only {MAX_DAYS_AHEAD} days ahead")
        if day.weekday() in CLOSED_WEEKDAYS:
            return []

        opens = datetime.combine(day, OPENS, self._tz).astimezone(timezone.utc)
        closes = datetime.combine(day, CLOSES, self._tz).astimezone(timezone.utc)
        length = timedelta(minutes=service.minutes)
        now = self._now()

        slots: list[Slot] = []
        start = opens
        while start + length <= closes:
            if start > now:
                end = start + length
                for staff_id, staff_name in STAFF.items():
                    if self._is_free(staff_id, start, end):
                        slots.append(Slot(staff_id, staff_name, start, end))
            start += SLOT_STEP
        return slots

    def book(self, slot_id: str, service_id: str, customer_name: str) -> Appointment:
        if not customer_name or not customer_name.strip():
            raise BookingError("A customer name is required")
        slot = self._find_slot(slot_id, service_id)
        appt = Appointment(
            id=secrets.token_hex(3),
            customer_name=customer_name.strip(),
            service_id=service_id,
            staff_id=slot.staff_id,
            start=slot.start,
            end=slot.end,
        )
        self._appointments[appt.id] = appt
        self._save()
        return appt

    def cancel(self, appointment_id: str) -> Appointment:
        appt = self._appointments.pop(appointment_id, None)
        if appt is None:
            raise BookingError(f"No appointment with id '{appointment_id}'")
        self._save()
        return appt

    def reschedule(self, appointment_id: str, new_slot_id: str) -> Appointment:
        old = self._appointments.pop(appointment_id, None)
        if old is None:
            raise BookingError(f"No appointment with id '{appointment_id}'")
        try:
            # The old booking is out of the dict so it cannot block its own new time.
            slot = self._find_slot(new_slot_id, old.service_id)
        except BookingError:
            self._appointments[old.id] = old
            raise
        moved = Appointment(
            id=old.id,
            customer_name=old.customer_name,
            service_id=old.service_id,
            staff_id=slot.staff_id,
            start=slot.start,
            end=slot.end,
        )
        self._appointments[moved.id] = moved
        self._save()
        return moved

    def list_appointments(self) -> list[Appointment]:
        return sorted(self._appointments.values(), key=lambda a: a.start)
