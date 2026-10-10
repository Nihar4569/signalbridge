"""Pydantic models = the shape of our data, written down once.

These mirror the collections described in docs/schema.md. The base business
logic works on plain dicts (simpler for beginners), but these models are here so
editors can autocomplete and so we can validate data at the edges later.
"""
from __future__ import annotations

from pydantic import BaseModel


class Product(BaseModel):
    sku: str
    name: str
    uom: str = "EA"
    unit_cost_minor: int = 0
    unit_price_minor: int = 0
    currency: str = "INR"
    perishable: bool = False


class Location(BaseModel):
    location_id: str
    name: str
    type: str  # dc | dark_store | store | port | supplier_site | sea_waypoint
    country: str | None = None
    active: bool = True


class StockBalance(BaseModel):
    sku: str
    location_id: str
    on_hand_qty: int = 0
    reserved_qty: int = 0
    incoming_qty: int = 0
    outgoing_qty: int = 0

    @property
    def free_to_use(self) -> int:
        return self.on_hand_qty - self.reserved_qty


class OrderLine(BaseModel):
    line_id: str
    order_id: str
    customer_id: str | None = None
    sku: str
    location_id: str
    quantity: int
    due_at: str
    status: str = "open"


class SupplierOffer(BaseModel):
    offer_id: str
    supplier_id: str
    sku: str
    available_qty: int
    unit_price_minor: int
    shipping_minor: int = 0
    currency: str = "INR"
    delivery_latest: str
