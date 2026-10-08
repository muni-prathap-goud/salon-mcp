"""Salon booking MCP server. Talks only to the BookingBackend interface."""

from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from booking import Appointment, BookingError, Slot, get_backend

mcp = MCPServer("SalonBooking", log_level="ERROR")
backend = get_backend()
SALON_TZ = ZoneInfo(backend.timezone_name)


# ----- helpers -----------------------------------------------------------------


def user_facing_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Turn BookingError into ToolError so the model sees the actual message."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except BookingError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def readable(when: datetime) -> str:
    """Salon-local text such as 'Sat Oct 10, 9:00 AM EDT'."""
    local = when.astimezone(SALON_TZ)
    hour = local.strftime("%I").lstrip("0")
    return f"{local.strftime('%a %b')} {local.day}, {hour}:{local.strftime('%M %p %Z')}"


def parse_day(text: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise BookingError(f"'{text}' is not a valid day; use the form YYYY-MM-DD") from None


def service_name(service_id: str) -> str:
    for service in backend.list_services():
        if service.id == service_id:
            return service.name
    return service_id


_staff_names: dict[str, str] = {}


def remember_staff(slots: list[Slot]) -> None:
    """The interface only exposes staff names on slots, so learn them as we go."""
    for slot in slots:
        _staff_names[slot.staff_id] = slot.staff_name


def staff_name(staff_id: str) -> str:
    return _staff_names.get(staff_id, staff_id.title())


def appointment_json(appt: Appointment) -> dict[str, str]:
    return {
        "appointment_id": appt.id,
        "name": appt.customer_name,
        "service": service_name(appt.service_id),
        "starts": readable(appt.start),
        "ends": readable(appt.end),
        "with": staff_name(appt.staff_id),
    }


def slots_json(day: date, slots: list[Slot]) -> dict[str, Any]:
    remember_staff(slots)
    return {
        "day": day.isoformat(),
        "timezone": backend.timezone_name,
        "open_slots": [
            {"slot_id": s.id, "starts": readable(s.start), "with": s.staff_name} for s in slots
        ],
    }


# ----- tools -------------------------------------------------------------------


@mcp.tool(
    name="list_services",
    description=(
        "List the services the salon offers. Returns service_id, name and length in "
        "minutes. Use the service_id with check_open_slots and book_appointment."
    ),
)
@user_facing_errors
def list_services() -> list[dict[str, Any]]:
    return [
        {"service_id": s.id, "name": s.name, "minutes": s.minutes} for s in backend.list_services()
    ]


@mcp.tool(
    name="check_open_slots",
    description=(
        "Show open appointment times on one day for one service. Returns a list of "
        "slots, each with the slot_id that book_appointment and reschedule_appointment "
        "need, a readable start time in the salon's time zone, and the staff member. "
        "An empty list means the salon is closed or fully booked that day."
    ),
)
@user_facing_errors
def check_open_slots(
    day: Annotated[str, Field(description="Calendar day in the salon's time zone, as YYYY-MM-DD")],
    service_id: Annotated[str, Field(description="A service_id from list_services")],
) -> dict[str, Any]:
    the_day = parse_day(day)
    return slots_json(the_day, backend.get_open_slots(the_day, service_id))


@mcp.tool(
    name="book_appointment",
    description=(
        "Book an open slot. Returns the new appointment, including the appointment_id "
        "needed to cancel or reschedule it. Confirm with the user before calling this."
    ),
)
@user_facing_errors
def book_appointment(
    slot_id: Annotated[str, Field(description="A slot_id from check_open_slots")],
    service_id: Annotated[str, Field(description="A service_id from list_services")],
    customer_name: Annotated[str, Field(description="Name the booking is under")],
) -> dict[str, str]:
    return appointment_json(backend.book(slot_id, service_id, customer_name))


@mcp.tool(
    name="cancel_appointment",
    description=(
        "Cancel an existing appointment by appointment_id (see list_my_appointments). "
        "Returns the cancelled appointment. Confirm with the user before calling this."
    ),
)
@user_facing_errors
def cancel_appointment(
    appointment_id: Annotated[str, Field(description="An appointment_id from a booking or list_my_appointments")],
) -> dict[str, Any]:
    return {"cancelled": appointment_json(backend.cancel(appointment_id))}


@mcp.tool(
    name="reschedule_appointment",
    description=(
        "Move an existing appointment to a different open slot, keeping the same service "
        "and appointment_id. Returns the moved appointment. If the new slot is not open, "
        "the original booking is left unchanged. Confirm with the user before calling this."
    ),
)
@user_facing_errors
def reschedule_appointment(
    appointment_id: Annotated[str, Field(description="An appointment_id from a booking or list_my_appointments")],
    new_slot_id: Annotated[str, Field(description="A slot_id from check_open_slots")],
) -> dict[str, str]:
    return appointment_json(backend.reschedule(appointment_id, new_slot_id))


@mcp.tool(
    name="list_my_appointments",
    description=(
        "List every booked appointment, soonest first, with appointment_id, name, "
        "service, start, end and staff member."
    ),
)
@user_facing_errors
def list_my_appointments() -> list[dict[str, str]]:
    return [appointment_json(a) for a in backend.list_appointments()]


if __name__ == "__main__":
    mcp.run(transport="stdio")
