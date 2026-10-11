"""Tools the agents are allowed to call.

A "tool" is just a plain Python function with clear type hints and a clear
docstring. ADK shows the docstring to Gemini so it knows when to use the tool.
Each tool reads data through the store and calls deterministic domain code —
tools never do their own math.
"""
from __future__ import annotations

from ..adapters import news as news_adapter
from ..adapters import weather as weather_adapter
from ..core.store import get_store
from ..domain import exposure as exposure_mod
from ..domain import margin as margin_mod
from ..domain import network_balance as nb_mod
from ..domain import planner as planner_mod
from ..domain import surplus as surplus_mod


def weather_risk_tool(location_id: str) -> dict:
    """Check the LIVE weather risk (storm / heavy rain / strong wind) at a
    location, using the free Open-Meteo forecast API."""
    location = get_store().get("locations", "location_id", location_id)
    if not location or location.get("lat") is None:
        return {"ok": False, "error": "unknown location or no coordinates"}
    return weather_adapter.get_weather_risk(location["lat"], location["lon"])


def news_scan_tool(location_id: str) -> dict:
    """Search LIVE news for disruptions (strike, closure, storm, flood) near a
    location, using the free GDELT news API."""
    location = get_store().get("locations", "location_id", location_id)
    if not location:
        return {"ok": False, "error": "unknown location"}
    return news_adapter.search_disruptions(location.get("name", location_id))


def exposure_tool(sku: str, location_id: str) -> dict:
    """Return how many units of a SKU will be short at a location by its earliest
    order deadline. Counts a shipment as delayed only when triage has set its
    risk_zone to "risk" from a live weather or news signal."""
    store = get_store()
    order_lines = store.list("order_lines")
    deadline = planner_mod._earliest_deadline(order_lines, sku, location_id)
    if deadline is None:
        return {"error": "no open orders for this sku/location"}
    balance = store.get("stock_balances", "location_id", location_id)
    on_hand = 0
    for b in store.list("stock_balances"):
        if b["sku"] == sku and b["location_id"] == location_id:
            on_hand = int(b["on_hand_qty"])
            break
    shipments = store.list("shipments")
    scenario = "disrupted" if exposure_mod.is_disrupted(shipments, sku, location_id) else "baseline"
    return exposure_mod.assess_exposure(
        sku=sku,
        location_id=location_id,
        deadline=deadline,
        on_hand_qty=on_hand,
        shipments=shipments,
        order_lines=order_lines,
        scenario=scenario,
    )


def internal_balance_tool(sku: str, location_id: str) -> dict:
    """List our own distribution centres / dark stores that have free stock of a
    SKU to use before buying externally."""
    store = get_store()
    options = nb_mod.find_internal_surplus(
        sku=sku,
        exclude_location_id=location_id,
        stock_balances=store.list("stock_balances"),
        locations=store.list("locations"),
        origin_location_id=location_id,
    )
    return {"options": options, "total_free_qty": sum(o["free_qty"] for o in options)}


def supplier_options_tool(sku: str) -> dict:
    """Return the available supplier offers for a SKU (quantity, price, delivery)."""
    store = get_store()
    offers = [o for o in store.list("supplier_offers") if o["sku"] == sku]
    return {"offers": offers}


def margin_tool(
    shortage_qty: int,
    unit_price_minor: int,
    recovery_cost_minor: int,
    penalty_at_risk_minor: int = 0,
) -> dict:
    """Decide whether a recovery is worth its cost (all money in integer paise)."""
    return margin_mod.assess_margin(
        shortage_qty=shortage_qty,
        unit_price_minor=unit_price_minor,
        recovery_cost_minor=recovery_cost_minor,
        penalty_at_risk_minor=penalty_at_risk_minor,
    )


def surplus_tool(late_shipment_units: int, recovery_qty: int) -> dict:
    """Warn about future overstock when a late shipment arrives after recovery."""
    return surplus_mod.forecast_surplus(
        late_shipment_units=late_shipment_units,
        recovery_qty=recovery_qty,
        original_still_arriving=True,
    )


def build_plan_tool(sku: str, location_id: str) -> dict:
    """Shortcut: build the complete recovery plan in one call (used for demos)."""
    return planner_mod.build_plan(get_store(), sku=sku, location_id=location_id)
