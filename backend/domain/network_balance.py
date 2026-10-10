"""Internal network balancing.

Before buying from an outside supplier, check whether we already own free stock
in another distribution centre or dark store. Free = on_hand - reserved.
"""
from __future__ import annotations

# Location types that count as "our own" reservable inventory.
INTERNAL_TYPES = ("dc", "dark_store")


def find_internal_surplus(
    *,
    sku: str,
    exclude_location_id: str,
    stock_balances: list[dict],
    locations: list[dict],
) -> list[dict]:
    """Return internal locations that have free stock of this SKU, richest first."""
    internal_ids = {
        loc["location_id"]
        for loc in locations
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
        if free > 0:
            options.append({"location_id": location_id, "free_qty": free})

    options.sort(key=lambda option: option["free_qty"], reverse=True)
    return options
