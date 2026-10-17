"""Dashboard data: KPI overview + map (routes, markers, alerts)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...domain import network as network_mod
from ...domain import planner as planner_mod
from ..deps import store_dep

router = APIRouter(tags=["dashboard"])

HEALTH_COLORS = {"on_time": "green", "at_risk": "amber", "delayed": "red"}


def _incident_plans(store) -> list[dict]:
    """Build a plan for every unique open SKU/location and keep the short ones."""
    seen: set[tuple[str, str]] = set()
    plans: list[dict] = []
    for line in store.list("order_lines"):
        if line.get("status") != "open":
            continue
        key = (line["sku"], line["location_id"])
        if key in seen:
            continue
        seen.add(key)
        plan = planner_mod.build_plan(store, sku=key[0], location_id=key[1])
        if (plan.get("exposure") or {}).get("shortage_qty", 0) > 0:
            plans.append(plan)
    return plans


@router.get("/overview")
def overview(store=Depends(store_dep)) -> dict:
    """Headline numbers for the dashboard KPI row."""
    shipments = store.list("shipments")
    health = [network_mod.shipment_health(s) for s in shipments]
    incidents = _incident_plans(store)
    revenue_at_risk = sum(
        (p.get("margin_check") or {}).get("protected_revenue_minor", 0) for p in incidents
    )
    return {
        "shipments_tracked": len(shipments),
        "on_time": health.count("on_time"),
        "at_risk": len(health) - health.count("on_time"),
        "orders_at_risk": len(incidents),
        "recovery_ready": sum(1 for p in incidents if p.get("status") == "awaiting_approval"),
        "revenue_at_risk_minor": revenue_at_risk,
        "active_alerts": len(network_mod.active_alerts(store)),
        "currency": "INR",
    }


@router.get("/map")
def map_data(store=Depends(store_dep)) -> dict:
    """Everything the map needs: routes (polylines), location markers, alerts."""
    lanes = {lane["lane_id"]: lane for lane in store.list("lanes")}
    locations_by_id = {loc["location_id"]: loc for loc in store.list("locations")}

    routes = []
    for shipment in store.list("shipments"):
        lane = lanes.get(shipment.get("lane_id"))
        points = network_mod.lane_points(lane, locations_by_id)
        if len(points) < 2:
            continue
        item = (shipment.get("items") or [{}])[0]
        health = network_mod.shipment_health(shipment)
        routes.append(
            {
                "shipment_id": shipment["shipment_id"],
                "lane_id": shipment["lane_id"],
                "lane_name": lane.get("name"),
                "sku": item.get("sku"),
                "quantity": item.get("quantity"),
                "carrier_id": shipment.get("carrier_id"),
                "health": health,
                "color": HEALTH_COLORS.get(health, "green"),
                "progress": network_mod.shipment_progress(shipment),
                "departed_at": shipment.get("departed_at"),
                "points": [[p["lat"], p["lon"]] for p in points],
                "destination_location_id": shipment.get("destination_location_id"),
                "eta": shipment.get("assumed_arrival_at") or shipment.get("expected_arrival_at"),
                "delay_state": shipment.get("delay_state"),
                "risk_reason": shipment.get("risk_reason"),
            }
        )

    locations = [
        {
            "location_id": loc["location_id"],
            "name": loc.get("name"),
            "type": loc.get("type"),
            "lat": loc.get("lat"),
            "lon": loc.get("lon"),
        }
        for loc in locations_by_id.values()
        if loc.get("lat") is not None
    ]

    return {"routes": routes, "locations": locations, "alerts": network_mod.active_alerts(store)}
