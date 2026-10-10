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


def signal_scan_location_ids() -> list[str]:
    """Locations the monitor should ask weather and news about.

    In-transit destinations, plus active ports. The port is where a delay
    usually starts; the warehouse is where the shipment is headed.
    """
    locations = get_store().list("locations")
    ids = set(active_shipment_locations())
    for loc in locations:
        if loc.get("type") == "port" and loc.get("active", True):
            ids.add(loc["location_id"])
    known = {loc["location_id"] for loc in locations}
    return sorted(ids & known)
