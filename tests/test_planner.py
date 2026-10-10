"""Tests for the planner — the end-to-end recovery plan on real fixtures."""
from backend.core.store import LocalStore
from backend.domain import planner as planner_mod

store = LocalStore()


def test_plan_uses_internal_then_supplier():
    plan = planner_mod.build_plan(store, sku="JACKET-BLUE-M", location_id="WH-MUM")
    assert plan["status"] == "awaiting_approval"
    assert plan["exposure"]["shortage_qty"] == 80
    # 20 free units exist in the Pune dark store.
    assert plan["internal_used_qty"] == 20
    # The remaining 60 come from a feasible supplier offer.
    assert plan["selected_offer_id"] in {"OFFER-A", "OFFER-B", "OFFER-C"}
    assert plan["recovered_qty"] == 80


def test_plan_picks_a_feasible_offer_before_the_deadline():
    plan = planner_mod.build_plan(store, sku="JACKET-BLUE-M", location_id="WH-MUM")
    # OFFER-C arrives 2026-10-20, after the 16 Oct deadline, so must be rejected.
    assert plan["selected_offer_id"] != "OFFER-C"
