"""Fulfillments = tracking for what happened after a plan was approved."""
from __future__ import annotations

from fastapi import APIRouter

from ...domain import fulfillment as fulfillment_mod

router = APIRouter(prefix="/fulfillments", tags=["fulfillments"])


@router.get("")
def list_fulfillments() -> dict:
    """List every approved recovery and its post-approval status."""
    items = fulfillment_mod.list_fulfillments()
    return {"count": len(items), "fulfillments": items}


@router.get("/{operation_id}")
def get_fulfillment(operation_id: str) -> dict:
    """Return one fulfillment (its actions, emails, and status timeline)."""
    item = fulfillment_mod.get_fulfillment(operation_id)
    if not item:
        return {"error": "not found"}
    return item
