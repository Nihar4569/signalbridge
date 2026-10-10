"""Models, document ids, and LocalStore write overlay."""
from __future__ import annotations

from backend.adapters.supplier import SupplierSimulator
from backend.core.store import LocalStore
from backend.domain import planner as planner_mod
from backend.domain import reservations as reservations_mod
from backend.models import (
    Product,
    doc_id_for,
    parse_doc,
    stock_balance_id,
)


def test_doc_ids_match_schema():
    assert doc_id_for("products", {"sku": "JACKET-BLUE-M"}) == "JACKET-BLUE-M"
    assert doc_id_for("locations", {"location_id": "WH-MUM"}) == "WH-MUM"
    assert (
        doc_id_for(
            "stock_balances",
            {"location_id": "WH-MUM", "sku": "JACKET-BLUE-M"},
        )
        == "WH-MUM__JACKET-BLUE-M"
    )
    assert stock_balance_id("WH-MUM", "JACKET-BLUE-M") == "WH-MUM__JACKET-BLUE-M"
    assert doc_id_for("order_lines", {"line_id": "LINE-001"}) == "LINE-001"
    assert doc_id_for("shipments", {"shipment_id": "SHP-001"}) == "SHP-001"
    assert doc_id_for("supplier_offers", {"offer_id": "OFFER-A"}) == "OFFER-A"
    assert doc_id_for("partners", {"partner_id": "CUST-ACME"}) == "CUST-ACME"
    assert doc_id_for("events", {"event_id": "EVT-0007"}) == "EVT-0007"


def test_parse_fixture_product():
    store = LocalStore()
    raw = store.get("products", "sku", "JACKET-BLUE-M")
    assert raw is not None
    doc = parse_doc("products", raw)
    model = Product.model_validate(doc)
    assert model.sku == "JACKET-BLUE-M"
    assert model.unit_price_minor == 249900
    assert model.currency == "INR"


def test_local_store_validates_all_seed_collections():
    store = LocalStore()
    from backend.models import SEED_COLLECTIONS

    for name in SEED_COLLECTIONS:
        for raw in store._load_file(name):
            parse_doc(name, raw)  # must not raise
            doc_id_for(name, raw)


def test_reserve_persists_operation_on_store():
    store = LocalStore()
    plan = planner_mod.build_plan(store, sku="JACKET-BLUE-M", location_id="WH-MUM")
    assert plan["status"] == "awaiting_approval"

    receipt = reservations_mod.reserve(
        plan=plan, supplier=SupplierSimulator(), store=store
    )
    assert receipt["status"] == "succeeded"
    assert receipt["qty"] == plan["recovered_qty"]

    ops = store.list("operations")
    assert len(ops) == 1
    assert ops[0]["status"] == "succeeded"
    assert ops[0]["idempotency_key"] == receipt["idempotency_key"]

    # Idempotent second call
    again = reservations_mod.reserve(
        plan=plan, supplier=SupplierSimulator(), store=store
    )
    assert again["idempotency_key"] == receipt["idempotency_key"]
    assert len(store.list("operations")) == 1
