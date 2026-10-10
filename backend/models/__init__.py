"""Data models and Firestore document-id helpers.

See docs/schema.md for the full collection design.
"""
from __future__ import annotations

from .collections import (
    COLLECTION_MODELS,
    Allocation,
    Event,
    Exposure,
    Location,
    Operation,
    OrderLine,
    Partner,
    Plan,
    Product,
    Shipment,
    Signal,
    StockBalance,
    StockMovement,
    SupplierOffer,
    parse_doc,
)
from .ids import (
    SEED_COLLECTIONS,
    WRITE_COLLECTIONS,
    doc_id_for,
    stock_balance_id,
    tenant_collection_path,
)

__all__ = [
    "COLLECTION_MODELS",
    "SEED_COLLECTIONS",
    "WRITE_COLLECTIONS",
    "Allocation",
    "Event",
    "Exposure",
    "Location",
    "Operation",
    "OrderLine",
    "Partner",
    "Plan",
    "Product",
    "Shipment",
    "Signal",
    "StockBalance",
    "StockMovement",
    "SupplierOffer",
    "doc_id_for",
    "parse_doc",
    "stock_balance_id",
    "tenant_collection_path",
]
