"""Plans = the recovery plan for one SKU/location, plus the approval endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...adapters.email import EmailSender
from ...adapters.supplier import SupplierSimulator
from ...ai import gemini as gemini_mod
from ...core.store import SnapshotStore
from ...domain import decision as decision_mod
from ...domain import fulfillment as fulfillment_mod
from ...domain import planner as planner_mod
from ...domain import reservations as reservations_mod
from ..deps import store_dep

router = APIRouter(prefix="/plans", tags=["plans"])
StoreDependency = Annotated[object, Depends(store_dep)]


class AskBody(BaseModel):
    question: str


@router.get("/{sku}/{location_id}")
def get_plan(sku: str, location_id: str, store: StoreDependency) -> dict:
    """Build and return the full recovery plan for a SKU at a location."""
    return planner_mod.build_plan(store, sku=sku, location_id=location_id)


@router.get("/{sku}/{location_id}/explain")
def explain_plan(sku: str, location_id: str, store: StoreDependency) -> dict:
    """Return a short, plain-English explanation of the plan (uses Gemini if a
    key is set, otherwise the built-in narrative)."""
    plan = planner_mod.build_plan(store, sku=sku, location_id=location_id)
    return gemini_mod.explain_plan(plan)


@router.post("/{sku}/{location_id}/ask")
def ask_plan(sku: str, location_id: str, body: AskBody, store: StoreDependency) -> dict:
    """Answer a free-form question about this plan.

    The whole plan (exposure, every supplier option and why it was rejected,
    margin, surplus, approval tier) is passed to Gemini as grounding context.
    """
    plan = planner_mod.build_plan(store, sku=sku, location_id=location_id)
    return gemini_mod.answer_question(plan, body.question, store=store)


@router.get("/{sku}/{location_id}/brief")
def decision_brief(sku: str, location_id: str, store: StoreDependency) -> dict:
    """Read the saved assessment with its evidence and calculated business impact."""
    snapshot = SnapshotStore(
        {
            name: store.list(name)
            for name in (
                "products",
                "shipments",
                "order_lines",
                "stock_balances",
                "locations",
                "supplier_offers",
                "partners",
                "lanes",
                "signals",
            )
        }
    )
    clock = planner_mod.utc_now()
    plan = planner_mod.build_plan(snapshot, sku=sku, location_id=location_id, as_of=clock)
    return {**decision_mod.build_decision_brief(snapshot, plan, as_of=clock), "plan": plan}


@router.post("/{sku}/{location_id}/approve")
def approve_plan(sku: str, location_id: str, store: StoreDependency) -> dict:
    """Approve a plan, then automate everything that follows.

    Steps (all automatic): reserve stock -> create the internal transfer and the
    supplier purchase order -> email the parties -> mark the order covered.
    Idempotent: approving twice returns the same result, no double-booking.
    See docs/after_plan_approval.md. (Auth is still a TODO — see manual_work.md.)
    """
    plan = planner_mod.build_plan(store, sku=sku, location_id=location_id)
    if plan.get("selected_offer_id") is None:
        return {"status": plan.get("status", "no_feasible_option"), "plan": plan}
    if (plan.get("margin_check") or {}).get("verdict") != "worth_it":
        raise HTTPException(
            status_code=409,
            detail="Recovery benefit does not justify the cost. Review the plan before approval.",
        )

    receipt = reservations_mod.reserve(plan=plan, supplier=SupplierSimulator(), store=store)

    fulfillment = fulfillment_mod.build_fulfillment(store, plan, receipt)
    sender = EmailSender()
    email_results = [
        sender.send(to=e["to"], subject=e["subject"], body=e["body"]) for e in fulfillment["emails"]
    ]
    saved = fulfillment_mod.save_fulfillment(fulfillment, email_results)

    return {"status": "approved", "receipt": receipt, "fulfillment": saved, "plan": plan}
