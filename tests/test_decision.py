"""Evidence contracts, safe state transitions and isolated walkthrough outcomes."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.ai import gemini
from backend.app.deps import store_dep
from backend.app.main import app
from backend.app.routers import decision_demo
from backend.core import config
from backend.core.store import LocalStore, SnapshotStore
from backend.domain import decision, exposure, planner, reservations, triage
from backend.models.decision import gemini_response_schema


def _sample(case_id="active-closure"):
    data = decision_demo._fixture()
    case = next(item for item in data["cases"] if item["case_id"] == case_id)
    clock = exposure.parse_ts(data["assessment_at"])
    store = SnapshotStore({**data["collections"], "signals": [case["signal"]]})
    evidence = decision.evidence_records(
        store.list("signals"), store.list("locations"), as_of=clock
    )
    lanes = {lane["lane_id"]: lane for lane in store.list("lanes")}
    routes = {
        shipment["shipment_id"]: decision.route_location_ids(shipment, lanes)
        for shipment in store.list("shipments")
    }
    return data, case, clock, store, evidence, routes


def _parse(payload, evidence, routes):
    return gemini._parse_judgments(
        json.dumps(payload), set(routes), evidence=evidence, shipment_locations=routes
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "missing",
        "duplicate",
        "unknown_id",
        "bad_status",
        "invented_quote",
        "unknown_source",
        "wrong_route",
        "no_citation",
    ],
)
def test_invalid_model_batches_are_rejected(mutation):
    _, case, _, _, evidence, routes = _sample()
    payload = deepcopy(case["reference"])
    rows = payload["shipments"]
    if mutation == "empty":
        payload["shipments"] = []
    elif mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif mutation == "unknown_id":
        rows[0]["shipment_id"] = "NOT-A-SHIPMENT"
    elif mutation == "bad_status":
        rows[0]["status"] = True
    elif mutation == "invented_quote":
        rows[0]["evidence"][0]["quote"] = "A fact that never appeared in the source"
    elif mutation == "unknown_source":
        rows[0]["evidence"][0]["signal_id"] = "MADE-UP-SOURCE"
    elif mutation == "wrong_route":
        rows[1]["status"] = "affected"
    elif mutation == "no_citation":
        rows[0]["evidence"] = []
    assert _parse(payload, evidence, routes) is None


def test_stale_evidence_cannot_support_a_fresh_judgment():
    _, case, _, _, evidence, routes = _sample()
    evidence[0]["current"] = False
    assert _parse(case["reference"], evidence, routes) is None


def test_unknown_status_preserves_existing_risk():
    _, case, clock, store, evidence, routes = _sample("cancelled-strike")
    shipment = store.get_by_id("shipments", "SHIP-MUM-DEMO")
    store.upsert(
        "shipments",
        shipment["shipment_id"],
        {**shipment, "risk_zone": "risk", "risk_reason": "Last known disruption"},
    )
    payload = deepcopy(case["reference"])
    payload["shipments"][0].update(
        status="unknown",
        event_status="uncertain",
        reason="Conflicting evidence",
        evidence=[],
        unresolved_fields=["Need event scope"],
    )
    rows = _parse(payload, evidence, routes)
    assert rows is not None
    # No unrelated severe floor should determine this preservation check.
    store = SnapshotStore(
        {
            "shipments": store.list("shipments"),
            "locations": store.list("locations"),
            "lanes": store.list("lanes"),
        }
    )
    triage.run_triage(store, judgments=rows, as_of=clock)
    assert store.get_by_id("shipments", "SHIP-MUM-DEMO")["risk_zone"] == "risk"


def test_missing_judgment_never_clears_risk():
    store = LocalStore()
    shipment = store.get_by_id("shipments", "SHP-001")
    store.upsert(
        "shipments",
        "SHP-001",
        {**shipment, "risk_zone": "risk", "risk_reason": "Previous valid assessment"},
    )
    triage.run_triage(store, judgments=[])
    assert store.get_by_id("shipments", "SHP-001")["risk_zone"] == "risk"


@pytest.mark.parametrize(
    "case_id,shortage,offer",
    [("active-closure", 80, "OFFER-DIRECT"), ("cancelled-strike", 0, None)],
)
def test_reference_walkthrough_uses_real_domain_engine(case_id, shortage, offer):
    result = decision_demo.run_case(case_id, decision_demo.RunBody(mode="reference"))
    assert result["mode"] == "reference" and result["synthetic"]
    assert result["assessment_state"] == "complete"
    assert result["plan"]["exposure"]["shortage_qty"] == shortage
    assert result["plan"].get("selected_offer_id") == offer
    assert all("no model call" in row["assessment"]["source"] for row in result["shipments"])
    assert result["shipments"][1]["risk_zone"] == "safe"
    source = result["brief"]["evidence"][0]
    assert source["citations"]
    assert all(citation["quote"] in source["text"] for citation in source["citations"])
    if shortage:
        assert result["plan"]["supplier_qty"] == 60
        assert result["plan"]["margin_check"]["recovery_cost_minor"] == 370000
        rejected = next(
            row
            for row in result["plan"]["supplier_options"]
            if row["offer_id"] == "OFFER-CHEAPER-SEA"
        )
        assert not rejected["feasible"] and "chokepoint" in rejected["reason"]


def test_demo_state_is_disposable_and_never_uses_operational_dependency():
    def forbidden():
        pytest.fail("The demonstration tried to read the operational store")

    app.dependency_overrides[store_dep] = forbidden
    fixture = deepcopy(decision_demo._fixture())
    try:
        with TestClient(app) as client:
            for case_id in ("active-closure", "cancelled-strike", "active-closure"):
                response = client.post(
                    f"/decision-demo/cases/{case_id}/run", json={"mode": "reference"}
                )
                assert response.status_code == 200
        assert decision_demo._fixture() == fixture
    finally:
        app.dependency_overrides.clear()


def test_gemini_failure_is_not_replaced_by_reference_answer(monkeypatch):
    monkeypatch.setattr(gemini, "judge_shipment_risk", lambda **kwargs: None)
    result = decision_demo.run_case("active-closure", decision_demo.RunBody(mode="gemini"))
    assert result["mode"] == "gemini"
    assert result["assessment_state"] == "unavailable"
    assert result["brief"]["interpretations"][0]["status"] == "unknown"
    assert all(
        row["assessment"]["source"] == "Assessment unavailable" for row in result["shipments"]
    )


def test_gemini_success_flows_into_same_validation_and_calculation(monkeypatch):
    def fake_call(*args, **kwargs):
        assert "responseJsonSchema" not in kwargs  # the helper accepts the schema separately
        assert kwargs["response_schema"]["type"] == "object"
        assert "North Passage" in args[0]
        return {"source": "gemini · test-model", "text": json.dumps(_sample()[1]["reference"])}

    monkeypatch.setattr(config, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(gemini, "_call", fake_call)
    result = decision_demo.run_case("active-closure", decision_demo.RunBody(mode="gemini"))
    assert result["assessment_state"] == "complete"
    assert result["plan"]["supplier_qty"] == 60
    assert result["brief"]["interpretations"][0]["source"] == "gemini · test-model"


def test_demo_rejects_unknown_case_or_mode():
    with TestClient(app) as client:
        assert (
            client.post("/decision-demo/cases/missing/run", json={"mode": "reference"}).status_code
            == 404
        )
        assert (
            client.post(
                "/decision-demo/cases/active-closure/run", json={"mode": "approve"}
            ).status_code
            == 422
        )


def test_quote_expiry_uses_explicit_assessment_clock():
    data, _, clock, store, evidence, routes = _sample()
    rows = _parse(_sample()[1]["reference"], evidence, routes)
    triage.run_triage(store, judgments=rows, as_of=clock)
    future = datetime(2026, 10, 19, tzinfo=timezone.utc)
    plan = planner.build_plan(store, sku=data["sku"], location_id=data["location_id"], as_of=future)
    assert plan["selected_offer_id"] is None
    assert all(
        not item["feasible"] and "expired" in item["reason"] for item in plan["supplier_options"]
    )


def test_supplier_hold_is_only_the_external_allocation():
    result = decision_demo.run_case("active-closure", decision_demo.RunBody(mode="reference"))
    plan = result["plan"]
    held = []

    class Supplier:
        def hold(self, *, offer_id, qty):
            held.append(qty)
            return {"held_qty": qty, "supplier_ref": "TEST-HOLD"}

    store = SnapshotStore({})
    receipt = reservations.reserve(plan=plan, supplier=Supplier(), store=store)
    assert held == [60] and receipt["qty"] == 60
    assert receipt["internal_qty"] == 20 and receipt["recovered_qty"] == 80
    assert store.list("operations")[0]["reservation"]["qty"] == 60
    again = reservations.reserve(plan=plan, supplier=Supplier(), store=store)
    assert again == receipt and held == [60]


def test_brief_marks_stale_or_unlinked_evidence():
    data, _, clock, store, _, _ = _sample()
    plan = planner.build_plan(store, sku=data["sku"], location_id=data["location_id"], as_of=clock)
    brief = decision.build_decision_brief(store, plan, as_of=clock)
    assert brief["interpretations"][0]["source"] == "Stored shipment flag"
    assert brief["evidence"][0]["citations"] == []
    assert any("predate" in note for note in brief["review_notes"])


def test_cancelled_notice_does_not_erase_an_independent_attack():
    _, case, clock, store, evidence, routes = _sample("cancelled-strike")
    rows = _parse(case["reference"], evidence, routes)
    store.upsert(
        "signals",
        "INDEPENDENT-ATTACK",
        {
            "signal_id": "INDEPENDENT-ATTACK",
            "source": "synthetic-notice",
            "title": "Cargo ship attacked at North Passage",
            "published_at": clock.isoformat(),
            "payload": {"location_id": "SEA-DEMO"},
        },
    )
    triage.run_triage(store, judgments=rows, as_of=clock)
    shipment = store.get_by_id("shipments", "SHIP-MUM-DEMO")
    assert shipment["risk_zone"] == "risk"
    assert shipment["risk_assessment"]["policy_override"]


def test_unavailable_attempt_keeps_previous_evidence():
    _, case, clock, store, evidence, routes = _sample()
    rows = _parse(case["reference"], evidence, routes)
    triage.run_triage(store, judgments=rows, as_of=clock)
    triage.mark_assessment_unavailable(store, as_of=clock)
    shipment = store.get_by_id("shipments", "SHIP-MUM-DEMO")
    assert shipment["risk_zone"] == "risk"
    assert shipment["risk_assessment"]["evidence"] == rows[0]["evidence"]
    assert shipment["risk_assessment"]["last_attempt_status"] == "unknown"


def test_schema_request_uses_the_verified_rest_contract(monkeypatch):
    seen = []

    class Response:
        status_code = 200

        def json(self):
            return {
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]
            }

    def post(url, **kwargs):
        seen.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(config, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(config, "GEMINI_MODELS", ["test-model"])
    monkeypatch.setattr(gemini.requests, "post", post)
    result = gemini._call(
        "Test", "fallback", json_mode=True, response_schema=gemini_response_schema()
    )
    assert result["source"].startswith("gemini")
    generation = seen[0]["generationConfig"]
    assert generation["responseFormat"]["text"]["mimeType"] == "APPLICATION_JSON"
    assert "responseMimeType" not in generation and "responseJsonSchema" not in generation
    serialized = json.dumps(generation["responseFormat"]["text"]["schema"])
    assert "minLength" not in serialized and "maxLength" not in serialized


def test_changed_source_cannot_keep_an_exact_quote_badge():
    data, case, clock, store, evidence, routes = _sample()
    rows = _parse(case["reference"], evidence, routes)
    triage.run_triage(store, judgments=rows, as_of=clock)
    signal = store.list("signals")[0]
    store.upsert(
        "signals",
        signal["signal_id"],
        {
            **signal,
            "payload": {**signal["payload"], "notice_text": "This source has been corrected."},
        },
    )
    plan = planner.build_plan(store, sku=data["sku"], location_id=data["location_id"], as_of=clock)
    brief = decision.build_decision_brief(store, plan, as_of=clock)
    assert brief["evidence"][0]["citations"] == []
    assert any("changed since" in note for note in brief["review_notes"])


def test_operational_brief_reads_saved_assessment_and_never_calls_model(monkeypatch):
    data, case, clock, store, evidence, routes = _sample()
    rows = _parse(case["reference"], evidence, routes)
    rows[0].update(source="gemini · test-model", assessed_at=clock.isoformat())
    triage.run_triage(store, judgments=rows, as_of=clock)
    monkeypatch.setattr(
        gemini, "_call", lambda *args, **kwargs: pytest.fail("Brief read initiated a model call")
    )
    app.dependency_overrides[store_dep] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.get(f"/plans/{data['sku']}/{data['location_id']}/brief")
        assert response.status_code == 200
        assert response.json()["interpretations"][0]["source"] == "gemini · test-model"
        assert response.json()["evidence"][0]["citations"]
    finally:
        app.dependency_overrides.clear()


def test_uneconomic_approval_stops_before_reservation():
    data, case, clock, store, evidence, routes = _sample()
    rows = _parse(case["reference"], evidence, routes)
    triage.run_triage(store, judgments=rows, as_of=clock)
    product = store.list("products")[0]
    store.upsert("products", product["sku"], {**product, "unit_price_minor": 1})
    app.dependency_overrides[store_dep] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.post(f"/plans/{data['sku']}/{data['location_id']}/approve")
        assert response.status_code == 409
        assert store.list("operations") == []
    finally:
        app.dependency_overrides.clear()


def test_cancellation_does_not_suppress_an_attack_even_when_the_model_cites_both():
    _, case, clock, store, evidence, routes = _sample("cancelled-strike")
    rows = _parse(case["reference"], evidence, routes)
    attack = {
        "signal_id": "SEPARATE-ATTACK",
        "source": "synthetic-notice",
        "title": "A cargo ship was attacked in North Passage; routine traffic resumed elsewhere.",
        "published_at": clock.isoformat(),
        "payload": {"location_id": "SEA-DEMO"},
    }
    store.upsert("signals", attack["signal_id"], attack)
    rows[0]["evidence"].append(
        {"signal_id": attack["signal_id"], "quote": "routine traffic resumed elsewhere"}
    )
    triage.run_triage(store, judgments=rows, as_of=clock)
    assessment = store.get_by_id("shipments", "SHIP-MUM-DEMO")["risk_assessment"]
    assert assessment["policy_evidence_ids"] == ["SEPARATE-ATTACK"]


def test_model_chain_shares_one_time_budget(monkeypatch):
    elapsed = [0]
    timeouts = []

    class Response:
        status_code = 503

    def post(url, **kwargs):
        timeouts.append(kwargs["timeout"])
        elapsed[0] += 6
        return Response()

    monkeypatch.setattr(config, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(config, "GEMINI_MODELS", ["one", "two", "three"])
    monkeypatch.setattr(gemini.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(gemini.requests, "post", post)
    result = gemini._call("test", "safe summary", timeout=10)
    assert result["source"].startswith("fallback")
    assert timeouts == [10, 4]


def test_supplier_is_not_rejected_for_a_cancelled_notice_on_another_part_of_the_route():
    data, case, clock, store, evidence, routes = _sample("cancelled-strike")
    rows = _parse(case["reference"], evidence, routes)
    store.upsert(
        "locations",
        "SEA-OTHER",
        {"location_id": "SEA-OTHER", "name": "Another channel", "type": "sea_waypoint"},
    )
    lane = store.get_by_id("lanes", "LANE-MUM-DEMO")
    store.upsert(
        "lanes",
        lane["lane_id"],
        {**lane, "points": [*lane["points"], {"location_id": "SEA-OTHER"}]},
    )
    store.upsert(
        "signals",
        "OTHER-ATTACK",
        {
            "signal_id": "OTHER-ATTACK",
            "source": "synthetic-notice",
            "title": "Cargo ship attacked in Another channel",
            "published_at": clock.isoformat(),
            "payload": {"location_id": "SEA-OTHER"},
        },
    )
    triage.run_triage(store, judgments=rows, as_of=clock)
    plan = planner.build_plan(store, sku=data["sku"], location_id=data["location_id"], as_of=clock)
    assert plan["selected_offer_id"] == "OFFER-CHEAPER-SEA"
