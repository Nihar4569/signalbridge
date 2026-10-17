"""Reservations: hold replacement stock exactly once (idempotent).

When a DataStore is passed, the operation is also written to the `operations`
collection (Firestore or local memory overlay) — schema.md Tier 2.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# In-process fallback when no store is provided (tests / bare domain calls).
_RESERVATIONS: dict[str, dict] = {}


def make_idempotency_key(plan: dict) -> str:
    """Stable key for plan+offer+quantity so retries map to one reservation."""
    return (
        f"{plan['sku']}:{plan['location_id']}:{plan.get('selected_offer_id')}:"
        f"{plan.get('recovered_qty')}:{plan.get('internal_used_qty', 0)}:v{plan.get('version', 1)}"
    )


def _operation_id(key: str) -> str:
    safe = key.replace(":", "-")
    return f"OP-{safe}"


def reserve(*, plan: dict, supplier: Any, store: Any | None = None) -> dict:
    """Hold stock for an approved plan. Safe to call twice — same result."""
    if plan.get("selected_offer_id") is None:
        raise ValueError("Plan has no feasible offer to reserve.")

    key = make_idempotency_key(plan)
    op_id = _operation_id(key)

    if store is not None:
        existing = store.get_by_id("operations", op_id)
        if existing and existing.get("status") == "succeeded":
            return existing.get("receipt") or existing

    if store is None and key in _RESERVATIONS:
        return _RESERVATIONS[key]

    supplier_qty = plan["recovered_qty"] - plan.get("internal_used_qty", 0)
    if supplier_qty <= 0 or plan.get("supplier_qty", supplier_qty) != supplier_qty:
        raise ValueError("Supplier quantity does not match the external recovery allocation.")
    receipt = supplier.hold(offer_id=plan["selected_offer_id"], qty=supplier_qty)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {
        "idempotency_key": key,
        "operation_id": op_id,
        "offer_id": plan["selected_offer_id"],
        "qty": supplier_qty,
        "recovered_qty": plan["recovered_qty"],
        "internal_qty": plan.get("internal_used_qty", 0),
        "status": "succeeded",
        **receipt,
    }

    if store is None:
        _RESERVATIONS[key] = result

    if store is not None:
        plan_id = plan.get("plan_id") or f"PLAN-{plan['sku']}-{plan['location_id']}"
        operation_doc = {
            "operation_id": op_id,
            "plan_id": plan_id,
            "plan_version": plan.get("version", 1),
            "idempotency_key": key,
            "status": "succeeded",
            "attempts": 1,
            "offer_id": plan["selected_offer_id"],
            "qty": supplier_qty,
            "reservation": {
                "supplier_ref": receipt.get("supplier_ref"),
                "qty": supplier_qty,
                "expires_at": receipt.get("expires_at"),
                "verified_at": receipt.get("verified_at"),
            },
            "receipt": result,
            "last_error": None,
            "updated_at": now,
        }
        store.upsert("operations", op_id, operation_doc)

        plan_doc = {
            **plan,
            "plan_id": plan_id,
            "status": "approved",
            "updated_at": now,
        }
        store.upsert("plans", plan_id, plan_doc)

    return result


def recovered_pairs(store: Any | None) -> set[tuple[str, str]]:
    """(sku, location_id) pairs that already have an approved recovery plan.

    Once a recovery is approved the order is being handled, so it must drop out
    of the threatened list and live in Recoveries instead.
    """
    if store is None:
        return set()
    pairs: set[tuple[str, str]] = set()
    for plan in store.list("plans"):
        if plan.get("status") == "approved" and plan.get("sku") and plan.get("location_id"):
            pairs.add((plan["sku"], plan["location_id"]))
    return pairs
