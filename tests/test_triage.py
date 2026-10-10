"""Phase 2 — stored signals set shipment risk_zone and write exposures.

Uses the bundled fixtures (SHP-001, JACKET-BLUE-M @ WH-MUM) plus signals
we insert in memory. No network.
"""
from backend.core.store import LocalStore
from backend.domain import triage

PORT = {
    "location_id": "IN-JNPA",
    "name": "Nhava Sheva port",
    "type": "port",
    "active": True,
}


def _news(signal_id: str, location_id: str, *, event_type: str | None, title: str) -> dict:
    return {
        "signal_id": signal_id,
        "source": "gdelt",
        "title": title,
        "fetched_at": "2026-10-11T00:00:00Z",
        "status": "new",
        "payload": {"location_id": location_id, "event_type": event_type},
    }


def _weather(location_id: str, risk: str) -> dict:
    return {
        "signal_id": f"SIG-WEATHER-{location_id}",
        "source": "open-meteo",
        "title": f"Weather risk at {location_id}: {risk}",
        "fetched_at": "2026-10-11T00:00:00Z",
        "status": "processed",
        "payload": {"location_id": location_id, "risk": risk},
    }


def test_port_suspension_flips_shipment_and_writes_shortage():
    store = LocalStore()
    signal = _news(
        "SIG-TEST-JNPA",
        "IN-JNPA",
        event_type="port_suspension",
        title="Operations suspended at Nhava Sheva",
    )
    store.upsert("signals", signal["signal_id"], signal)

    rows = triage.run_triage(store)

    shipment = store.get("shipments", "shipment_id", "SHP-001")
    assert shipment["risk_zone"] == "risk"
    assert shipment["risk_reason"] == "port_suspension@IN-JNPA"

    exposure = store.get("exposures", "exposure_id", "EXP-JACKET-BLUE-M__WH-MUM")
    assert exposure["shortage_qty"] == 80
    assert exposure["risk_zone"] == "risk"
    assert exposure["triage_decision"] == "actionable"
    assert rows == [exposure]


def test_unrelated_signal_does_not_flip_the_shipment():
    store = LocalStore()
    signal = _news(
        "SIG-TEST-DEL",
        "WH-DEL",
        event_type="warehouse_strike",
        title="Strike shuts the Delhi distribution centre",
    )
    store.upsert("signals", signal["signal_id"], signal)

    triage.run_triage(store)

    shipment = store.get("shipments", "shipment_id", "SHP-001")
    assert shipment["risk_zone"] == "safe"
    exposure = store.get("exposures", "exposure_id", "EXP-JACKET-BLUE-M__WH-MUM")
    assert exposure["shortage_qty"] == 0
    assert exposure["risk_zone"] == "safe"
    assert exposure["triage_decision"] == "ignored"


def test_low_weather_stays_safe_and_high_weather_flips_risk():
    store = LocalStore()
    low = _weather("IN-JNPA", "low")
    store.upsert("signals", low["signal_id"], low)
    triage.run_triage(store)
    assert store.get("shipments", "shipment_id", "SHP-001")["risk_zone"] == "safe"

    high = _weather("IN-JNPA", "high")
    store.upsert("signals", high["signal_id"], high)
    triage.run_triage(store)
    shipment = store.get("shipments", "shipment_id", "SHP-001")
    assert shipment["risk_zone"] == "risk"
    assert shipment["risk_reason"] == "high@IN-JNPA"


def test_clearing_the_signal_returns_the_shipment_to_safe():
    store = LocalStore()
    signal = _news(
        "SIG-TEST-JNPA",
        "IN-JNPA",
        event_type="port_suspension",
        title="Operations suspended at Nhava Sheva",
    )
    store.upsert("signals", signal["signal_id"], signal)
    triage.run_triage(store)
    assert store.get("shipments", "shipment_id", "SHP-001")["risk_zone"] == "risk"

    store.delete("signals", signal["signal_id"])
    triage.run_triage(store)

    shipment = store.get("shipments", "shipment_id", "SHP-001")
    assert shipment["risk_zone"] == "safe"
    assert shipment["risk_reason"] is None
    exposure = store.get("exposures", "exposure_id", "EXP-JACKET-BLUE-M__WH-MUM")
    assert exposure["shortage_qty"] == 0
    assert exposure["triage_decision"] == "ignored"


