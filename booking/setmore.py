"""Real salon backend for Setmore. Stub until the salon grants API access."""

from __future__ import annotations

from datetime import date

from booking.base import Appointment, BookingBackend, Service, Slot

_MESSAGE = "SetmoreBackend is not implemented yet: it needs the salon's Setmore API access"


class SetmoreBackend(BookingBackend):
    timezone_name = "America/New_York"

    def __init__(self, refresh_token: str | None = None) -> None:
        self._refresh_token = refresh_token

    def list_services(self) -> list[Service]:
        raise NotImplementedError(_MESSAGE)

    def get_open_slots(self, day: date, service_id: str) -> list[Slot]:
        raise NotImplementedError(_MESSAGE)

    def book(self, slot_id: str, service_id: str, customer_name: str) -> Appointment:
        raise NotImplementedError(_MESSAGE)

    def cancel(self, appointment_id: str) -> Appointment:
        raise NotImplementedError(_MESSAGE)

    def reschedule(self, appointment_id: str, new_slot_id: str) -> Appointment:
        raise NotImplementedError(_MESSAGE)

    def list_appointments(self) -> list[Appointment]:
        raise NotImplementedError(_MESSAGE)
