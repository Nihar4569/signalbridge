"""Exposure = how short we will be of a product by a deadline.

This is the heart of SignalBridge and the one module everything else depends on.
It is deliberately pure: give it numbers, it returns numbers. Fully unit-tested.

The idea (this is the industry's "Available-to-Promise" check):

    supply_by(deadline) = on_hand + incoming arriving on/before the deadline
    demand_by(deadline) = open orders due on/before the deadline
    shortage            = max(0, demand - supply)

A disruption does NOT change on_hand. It changes whether an incoming shipment
counts as "arriving in time" — i.e. which bucket its units fall into.
"""
from __future__ import annotations

from datetime import datetime


def parse_ts(ts: str) -> datetime:
    """Parse a UTC ISO-8601 string like '2026-10-16T12:00:00Z'."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


_DELAYED_STATES = ("assumed_delayed", "confirmed_delayed")


def is_disrupted(shipments: list[dict], sku: str, location_id: str) -> bool:
    """Is any incoming shipment of this sku/location actually flagged delayed?

    Reads real per-shipment fields only — `delay_state` (set by the carrier
    feed / route monitor) or `risk_zone` (set by domain/triage.py from live
    weather/news signals). Never assume "disrupted"; derive it.
    """
    for shipment in shipments:
        if shipment.get("destination_location_id") != location_id:
            continue
        if not any(item.get("sku") == sku for item in shipment.get("items", [])):
            continue
        if shipment.get("delay_state") in _DELAYED_STATES:
            return True
        if shipment.get("risk_zone") == "risk":
            return True
    return False


def demand_by(deadline: datetime, sku: str, location_id: str, order_lines: list[dict]) -> int:
    """Total open order units for this SKU/location due on or before the deadline."""
    total = 0
    for line in order_lines:
        if line.get("sku") != sku or line.get("location_id") != location_id:
            continue
        if line.get("status") != "open":
            continue
        if parse_ts(line["due_at"]) <= deadline:
            total += int(line["quantity"])
    return total


def incoming_by(
    deadline: datetime,
    sku: str,
    location_id: str,
    shipments: list[dict],
    *,
    use_assumed: bool,
) -> int:
    """Incoming units expected at this location on or before the deadline.

    When `use_assumed` is True we use each shipment's `assumed_arrival_at`
    (the disruption scenario) instead of its normal `expected_arrival_at`.
    """
    total = 0
    for shipment in shipments:
        if shipment.get("destination_location_id") != location_id:
            continue
        if shipment.get("status") not in ("in_transit", "planned"):
            continue
        arrival = shipment["expected_arrival_at"]
        if use_assumed and shipment.get("assumed_arrival_at"):
            arrival = shipment["assumed_arrival_at"]
        if parse_ts(arrival) > deadline:
            continue
        for item in shipment.get("items", []):
            if item.get("sku") == sku:
                total += int(item["quantity"])
    return total


def assess_exposure(
    *,
    sku: str,
    location_id: str,
    deadline: datetime | str,
    on_hand_qty: int,
    shipments: list[dict],
    order_lines: list[dict],
    scenario: str = "baseline",
) -> dict:
    """Return the shortage picture for one SKU at one location.

    scenario = "baseline"  -> use normal arrival times (nothing went wrong)
    scenario = "disrupted" -> use assumed (delayed) arrival times
    """
    if isinstance(deadline, str):
        deadline = parse_ts(deadline)
    use_assumed = scenario == "disrupted"

    incoming = incoming_by(deadline, sku, location_id, shipments, use_assumed=use_assumed)
    supply = on_hand_qty + incoming
    demand = demand_by(deadline, sku, location_id, order_lines)
    shortage = max(0, demand - supply)

    return {
        "sku": sku,
        "location_id": location_id,
        "deadline": deadline.isoformat(),
        "scenario": scenario,
        "on_hand_qty": on_hand_qty,
        "incoming_by_deadline": incoming,
        "supply_by_deadline": supply,
        "demand_by_deadline": demand,
        "shortage_qty": shortage,
        "is_actionable": shortage > 0,
    }
