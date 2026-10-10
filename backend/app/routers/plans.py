"""Plans = the recovery plan for one SKU/location, plus the approval endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...adapters.supplier import SupplierSimulator
from ...domain import planner as planner_mod
from ...domain import reservations as reservations_mod
from ..deps import store_dep

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{sku}/{location_id}")
def get_plan(sku: str, location_id: str, store=Depends(store_dep)) -> dict:
    """Build and return the full recovery plan for a SKU at a location."""
    return planner_mod.build_plan(store, sku=sku, location_id=location_id)


@router.post("/{sku}/{location_id}/approve")
def approve_plan(sku: str, location_id: str, store=Depends(store_dep)) -> dict:
    """Approve a plan and reserve the stock (idempotent).

    NOTE: in the base version there is no auth yet. A real deployment must check
    the approver's role here first — see docs/manual_work.md.
    """
    plan = planner_mod.build_plan(store, sku=sku, location_id=location_id)
    if plan.get("selected_offer_id") is None:
        return {"status": plan.get("status", "no_feasible_option"), "plan": plan}

    receipt = reservations_mod.reserve(plan=plan, supplier=SupplierSimulator())
    return {"status": "reserved", "receipt": receipt, "plan": plan}
