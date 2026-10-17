"""Phase 3 — a plan is built only for exposures triage marked risk."""
from backend.app.routers import incidents as incidents_router
from backend.core.store import LocalStore
from backend.domain import reservations
from backend.worker.main import run_monitoring_once


def _exposure(risk_zone: str) -> dict:
    return {
        "exposure_id": "EXP-JACKET-BLUE-M__WH-MUM",
        "sku": "JACKET-BLUE-M",
        "location_id": "WH-MUM",
        "risk_zone": risk_zone,
        "shortage_qty": 80 if risk_zone == "risk" else 0,
    }


def test_safe_exposure_does_not_build_a_plan():
    store = LocalStore()
    store.upsert("exposures", "EXP-JACKET-BLUE-M__WH-MUM", _exposure("safe"))
    assert run_monitoring_once(store) == []


def test_risk_exposure_builds_the_recovery_plan():
    store = LocalStore()
    shipment = dict(store.get("shipments", "shipment_id", "SHP-001"))
    shipment["risk_zone"] = "risk"
    store.upsert("shipments", "SHP-001", shipment)
    store.upsert("exposures", "EXP-JACKET-BLUE-M__WH-MUM", _exposure("risk"))

    plans = run_monitoring_once(store)
    assert len(plans) == 1
    assert plans[0]["status"] == "awaiting_approval"
    assert plans[0]["exposure"]["shortage_qty"] == 80
    assert plans[0]["selected_offer_id"] == "OFFER-A"


def test_approved_recovery_drops_out_of_threatened_orders():
    store = LocalStore()
    shipment = dict(store.get("shipments", "shipment_id", "SHP-001"))
    shipment["risk_zone"] = "risk"
    store.upsert("shipments", "SHP-001", shipment)

    before = incidents_router.list_incidents(store=store)
    pairs_before = {(i["sku"], i["location_id"]) for i in before["incidents"]}
    assert ("JACKET-BLUE-M", "WH-MUM") in pairs_before

    store.upsert(
        "plans",
        "PLAN-JACKET-BLUE-M-WH-MUM",
        {
            "plan_id": "PLAN-JACKET-BLUE-M-WH-MUM",
            "sku": "JACKET-BLUE-M",
            "location_id": "WH-MUM",
            "status": "approved",
        },
    )
    assert ("JACKET-BLUE-M", "WH-MUM") in reservations.recovered_pairs(store)

    after = incidents_router.list_incidents(store=store)
    pairs_after = {(i["sku"], i["location_id"]) for i in after["incidents"]}
    assert ("JACKET-BLUE-M", "WH-MUM") not in pairs_after
    assert after["count"] == before["count"] - 1