def test_seeded_assumed_delayed_flag_is_cleared():
    store = LocalStore()
    shipment = dict(store.get("shipments", "shipment_id", "SHP-001"))
    shipment["delay_state"] = "assumed_delayed"
    store.upsert("shipments", shipment["shipment_id"], shipment)

    triage.run_triage(store)

    saved = store.get("shipments", "shipment_id", "SHP-001")
    assert saved["delay_state"] is None
    assert saved["risk_zone"] == "safe"
    exposure = store.get("exposures", "exposure_id", "EXP-JACKET-BLUE-M__WH-MUM")
    assert exposure["shortage_qty"] == 0


def test_gemini_judgment_overrides_keyword_overlap():
    """A model can call risk on a shipment the keywords would miss, and can
    refuse a headline the keywords would accept."""
    store = LocalStore()
    signal = _news(
        "SIG-TEST-JNPA",
        "IN-JNPA",
        event_type="port_suspension",
        title="Operations suspended at Nhava Sheva",
    )
    store.upsert("signals", signal["signal_id"], signal)

    triage.run_triage(
        store,
        judgments=[
            {
                "shipment_id": "SHP-001",
                "risk": False,
                "reason": "The headline is about a drill, not a real closure.",
            }
        ],
    )
    assert store.get("shipments", "shipment_id", "SHP-001")["risk_zone"] == "safe"

    triage.run_triage(
        store,
        judgments=[
            {
                "shipment_id": "SHP-001",
                "risk": True,
                "reason": "A cyclone may cross this lane before the ship docks.",
            }
        ],
    )
    saved = store.get("shipments", "shipment_id", "SHP-001")
    assert saved["risk_zone"] == "risk"
    assert "cyclone" in saved["risk_reason"]


def test_headline_keyword_matches_without_an_event_type():
    shipment = {
        "shipment_id": "SHP-001",
        "destination_location_id": "WH-MUM",
        "status": "in_transit",
        "items": [{"sku": "JACKET-BLUE-M", "quantity": 500}],
    }
    signal = _news(
        "SIG-HEADLINE",
        "IN-JNPA",
        event_type=None,
        title="Terminal operations suspended after the storm",
    )
    dest = {"location_id": "WH-MUM", "country": "IN", "type": "dc"}
    port = dict(PORT, country="IN")
    assert triage.match_signal_to_shipment(signal, shipment, port, dest) is True


def test_mexico_port_weather_does_not_flag_the_mumbai_shipment():
    shipment = {
        "shipment_id": "SHP-001",
        "destination_location_id": "WH-MUM",
        "status": "in_transit",
        "items": [{"sku": "JACKET-BLUE-M", "quantity": 500}],
    }
    signal = _weather("MX-ZLO", "high")
    mexico = {"location_id": "MX-ZLO", "type": "port", "country": "MX", "active": True}
    mumbai = {"location_id": "WH-MUM", "type": "dc", "country": "IN"}
    assert triage.match_signal_to_shipment(signal, shipment, mexico, mumbai) is False


def test_rerun_overwrites_the_same_exposure_id():
    store = LocalStore()
    signal = _news(
        "SIG-TEST-JNPA",
        "IN-JNPA",
        event_type="port_suspension",
        title="Operations suspended at Nhava Sheva",
    )
    store.upsert("signals", signal["signal_id"], signal)
    triage.run_triage(store)
    triage.run_triage(store)
    assert len(store.list("exposures")) == 1
