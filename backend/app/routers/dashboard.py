"""Dashboard data: KPI overview + map (routes, markers, alerts)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

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
    incidents = _incident_plans(store)
    revenue_at_risk = sum(
        (p.get("margin_check") or {}).get("protected_revenue_minor", 0) for p in incidents
    )
    return {
        "shipments_tracked": len(shipments),
        "on_time": sum(1 for s in shipments if s.get("health") == "on_time"),
        "at_risk": sum(1 for s in shipments if s.get("health") in ("at_risk", "delayed")),
        "orders_at_risk": len(incidents),
        "recovery_ready": sum(1 for p in incidents if p.get("status") == "awaiting_approval"),
        "revenue_at_risk_minor": revenue_at_risk,
        "active_alerts": len(store.list("alerts")),
        "currency": "INR",
    }


@router.get("/map")
def map_data(store=Depends(store_dep)) -> dict:
    """Everything the map needs: routes (polylines), location markers, alerts."""
    lanes = {lane["lane_id"]: lane for lane in store.list("lanes")}

    routes = []
    for shipment in store.list("shipments"):
        lane = lanes.get(shipment.get("lane_id"))
        if not lane:
            continue
        item = (shipment.get("items") or [{}])[0]
        health = shipment.get("health", "on_time")
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
                "progress": shipment.get("progress", 0.5),
                "points": [[p["lat"], p["lon"]] for p in lane.get("points", [])],
                "destination_location_id": shipment.get("destination_location_id"),
                "eta": shipment.get("assumed_arrival_at") or shipment.get("expected_arrival_at"),
                "delay_state": shipment.get("delay_state"),
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
        for loc in store.list("locations")
        if loc.get("lat") is not None
    ]

    return {"routes": routes, "locations": locations, "alerts": store.list("alerts")}
