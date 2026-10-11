"""Internal network balancing.

Before buying from an outside supplier, check whether we already own free stock
in another distribution centre or dark store. Free = on_hand - reserved.
"""
from __future__ import annotations

import math

# Location types that count as "our own" reservable inventory.
INTERNAL_TYPES = ("dc", "dark_store")


def _haversine_km(a: dict, b: dict) -> float | None:
    """Great-circle distance in km between two locations that have lat/lon."""
    if None in (a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon")):
        return None
    radius_km = 6371.0
    lat1 = math.radians(float(a["lat"]))
    lat2 = math.radians(float(b["lat"]))
    d_lat = lat2 - lat1
    d_lon = math.radians(float(b["lon"]) - float(a["lon"]))
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return round(2 * radius_km * math.asin(math.sqrt(h)), 1)


def find_internal_surplus(
    *,
    sku: str,
    exclude_location_id: str,
    stock_balances: list[dict],
    locations: list[dict],
    origin_location_id: str | None = None,
    sort_by: str = "free_qty",
) -> list[dict]:
    """Return internal locations that have free stock of this SKU.

    Default order is richest first. Pass origin_location_id to attach
    distance_km from that site. sort_by="distance" orders nearest first.
    """
    by_id = {loc["location_id"]: loc for loc in locations}
    origin = by_id.get(origin_location_id) if origin_location_id else None
    internal_ids = {
        loc_id
        for loc_id, loc in by_id.items()
        if loc.get("type") in INTERNAL_TYPES and loc.get("active", True)
    }

    options: list[dict] = []
    for balance in stock_balances:
        if balance.get("sku") != sku:
            continue
        location_id = balance.get("location_id")
        if location_id == exclude_location_id or location_id not in internal_ids:
            continue
        free = int(balance.get("on_hand_qty", 0)) - int(balance.get("reserved_qty", 0))
        if free <= 0:
            continue
        option = {"location_id": location_id, "free_qty": free}
        if origin is not None:
            option["distance_km"] = _haversine_km(origin, by_id.get(location_id, {}))
        options.append(option)

    if sort_by == "distance":
        options.sort(
            key=lambda option: (option.get("distance_km") is None, option.get("distance_km") or 0)
        )
    else:
        options.sort(key=lambda option: option["free_qty"], reverse=True)
    return options
