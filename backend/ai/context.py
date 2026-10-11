"""Builds the full business context we hand to Gemini for Q&A.

The recovery plan alone is not enough to answer questions like "what is my loss
in margin?" — that needs the product's cost and price, the customers affected,
the shipment that was delayed, and the disruption itself. This module gathers
all of it from the store so Gemini can answer grounded in real facts.
"""
from __future__ import annotations

from ..domain import network as network_mod


def build_qa_context(store, plan: dict) -> dict:
    """Return a rich, self-describing context dict for one recovery plan."""
    sku = plan.get("sku")
    destination = plan.get("location_id")

    products = {p["sku"]: p for p in store.list("products")}
    locations = {l["location_id"]: l for l in store.list("locations")}
    partners = {p["partner_id"]: p for p in store.list("partners")}

    product = products.get(sku, {})
    unit_price = int(product.get("unit_price_minor") or 0)
    unit_cost = int(product.get("unit_cost_minor") or 0)

    # --- orders at risk, with the customer behind each one ---
    orders = []
    for line in store.list("order_lines"):
        if line.get("sku") != sku or line.get("location_id") != destination:
            continue
        if line.get("status") != "open":
            continue
        customer = partners.get(line.get("customer_id"), {})
        service = customer.get("service_level") or {}
        orders.append({
            "line_id": line.get("line_id"),
            "customer_name": customer.get("name", line.get("customer_id")),
            "customer_tier": service.get("tier", "standard"),
            "quantity": line.get("quantity"),
            "due_at": line.get("due_at"),
            "late_penalty_minor": service.get("penalty_per_late_order_minor", 0),
            "otif_target_pct": service.get("otif_target_pct"),
        })

    # --- shipments carrying this SKU to this destination ---
    shipments = []
    for shipment in store.list("shipments"):
        if shipment.get("destination_location_id") != destination:
            continue
        qty = sum(i["quantity"] for i in shipment.get("items", []) if i.get("sku") == sku)
        if not qty:
            continue
        shipments.append({
            "shipment_id": shipment.get("shipment_id"),
            "units_of_this_sku": qty,
            "carrier_id": shipment.get("carrier_id"),
            "originally_expected_at": shipment.get("expected_arrival_at"),
            "now_assumed_to_arrive_at": shipment.get("assumed_arrival_at"),
            "delay_state": shipment.get("delay_state"),
            "health": network_mod.shipment_health(shipment),
            "why_at_risk": shipment.get("risk_reason"),
        })

    # --- the disruption signals themselves ---
    events = []
    for event in store.list("events"):
        where = event.get("where") or {}
        why = event.get("why") or {}
        when = event.get("when") or {}
        events.append({
            "event_type": why.get("event_type"),
            "location": (locations.get(where.get("location_id")) or {}).get("name", where.get("location_id")),
            "effective_from": when.get("effective_from"),
            "effective_until": when.get("effective_until"),
            "confidence": event.get("confidence"),
            "verification_status": event.get("verification_status"),
            "is_assumption": event.get("is_assumption"),
            "matched_shipment_ids": event.get("matched_shipment_ids"),
        })

    # --- stock of this SKU everywhere in our network ---
    stock = []
    for balance in store.list("stock_balances"):
        if balance.get("sku") != sku:
            continue
        location = locations.get(balance.get("location_id"), {})
        on_hand = int(balance.get("on_hand_qty", 0))
        reserved = int(balance.get("reserved_qty", 0))
        stock.append({
            "location_id": balance.get("location_id"),
            "location_name": location.get("name"),
            "location_type": location.get("type"),
            "on_hand_qty": on_hand,
            "reserved_qty": reserved,
            "free_to_use_qty": on_hand - reserved,
            "incoming_qty": balance.get("incoming_qty", 0),
            "is_the_destination": balance.get("location_id") == destination,
        })

    # --- every supplier offer for this SKU, named ---
    offers = []
    for offer in store.list("supplier_offers"):
        if offer.get("sku") != sku:
            continue
        supplier = partners.get(offer.get("supplier_id"), {})
        offers.append({
            "offer_id": offer.get("offer_id"),
            "supplier_name": supplier.get("name", offer.get("supplier_id")),
            "available_qty": offer.get("available_qty"),
            "unit_price_minor": offer.get("unit_price_minor"),
            "shipping_minor": offer.get("shipping_minor"),
            "delivery_latest": offer.get("delivery_latest"),
            "expires_at": offer.get("expires_at"),
            "deliver_to": offer.get("deliver_to_location_id"),
            "ships_from": offer.get("ships_from"),
            "mode": offer.get("mode"),
            "route": offer.get("route"),
            "note": offer.get("note"),
        })

    return {
        "product": {
            "sku": sku,
            "name": product.get("name"),
            "category": product.get("category"),
            "our_cost_per_unit_minor": unit_cost,
            "our_selling_price_per_unit_minor": unit_price,
            "normal_gross_margin_per_unit_minor": unit_price - unit_cost,
            "perishable": product.get("perishable"),
            "shelf_life_days": product.get("shelf_life_days"),
        },
        "destination_location": {
            "location_id": destination,
            "name": (locations.get(destination) or {}).get("name"),
            "type": (locations.get(destination) or {}).get("type"),
        },
        "disruption_events": events,
        "shipments_carrying_this_sku": shipments,
        "customer_orders_at_risk": orders,
        "stock_across_our_network": stock,
        "all_supplier_offers_for_this_sku": offers,
        "recovery_plan": plan,
        "field_notes": {
            "money": "Every field ending in _minor is an integer in paise. Divide by 100 for rupees.",
            "margin": "Normal gross margin per unit = selling price - our cost. Emergency "
                      "replacement units are bought at the offer's unit_price_minor plus "
                      "shipping, so margin on those units is lower than normal.",
            "coverage": "A recovered order is 'covered by a plan', not yet physically delivered.",
        },
    }
