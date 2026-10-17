"""Triage safety net: a confirmed severe disruption on the route overrides the LLM.

This keeps the demo stable — the chokepoint story never silently flips just
because Gemini's per-run judgment wavered.
"""
from datetime import datetime, timezone

from backend.core.store import LocalStore
from backend.domain import triage


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def test_severe_route_signal_overrides_gemini_safe():
    store = LocalStore()
    store.upsert("locations", "SEA-X", {"location_id": "SEA-X", "name": "Test Strait",
                                        "type": "sea_waypoint", "lat": 1.0, "lon": 1.0})
    store.upsert("lanes", "LANE-X", {"lane_id": "LANE-X",
                                     "points": [{"name": "Test Strait", "lat": 1.0, "lon": 1.0, "location_id": "SEA-X"}]})
    sh = store.get("shipments", "shipment_id", "SHP-001")
    store.upsert("shipments", "SHP-001", {**sh, "lane_id": "LANE-X"})
    store.upsert("signals", "SIG-X", {"signal_id": "SIG-X", "source": "google-news",
                                      "title": "Cargo ship attacked in the Test Strait",
                                      "published_at": _now(), "payload": {"location_id": "SEA-X"}})

    # Gemini (wrongly) says SHP-001 is safe — the net must still flag it.
    triage.run_triage(store, judgments=[{"shipment_id": "SHP-001", "risk": False, "reason": ""}])
    saved = store.get("shipments", "shipment_id", "SHP-001")
    assert saved["risk_zone"] == "risk"
    assert "Confirmed disruption on route" in (saved["risk_reason"] or "")


def test_gemini_safe_respected_when_route_is_calm():
    store = LocalStore()
    store.upsert("locations", "LOC-CALM", {"location_id": "LOC-CALM", "name": "Calm Port",
                                           "type": "port", "lat": 5.0, "lon": 5.0})
    store.upsert("lanes", "LANE-CALM", {"lane_id": "LANE-CALM",
                                        "points": [{"name": "Calm", "lat": 5.0, "lon": 5.0, "location_id": "LOC-CALM"}]})
    store.upsert("shipments", "SHP-CALM", {"shipment_id": "SHP-CALM", "status": "in_transit",
                                           "lane_id": "LANE-CALM", "destination_location_id": "LOC-CALM",
                                           "items": [{"sku": "JACKET-BLUE-M", "quantity": 10}], "risk_zone": "safe"})

    triage.run_triage(store, judgments=[{"shipment_id": "SHP-CALM", "risk": False, "reason": ""}])
    assert store.get("shipments", "shipment_id", "SHP-CALM")["risk_zone"] == "safe"


def test_mild_news_does_not_trip_the_net():
    store = LocalStore()
    store.upsert("locations", "SEA-MILD", {"location_id": "SEA-MILD", "name": "Mild Sea",
                                           "type": "sea_waypoint", "lat": 2.0, "lon": 2.0})
    store.upsert("lanes", "LANE-MILD", {"lane_id": "LANE-MILD",
                                        "points": [{"name": "Mild Sea", "lat": 2.0, "lon": 2.0, "location_id": "SEA-MILD"}]})
    store.upsert("shipments", "SHP-MILD", {"shipment_id": "SHP-MILD", "status": "in_transit",
                                           "lane_id": "LANE-MILD", "destination_location_id": "SEA-MILD",
                                           "items": [{"sku": "JACKET-BLUE-M", "quantity": 10}], "risk_zone": "safe"})
    # "congestion" is a disruption word but not in the SEVERE set — must not override.
    store.upsert("signals", "SIG-MILD", {"signal_id": "SIG-MILD", "source": "google-news",
                                         "title": "Minor congestion reported near Mild Sea",
                                         "published_at": _now(), "payload": {"location_id": "SEA-MILD"}})
    triage.run_triage(store, judgments=[{"shipment_id": "SHP-MILD", "risk": False, "reason": ""}])
    assert store.get("shipments", "shipment_id", "SHP-MILD")["risk_zone"] == "safe"
