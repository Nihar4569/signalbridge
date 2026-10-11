"""Supplier offers must not route through a chokepoint that is delaying us now."""
from backend.core.store import LocalStore
from backend.domain import planner


def _store():
    store = LocalStore()
    store.upsert("locations", "SEA-HORMUZ", {
        "location_id": "SEA-HORMUZ", "name": "Strait of Hormuz", "type": "sea_waypoint", "lat": 26.55, "lon": 56.45,
    })
    store.upsert("lanes", "ROUTE-ET-MUM", {
        "lane_id": "ROUTE-ET-MUM", "points": [{"name": "Strait of Hormuz", "lat": 26.55, "lon": 56.45, "location_id": "SEA-HORMUZ"}],
    })
    shipment = store.get("shipments", "shipment_id", "SHP-001")
    store.upsert("shipments", "SHP-001", {**shipment, "risk_zone": "risk"})
    # Cheapest offer, but it sails through Hormuz.
    store.upsert("supplier_offers", "OFFER-HZ", {
        "offer_id": "OFFER-HZ", "supplier_id": "SUP-X", "sku": "JACKET-BLUE-M", "deliver_to_location_id": "WH-MUM",
        "available_qty": 500, "unit_price_minor": 100, "shipping_minor": 0,
        "delivery_latest": "2026-10-14T12:00:00Z", "route_location_ids": ["SEA-HORMUZ"],
    })
    return store


def _option(plan, offer_id):
    return next(o for o in plan["supplier_options"] if o["offer_id"] == offer_id)


def test_offer_through_disrupted_chokepoint_is_rejected():
    store = _store()
    store.upsert("signals", "SIG-NEWS-1", {
        "signal_id": "SIG-NEWS-1", "source": "google-news", "title": "Tanker attacked in Strait of Hormuz",
        "published_at": "2099-01-01T00:00:00Z", "payload": {"location_id": "SEA-HORMUZ"},
    })
    plan = planner.build_plan(store, sku="JACKET-BLUE-M", location_id="WH-MUM")
    hz = _option(plan, "OFFER-HZ")
    assert not hz["feasible"] and "Strait of Hormuz" in hz["reason"]
    assert plan["selected_offer_id"] != "OFFER-HZ"


def test_calm_chokepoint_is_allowed():
    plan = planner.build_plan(_store(), sku="JACKET-BLUE-M", location_id="WH-MUM")
    assert plan["selected_offer_id"] == "OFFER-HZ"  # no live signal there, so cheapest wins


def test_offers_for_other_warehouses_are_ignored():
    store = _store()
    store.upsert("supplier_offers", "OFFER-HZ", {**store.get_by_id("supplier_offers", "OFFER-HZ"), "deliver_to_location_id": "WH-DEL"})
    plan = planner.build_plan(store, sku="JACKET-BLUE-M", location_id="WH-MUM")
    assert all(o["offer_id"] != "OFFER-HZ" for o in plan["supplier_options"])
