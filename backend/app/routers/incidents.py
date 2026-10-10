"""Incidents = SKUs/locations that currently have a shortage."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...domain import exposure as exposure_mod
from ...domain import planner as planner_mod
from ..deps import store_dep

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
def list_incidents(store=Depends(store_dep)) -> dict:
    """List every SKU/location pair that is short under the disruption scenario."""
    order_lines = store.list("order_lines")
    shipments = store.list("shipments")
    balances = store.list("stock_balances")

    incidents = []
    seen = set()
    for line in order_lines:
        key = (line["sku"], line["location_id"])
        if key in seen or line.get("status") != "open":
            continue
        seen.add(key)
        sku, location_id = key
        deadline = planner_mod._earliest_deadline(order_lines, sku, location_id)
        on_hand = next(
            (int(b["on_hand_qty"]) for b in balances
             if b["sku"] == sku and b["location_id"] == location_id),
            0,
        )
        exposure = exposure_mod.assess_exposure(
            sku=sku,
            location_id=location_id,
            deadline=deadline,
            on_hand_qty=on_hand,
            shipments=shipments,
            order_lines=order_lines,
            scenario="disrupted",
        )
        if exposure["is_actionable"]:
            incidents.append(exposure)

    return {"count": len(incidents), "incidents": incidents}
