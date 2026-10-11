"""Firestore document ids: one natural key per collection, so writes never duplicate.

Path for everything: tenants/{tenant_id}/{collection}/{doc_id}  (docs/schema.md)
"""
from __future__ import annotations

# Collections loaded from fixtures/ by scripts/seed_firestore.py.
SEED_COLLECTIONS = [
    "products",
    "locations",
    "partners",
    "lanes",
    "stock_balances",
    "order_lines",
    "shipments",
    "supplier_offers",
    "events",
]

# Collections the app writes while running.
WRITE_COLLECTIONS = ["signals", "exposures", "plans", "operations", "allocations", "stock_movements"]

ID_FIELDS = {
    "products": "sku",
    "locations": "location_id",
    "partners": "partner_id",
    "lanes": "lane_id",
    "order_lines": "line_id",
    "shipments": "shipment_id",
    "supplier_offers": "offer_id",
    "events": "event_id",
    "alerts": "alert_id",
    "signals": "signal_id",
    "exposures": "exposure_id",
    "plans": "plan_id",
    "operations": "operation_id",
    "allocations": "line_id",
    "stock_movements": "movement_id",
}


def stock_balance_id(location_id: str, sku: str) -> str:
    return f"{location_id}__{sku}"


def doc_id_for(collection: str, doc: dict) -> str:
    """The Firestore document id for this document."""
    if collection == "stock_balances":
        return stock_balance_id(doc["location_id"], doc["sku"])
    field = ID_FIELDS.get(collection)
    if field is None:
        raise ValueError(f"No id rule for collection {collection!r}")
    return str(doc[field])


def tenant_collection_path(tenant_id: str, collection: str) -> str:
    return f"tenants/{tenant_id}/{collection}"
