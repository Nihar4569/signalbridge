"""Penalty must only count orders the shortage actually threatens."""
from backend.core.store import LocalStore
from backend.domain import planner


def _store():
    """One SKU, two customers: one order due at the deadline, one due later."""
    store = LocalStore()
    store.upsert("products", "WIDGET", {"sku": "WIDGET", "name": "Widget",
                                        "unit_cost_minor": 1000, "unit_price_minor": 2000})
    store.upsert("locations", "WH-A", {"location_id": "WH-A", "name": "DC A", "type": "dc"})
    store.upsert("partners", "CUST-EARLY", {"partner_id": "CUST-EARLY", "name": "Early",
                                            "service_level": {"tier": "vip", "penalty_per_late_order_minor": 100_000}})
    store.upsert("partners", "CUST-LATE", {"partner_id": "CUST-LATE", "name": "Later",
                                           "service_level": {"tier": "vip", "penalty_per_late_order_minor": 900_000}})
    store.upsert("order_lines", "L-EARLY", {"line_id": "L-EARLY", "order_id": "O1", "customer_id": "CUST-EARLY",
                                            "sku": "WIDGET", "location_id": "WH-A", "quantity": 100,
                                            "due_at": "2026-11-01T12:00:00Z", "status": "open"})
    store.upsert("order_lines", "L-LATE", {"line_id": "L-LATE", "order_id": "O2", "customer_id": "CUST-LATE",
                                           "sku": "WIDGET", "location_id": "WH-A", "quantity": 50,
                                           "due_at": "2026-12-01T12:00:00Z", "status": "open"})
    store.upsert("stock_balances", "WH-A__WIDGET", {"sku": "WIDGET", "location_id": "WH-A",
                                                    "on_hand_qty": 20, "reserved_qty": 0})
    store.upsert("supplier_offers", "OFF-1", {"offer_id": "OFF-1", "supplier_id": "S1", "sku": "WIDGET",
                                              "deliver_to_location_id": "WH-A", "available_qty": 500,
                                              "unit_price_minor": 1500, "shipping_minor": 5000,
                                              "delivery_latest": "2026-10-30T12:00:00Z"})
    return store


def test_penalty_excludes_orders_not_yet_due():
    plan = planner.build_plan(_store(), sku="WIDGET", location_id="WH-A")
    # Deadline is the earliest due date, so only L-EARLY is threatened.
    assert plan["exposure"]["demand_by_deadline"] == 100
    assert plan["margin_check"]["penalty_avoided_minor"] == 100_000  # not 1,000,000


def test_penalty_matches_the_lines_counted_in_demand():
    store = _store()
    # Move the second order inside the deadline window: now both count.
    late = store.get("order_lines", "line_id", "L-LATE")
    store.upsert("order_lines", "L-LATE", {**late, "due_at": "2026-11-01T12:00:00Z"})

    plan = planner.build_plan(store, sku="WIDGET", location_id="WH-A")
    assert plan["exposure"]["demand_by_deadline"] == 150
    assert plan["margin_check"]["penalty_avoided_minor"] == 1_000_000
