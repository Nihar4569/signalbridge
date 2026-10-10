"""Route monitoring helpers.

Placeholder for the logic that reads a shipment's remaining legs and decides
which external signals to fetch. The base version keeps it simple; see
docs/schema.md section 5 (lanes) for the full design.
"""
from __future__ import annotations

from ..core.store import get_store


def active_shipment_locations() -> list[str]:
    """Return the destination locations of all in-transit shipments."""
    locations = {
        s["destination_location_id"]
        for s in get_store().list("shipments")
        if s.get("status") == "in_transit"
    }
    return sorted(locations)
