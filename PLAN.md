# Salon Booking MCP Server: Build Plan

An MCP server that lets an AI assistant handle salon appointments for Jersey's Finest
(New Jersey, books through Setmore): see open times, book, cancel, reschedule, and only
offer times that fit my own calendar.

## Architecture

```
AI assistant -> server.py (MCP tools) -> BookingBackend interface
                     |                     |-- booking/mock.py     fake salon, runs anywhere
                     |                     `-- booking/setmore.py  real salon, stub for now
                     `-> availability.py -> calendars/google.py, calendars/apple.py
```

Rules that hold for the whole project:

- `server.py` only talks to the `BookingBackend` interface, never to a specific backend.
- Every datetime inside the code is timezone-aware and in UTC. Convert to the salon's
  time zone (America/New_York) only when showing a time to a person.
- Problems a user should hear about are raised as `BookingError` with a plain message.
- No secrets in the repo. Settings come from environment variables.
- Run everything with `uv run ...`, never plain `python` or `pytest`.

## Phases

| Phase | Deliverable | State |
|---|---|---|
| 0 | Project setup and first commit | Done |
| 1 | `booking/base.py`: `BookingError`, `Service`, `Slot`, `Appointment`, slot id helpers, `BookingBackend` | Done |
| 2 | `booking/mock.py`, `booking/__init__.py` (`get_backend`), `booking/setmore.py` stub | Done |
| 3 | `tests/test_mock_backend.py`, 20 tests | Done |
| 4 | `server.py` with six tools, `BookingError` mapped to `ToolError` | Done |
| 5 | Try it in the MCP Inspector and the Claude desktop app; record a screen capture | Done (screen capture skipped) |
| 6 | `calendars/google.py`, `calendars/apple.py`, `availability.py`, seventh tool, 6 tests | Done. Apple connected; Google not set up |
| 7 | README, `.env.example`, pre-push secret check, push to GitHub | Done |
| Later | Fill in `booking/setmore.py` when the salon grants API access | Waiting on salon |

## Mock salon rules

- Services: haircut 30 min, beard 15 min, haircut_beard 45 min
- Staff: sam and alex
- Open 9:00 to 18:00 salon time, closed Sunday
- Start times every 15 minutes, bookings allowed up to 14 days ahead
- Overlap rule: `a.start < end and start < a.end`, same staff member only
- Reschedule removes the old booking before checking the new slot and restores it on failure

## Calendar rules

- `merge_busy(*lists)`: combine and sort busy ranges, merging overlaps
- `filter_slots(slots, busy, buffer_minutes=30)`: keep a slot only if
  `slot.start - buffer .. slot.end + buffer` overlaps no busy range
- A calendar that is not configured is skipped and named in the tool result

## Before the first push

1. `git status` and read every file name.
2. `git grep -n -i "password\|token\|secret"` and read every hit.
3. Confirm `git config user.email` is the muni-prathap-goud noreply address.
4. Create the repo under muni-prathap-goud on GitHub, add it as the remote, push main.

## Questions I should be able to answer when it is done

- Why store times in UTC and convert only for display?
- How does the overlap check work, and why does a slot that touches a booking's edge stay open?
- Why does reschedule remove the old booking before checking the new slot?
- Why is there an interface between the server and the booking system?
- How does the model decide which tool to call?
- What does the model see when a tool fails, and why does that matter?
- What changes when Setmore access arrives?
