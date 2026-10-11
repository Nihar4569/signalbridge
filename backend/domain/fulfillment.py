"""What happens after a plan is approved.

build_fulfillment() turns an approved plan into concrete, automated actions:
  1. an INTERNAL TRANSFER for the units taken from our own stores, and
  2. a PURCHASE ORDER for the units bought from a supplier,
plus the EMAILS that notify each party, and a simple status timeline.

Nothing here does real I/O. The approve endpoint sends the emails (via the email
adapter) and stores the result. See docs/after_plan_approval.md.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..core import config

# In-memory record of fulfillments, keyed by operation_id. Later: Firestore.
_FULFILLMENTS: dict[str, dict] = {}


def build_fulfillment(store, plan: dict, receipt: dict) -> dict:
    """Assemble the post-approval actions + emails for an approved plan."""
    partners = {p["partner_id"]: p for p in store.list("partners")}
    offers = {o["offer_id"]: o for o in store.list("supplier_offers")}

    sku = plan["sku"]
    destination = plan["location_id"]
    internal_used = int(plan.get("internal_used_qty", 0))
    recovered = int(plan.get("recovered_qty", 0))
    remainder = max(0, recovered - internal_used)

    actions: list[dict] = []
    emails: list[dict] = []

    # 1. Internal transfers (divert our own free stock first).
    allocated = 0
    for option in plan.get("internal_options", []):
        if allocated >= internal_used:
            break
        take = min(int(option["free_qty"]), internal_used - allocated)
        if take <= 0:
            continue
        allocated += take
        transfer = {
            "type": "internal_transfer",
            "from_location_id": option["location_id"],
            "to_location_id": destination,
            "sku": sku,
            "qty": take,
        }
        actions.append(transfer)
        emails.append(_internal_transfer_email(transfer, plan))

    # 2. Purchase order for the remainder (external supplier).
    if remainder > 0 and plan.get("selected_offer_id"):
        offer = offers.get(plan["selected_offer_id"], {})
        supplier = partners.get(offer.get("supplier_id"), {})
        po = {
            "type": "purchase_order",
            "offer_id": plan["selected_offer_id"],
            "supplier_id": offer.get("supplier_id"),
            "supplier_name": supplier.get("name", "Supplier"),
            "sku": sku,
            "qty": remainder,
            "deliver_to_location_id": offer.get("deliver_to_location_id", destination),
            "unit_price_minor": offer.get("unit_price_minor"),
            "delivery_latest": offer.get("delivery_latest"),
            "reservation_ref": receipt.get("supplier_ref"),
        }
        actions.append(po)
        emails.append(_purchase_order_email(supplier, po, plan))

    fulfillment = {
        "operation_id": receipt.get("idempotency_key"),
        "sku": sku,
        "location_id": destination,
        "recovered_qty": recovered,
        "actions": actions,
        "emails": emails,
        "order_update": {
            "sku": sku,
            "location_id": destination,
            "recovery_coverage_qty": recovered,
            "note": "Threatened order is now COVERED BY A RECOVERY PLAN (not yet physically delivered).",
        },
        "status": "in_progress",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return fulfillment


# ---- in-memory tracking store ----------------------------------------------

def save_fulfillment(fulfillment: dict, email_results: list[dict]) -> dict:
    """Store the fulfillment (idempotent) and attach the email send results."""
    op_id = fulfillment["operation_id"]
    if op_id in _FULFILLMENTS:
        return _FULFILLMENTS[op_id]  # already done — don't duplicate
    fulfillment["email_results"] = email_results
    fulfillment["steps"] = _steps(fulfillment)
    _FULFILLMENTS[op_id] = fulfillment
    return fulfillment


def list_fulfillments() -> list[dict]:
    return list(_FULFILLMENTS.values())


def get_fulfillment(operation_id: str) -> dict | None:
    return _FULFILLMENTS.get(operation_id)


# ---- email builders ---------------------------------------------------------

def _money(minor) -> str:
    return "Rs " + f"{(minor or 0) / 100:,.0f}"


def _purchase_order_email(supplier: dict, po: dict, plan: dict) -> dict:
    to = supplier.get("email") or config.DEFAULT_SUPPLIER_EMAIL
    deadline = (po.get("delivery_latest") or "")[:10]
    subject = f"Urgent Purchase Order: {po['qty']} x {po['sku']} by {deadline}"
    body = (
        f"Dear {po['supplier_name']},\n\n"
        f"Please confirm the following emergency replenishment order:\n\n"
        f"  Product    : {po['sku']}\n"
        f"  Quantity   : {po['qty']} units\n"
        f"  Deliver to : {po['deliver_to_location_id']}\n"
        f"  Unit price : {_money(po.get('unit_price_minor'))}\n"
        f"  Required by: {deadline}\n"
        f"  Our ref    : {po.get('reservation_ref')}\n\n"
        f"This covers a shortage caused by a transit disruption. Please reply to "
        f"confirm availability and dispatch.\n\n"
        f"Regards,\nSignalBridge Operations"
    )
    return {"kind": "purchase_order", "to": to, "subject": subject, "body": body}


def _internal_transfer_email(transfer: dict, plan: dict) -> dict:
    subject = (
        f"Stock transfer request: {transfer['qty']} x {transfer['sku']} "
        f"{transfer['from_location_id']} -> {transfer['to_location_id']}"
    )
    body = (
        f"Hello {transfer['from_location_id']} team,\n\n"
        f"Please dispatch the following internal transfer to cover a shortage:\n\n"
        f"  Product : {transfer['sku']}\n"
        f"  Quantity: {transfer['qty']} units\n"
        f"  From    : {transfer['from_location_id']}\n"
        f"  To      : {transfer['to_location_id']}\n\n"
        f"Please confirm pick and dispatch today.\n\n"
        f"Regards,\nSignalBridge Operations"
    )
    return {"kind": "internal_transfer", "to": config.OPS_EMAIL, "subject": subject, "body": body}


def _steps(fulfillment: dict) -> list[dict]:
    """A simple timeline the UI can show."""
    has_transfer = any(a["type"] == "internal_transfer" for a in fulfillment["actions"])
    has_po = any(a["type"] == "purchase_order" for a in fulfillment["actions"])
    sent = sum(1 for r in fulfillment.get("email_results", []) if r.get("sent"))
    return [
        {"label": "Plan approved", "done": True},
        {"label": "Replacement stock reserved", "done": True},
        {"label": "Internal transfer requested", "done": has_transfer},
        {"label": "Purchase order emailed to supplier", "done": has_po},
        {"label": f"Notifications sent ({sent})", "done": sent > 0},
        {"label": "Order marked covered by recovery", "done": True},
        {"label": "Awaiting supplier / delivery confirmation", "done": False},
    ]
