"""Pydantic shapes for every collection in docs/schema.md / fixtures/.

Business logic still works on plain dicts (simpler + tested). These models:
  - document the contract
  - validate at the edges (seed script, optional API)
  - convert to/from Firestore-friendly dicts
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    def to_firestore(self) -> dict[str, Any]:
        """JSON-serialisable dict (no None-stripping — nulls are intentional)."""
        return self.model_dump(mode="json")


# --- Layer 1: master data -----------------------------------------------------


class Product(_Model):
    sku: str
    gtin: str | None = None
    name: str
    category: str | None = None
    uom: str = "EA"
    unit_cost_minor: int = 0
    unit_price_minor: int = 0
    currency: str = "INR"
    substitute_skus: list[str] = Field(default_factory=list)
    perishable: bool = False
    shelf_life_days: int | None = None
    temp_range_c: list[float] | None = None
    version: int = 1


class Location(_Model):
    location_id: str
    gln: str | None = None
    name: str
    type: Literal["dc", "dark_store", "store", "port", "supplier_site", "sea_waypoint"]
    unlocode: str | None = None
    country: str | None = None
    lat: float | None = None
    lon: float | None = None
    aliases: list[str] = Field(default_factory=list)
    news_query: str | None = None
    can_transfer_to: list[str] = Field(default_factory=list)
    active: bool = True


class ServiceLevel(_Model):
    tier: str | None = None
    otif_target_pct: float | None = None
    penalty_per_late_order_minor: int = 0
    sla_hours: int | None = None


class Partner(_Model):
    partner_id: str
    name: str
    roles: list[str] = Field(default_factory=list)
    gln: str | None = None
    service_level: ServiceLevel | None = None
    email: str | None = None
    country: str | None = None
    city: str | None = None
    active: bool = True


class Lane(_Model):
    lane_id: str
    name: str | None = None
    origin_location_id: str | None = None
    destination_location_id: str | None = None
    points: list[dict[str, Any]] = Field(default_factory=list)
    legs: list[dict[str, Any]] = Field(default_factory=list)


# --- Layer 2: inventory -------------------------------------------------------


class StockBalance(_Model):
    sku: str
    location_id: str
    on_hand_qty: int = 0
    reserved_qty: int = 0
    incoming_qty: int = 0
    outgoing_qty: int = 0
    updated_at: str | None = None
    version: int = 1

    @property
    def free_to_use(self) -> int:
        return self.on_hand_qty - self.reserved_qty


class StockMovement(_Model):
    movement_id: str
    sku: str
    location_id: str
    qty_delta: int
    bucket: Literal["on_hand", "reserved", "incoming", "outgoing"]
    reason: str
    ref_type: str | None = None
    ref_id: str | None = None
    occurred_at: str
    actor: str = "system"


# --- Layer 3: commitments -----------------------------------------------------


class OrderLine(_Model):
    line_id: str
    order_id: str
    customer_id: str | None = None
    sku: str
    location_id: str
    quantity: int
    due_at: str
    status: str = "open"
    on_hand_allocated_qty: int = 0
    recovery_coverage_qty: int = 0
    priority_score: float | None = None
    version: int = 1


class ShipmentItem(_Model):
    sku: str
    quantity: int


class Shipment(_Model):
    shipment_id: str
    lane_id: str | None = None
    destination_location_id: str
    status: str = "in_transit"
    items: list[ShipmentItem] = Field(default_factory=list)
    departed_at: str | None = None
    expected_arrival_at: str | None = None
    assumed_arrival_at: str | None = None
    confirmed_arrival_at: str | None = None
    delay_state: str | None = None
    carrier_id: str | None = None
    updated_at: str | None = None
    # Set by triage (domain/triage.py), never guessed by an LLM. Defaults
    # "safe"; flips to "risk" only when a matched signal touches this
    # shipment's destination (or lane, once lanes carry waypoints — see
    # docs/productiongrade.md §2.6).
    risk_zone: Literal["safe", "risk"] = "safe"
    risk_reason: str | None = None
    version: int = 1


class SupplierOffer(_Model):
    offer_id: str
    supplier_id: str
    sku: str
    deliver_to_location_id: str | None = None
    available_qty: int
    unit_price_minor: int
    shipping_minor: int = 0
    currency: str = "INR"
    delivery_latest: str
    expires_at: str | None = None
    ships_from: str | None = None
    mode: str | None = None  # sea | air | road | rail
    route: str | None = None
    route_location_ids: list[str] = Field(default_factory=list)
    note: str | None = None
    version: int = 1


# --- Layer 4: intelligence ----------------------------------------------------


class Signal(_Model):
    signal_id: str
    source: str
    source_url: str | None = None
    title: str | None = None
    raw_hash: str | None = None
    fetched_at: str
    published_at: str | None = None
    status: str = "new"
    ttl_at: str | None = None
    # Adapter-specific extras (weather metrics, article domain/country, ...).
    # A dict here keeps Signal generic across sources instead of growing a
    # new optional field per adapter.
    payload: dict[str, Any] = Field(default_factory=dict)


class EventWhat(_Model):
    subject_type: str
    subject_id: str


class EventWhen(_Model):
    occurred_at: str | None = None
    effective_from: str | None = None
    effective_until: str | None = None
    recorded_at: str | None = None


class EventWhere(_Model):
    location_id: str | None = None
    unlocode: str | None = None


class EventWhy(_Model):
    event_type: str | None = None
    biz_step: str | None = None
    disposition: str | None = None


class Event(_Model):
    event_id: str
    signal_ids: list[str] = Field(default_factory=list)
    what: EventWhat | None = None
    when: EventWhen | None = None
    where: EventWhere | None = None
    why: EventWhy | None = None
    confidence: float | None = None
    verification_status: str | None = None
    is_assumption: bool = False
    matched_shipment_ids: list[str] = Field(default_factory=list)
    superseded_by: str | None = None
    version: int = 1


class Exposure(_Model):
    exposure_id: str
    event_id: str | None = None
    shipment_id: str | None = None
    sku: str
    location_id: str
    deadline_at: str
    supply_by_deadline: int
    demand_by_deadline: int
    shortage_qty: int
    affected_order_line_ids: list[str] = Field(default_factory=list)
    revenue_at_risk_minor: int = 0
    penalty_at_risk_minor: int = 0
    severity: str | None = None
    # Business-impact flag: "safe" unless this pair has a real shortage
    # caused by a matched signal. A shipment can be risk_zone="risk" while
    # its exposure stays "safe" (enough buffer stock that nobody notices).
    risk_zone: Literal["safe", "risk"] = "safe"
    triage_decision: str = "actionable"
    computed_at: str | None = None


class PlanApproval(_Model):
    tier: str
    threshold_minor: int | None = None
    required_role: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    decision: str | None = None


class Plan(_Model):
    plan_id: str
    exposure_id: str | None = None
    sku: str
    location_id: str
    plan_type: str = "replacement_purchase"
    status: str = "awaiting_approval"
    options: list[dict[str, Any]] = Field(default_factory=list)
    selected_option_rank: int | None = None
    selected_offer_id: str | None = None
    internal_used_qty: int = 0
    recovered_qty: int = 0
    margin_check: dict[str, Any] = Field(default_factory=dict)
    surplus_forecast: dict[str, Any] = Field(default_factory=dict)
    approval: PlanApproval | dict[str, Any] | None = None
    narrative: str | None = None
    version: int = 1


class OperationReservation(_Model):
    supplier_ref: str | None = None
    qty: int = 0
    expires_at: str | None = None
    verified_at: str | None = None


class Operation(_Model):
    operation_id: str
    plan_id: str | None = None
    plan_version: int = 1
    idempotency_key: str
    status: str = "succeeded"
    attempts: int = 1
    reservation: OperationReservation | dict[str, Any] | None = None
    last_error: str | None = None
    updated_at: str | None = None
    offer_id: str | None = None
    qty: int | None = None


class AllocationClaim(_Model):
    operation_id: str
    qty: int
    state: str = "confirmed"
    claimed_at: str | None = None


class Allocation(_Model):
    line_id: str
    claims: list[AllocationClaim] = Field(default_factory=list)
    version: int = 1


# Map collection name → model (for seed validation).
COLLECTION_MODELS: dict[str, type[_Model]] = {
    "products": Product,
    "locations": Location,
    "partners": Partner,
    "lanes": Lane,
    "stock_balances": StockBalance,
    "stock_movements": StockMovement,
    "order_lines": OrderLine,
    "shipments": Shipment,
    "supplier_offers": SupplierOffer,
    "signals": Signal,
    "events": Event,
    "exposures": Exposure,
    "plans": Plan,
    "operations": Operation,
    "allocations": Allocation,
}


def parse_doc(collection: str, data: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw dict against the collection model; return plain dict."""
    model_cls = COLLECTION_MODELS.get(collection)
    if model_cls is None:
        return dict(data)
    return model_cls.model_validate(data).to_firestore()
