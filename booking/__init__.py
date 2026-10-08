"""Booking backends. Use ``get_backend()`` to pick one from the environment."""

from __future__ import annotations

import os

from booking.base import Appointment, BookingBackend, BookingError, Service, Slot

__all__ = ["Appointment", "BookingBackend", "BookingError", "Service", "Slot", "get_backend"]


def get_backend() -> BookingBackend:
    """Return the backend named by ``SALON_BACKEND`` (default ``mock``).

    Backend classes are imported inside the function so a missing Setmore
    dependency never breaks mock mode.
    """
    name = os.environ.get("SALON_BACKEND", "mock").strip().lower()
    if name == "mock":
        from booking.mock import MockBackend

        return MockBackend(state_file=os.environ.get("SALON_STATE_FILE") or None)
    if name == "setmore":
        from booking.setmore import SetmoreBackend

        return SetmoreBackend(refresh_token=os.environ.get("SETMORE_REFRESH_TOKEN"))
    raise ValueError(f"Unknown SALON_BACKEND '{name}'. Use 'mock' or 'setmore'.")
