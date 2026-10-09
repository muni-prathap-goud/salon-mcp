# Salon Booking MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant handle
salon appointments for Jersey's Finest (New Jersey): see open times, book, cancel,
reschedule, and only offer times that fit the user's own calendar.

## Status

| Piece | State |
|---|---|
| Mock salon (two staff, three services, 9 to 6, closed Sunday) | Works, with optional JSON persistence |
| Six booking tools over MCP stdio | Work |
| Calendar-aware slot finder (Google and Apple iCloud) | Works when credentials are configured; skipped otherwise |
| Setmore backend (the real salon) | Stub. Every method raises until the salon grants API access |

## Run it

```bash
uv sync
uv run pytest            # 26 passed
uv run mcp dev server.py # opens the MCP Inspector to call tools by hand
```

## Use it from the Claude desktop app

Add this to `claude_desktop_config.json` and restart the app:

```json
{
  "mcpServers": {
    "salon": {
      "command": "uv",
      "args": ["--directory", "/Users/muniprathapmurari/Projects/salon-mcp", "run", "server.py"]
    }
  }
}
```

Then ask: "Find me a haircut slot on Saturday morning and book it under Muni."

Settings come from environment variables. See `.env.example` for every name.

## Tools

| Tool | Parameters | Returns |
|---|---|---|
| `list_services` | none | `[{service_id, name, minutes}]` |
| `check_open_slots` | `day` (YYYY-MM-DD, salon time), `service_id` | `{day, timezone, open_slots: [{slot_id, starts, with}]}` |
| `find_slots_that_fit_my_calendar` | `day`, `service_id` | Same as above, minus slots within 30 minutes of a calendar event, plus a `calendars` status note |
| `book_appointment` | `slot_id`, `service_id`, `customer_name` | The appointment |
| `cancel_appointment` | `appointment_id` | `{cancelled: appointment}` |
| `reschedule_appointment` | `appointment_id`, `new_slot_id` | The moved appointment |
| `list_my_appointments` | none | Appointments, soonest first |

An appointment looks like `{appointment_id, name, service, starts, ends, with}`, with
times as readable salon-local text such as `Sat Oct 10, 9:00 AM EDT`. The book,
cancel and reschedule descriptions tell the model to confirm with the user first.

## Architecture

```
AI assistant -> server.py (MCP tools) -> BookingBackend interface
                     |                     |-- booking/mock.py     fake salon, runs anywhere
                     |                     `-- booking/setmore.py  real salon, stub for now
                     `-> availability.py -> calendars/google.py, calendars/apple.py
```

`server.py` only talks to the `BookingBackend` interface in `booking/base.py`.
Set `SALON_BACKEND=setmore` to switch backends once `booking/setmore.py` is filled in.
Nothing else needs to change.

## Design decisions

- **UTC inside, local only for display.** Every datetime in the code is timezone-aware
  UTC. Salon-local times are built with the zone attached and converted, so 9 AM stays
  9 AM across the November clock change.
- **Overlap rule.** Two ranges overlap when each starts before the other ends. Touching
  edges do not overlap, so a 9:00 to 9:30 haircut blocks a 9:15 start and allows 9:30.
  The calendar filter uses the same rule with a 30-minute buffer on both sides.
- **Readable errors.** Anything a user should hear about is a `BookingError` with a
  plain message. The server converts it to an MCP `ToolError`, so the model sees
  "That slot is no longer open" rather than a generic failure, and can explain or retry.
- **Failed reschedule keeps the original.** Reschedule lifts the old booking out so it
  cannot block its own new time, checks the new slot, and puts the old booking back
  if the check fails.
- **Calendars are optional.** A calendar that is not configured, or that errors, is
  skipped and named in the result rather than hiding the salon's open slots.
