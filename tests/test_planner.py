"""Planner follows triage's risk_zone. A seeded delay flag does not create a plan."""
from backend.core.store import LocalStore
from backend.domain import planner as planner_mod


def _mark_at_risk(store: LocalStore) -> None:
    shipment = dict(store.get("shipments", "shipment_id", "SHP-001"))
    shipment["risk_zone"] = "risk"
    shipment["risk_reason"] = "port_suspension@IN-JNPA"
    store.upsert("shipments", "SHP-001", shipment)


def test_no_plan_when_triage_has_not_marked_risk():
    store = LocalStore()
    plan = planner_mod.build_plan(store, sku="JACKET-BLUE-M", location_id="WH-MUM")
    assert plan["status"] == "no_action_needed"
    assert plan["exposure"]["shortage_qty"] == 0


def test_plan_uses_internal_then_supplier_once_shipment_is_at_risk():
    store = LocalStore()
    _mark_at_risk(store)
    plan = planner_mod.build_plan(store, sku="JACKET-BLUE-M", location_id="WH-MUM")
    assert plan["status"] == "awaiting_approval"
    assert plan["exposure"]["shortage_qty"] == 80
    # 20 free units exist in the Pune dark store.
    assert plan["internal_used_qty"] == 20
    # The remaining 60 come from a feasible supplier offer.
    assert plan["selected_offer_id"] in {"OFFER-A", "OFFER-B", "OFFER-C"}
    assert plan["recovered_qty"] == 80
    pune = next(o for o in plan["internal_options"] if o["location_id"] == "DS-PUN-01")
    # Mumbai DC to the Pune dark store is a bit over 100 km.
    assert 100 < pune["distance_km"] < 150


def test_plan_picks_a_feasible_offer_before_the_deadline():
    store = LocalStore()
    _mark_at_risk(store)
    plan = planner_mod.build_plan(store, sku="JACKET-BLUE-M", location_id="WH-MUM")
    # OFFER-C arrives 2026-10-20, after the 16 Oct deadline, so must be rejected.
    assert plan["selected_offer_id"] != "OFFER-C"
