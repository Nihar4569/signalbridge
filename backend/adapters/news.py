"""News / disruption signal adapter.

In the base version this just returns the pre-seeded events from the fixtures so
the demo is deterministic. Later, swap in a real source (GDELT, port notices).
See docs/manual_work.md.
"""
from __future__ import annotations

from ..core.store import get_store


def fetch_events(location_ids: list[str] | None = None) -> list[dict]:
    """Return validated disruption events, optionally filtered by location."""
    events = get_store().list("events")
    if location_ids is None:
        return events
    wanted = set(location_ids)
    return [e for e in events if (e.get("where") or {}).get("location_id") in wanted]
