"""Reservations: actually hold the replacement stock, exactly once.

In the base version this holds stock in the in-memory supplier simulator. The
important idea to keep from day one is **idempotency**: the same approved plan,
retried twice, must never book twice.
"""
from __future__ import annotations

# In-memory record of what we have already reserved, keyed by idempotency key.
# Later this becomes the Firestore `operations` collection.
_RESERVATIONS: dict[str, dict] = {}


def make_idempotency_key(plan: dict) -> str:
    """A stable key for a plan+offer+quantity, so retries map to one reservation."""
    return f"{plan['sku']}:{plan['location_id']}:{plan.get('selected_offer_id')}:{plan.get('recovered_qty')}:v{plan.get('version', 1)}"


def reserve(*, plan: dict, supplier) -> dict:
    """Hold stock for an approved plan. Safe to call twice — returns the same result."""
    if plan.get("selected_offer_id") is None:
        raise ValueError("Plan has no feasible offer to reserve.")

    key = make_idempotency_key(plan)
    if key in _RESERVATIONS:
        return _RESERVATIONS[key]  # already done — do not book again

    receipt = supplier.hold(offer_id=plan["selected_offer_id"], qty=plan["recovered_qty"])
    result = {
        "idempotency_key": key,
        "offer_id": plan["selected_offer_id"],
        "qty": plan["recovered_qty"],
        "status": "succeeded",
        **receipt,
    }
    _RESERVATIONS[key] = result
    return result
