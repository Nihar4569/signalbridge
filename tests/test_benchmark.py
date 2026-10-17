"""Regression and negative-control tests for trustworthy benchmark reporting."""

import ast
import importlib.util
import socket
from copy import deepcopy
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "benchmark_under_test", Path(__file__).parent / "benchmark" / "benchmark.py"
)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
CLOCK = benchmark.SCENARIO_CLOCK


@pytest.fixture
def sample():
    """Hand-solvable case: 80 short, 20 internal, 60 bought for 370000 paise."""
    return benchmark.SnapshotStore(
        {
            "locations": [
                {"location_id": "DEST", "type": "dc"},
                {"location_id": "DONOR", "type": "dark_store", "active": True},
                {"location_id": "INACTIVE", "type": "dc", "active": False},
                {"location_id": "SEA-HORMUZ", "type": "sea_waypoint"},
            ],
            "lanes": [{"lane_id": "LANE", "points": [{"location_id": "SEA-HORMUZ"}]}],
            "shipments": [
                {
                    "shipment_id": "SHIP",
                    "lane_id": "LANE",
                    "destination_location_id": "DEST",
                    "status": "in_transit",
                    "risk_zone": "risk",
                    "expected_arrival_at": "2026-10-18T00:00:00Z",
                    "assumed_arrival_at": "2026-10-22T00:00:00Z",
                    "items": [{"sku": "COFFEE", "quantity": 80}],
                }
            ],
            "order_lines": [
                {
                    "order_id": "ORDER",
                    "line_id": "LINE-1",
                    "sku": "COFFEE",
                    "location_id": "DEST",
                    "quantity": 100,
                    "status": "open",
                    "due_at": "2026-10-19T00:00:00Z",
                    "customer_id": "CUSTOMER",
                },
                {
                    "order_id": "LATER",
                    "line_id": "LINE-2",
                    "sku": "COFFEE",
                    "location_id": "DEST",
                    "quantity": 999,
                    "status": "open",
                    "due_at": "2026-10-20T00:00:00Z",
                    "customer_id": "CUSTOMER",
                },
            ],
            "stock_balances": [
                {"sku": "COFFEE", "location_id": "DEST", "on_hand_qty": 20, "reserved_qty": 0},
                {"sku": "COFFEE", "location_id": "DONOR", "on_hand_qty": 30, "reserved_qty": 10},
                {"sku": "COFFEE", "location_id": "INACTIVE", "on_hand_qty": 999, "reserved_qty": 0},
            ],
            "products": [{"sku": "COFFEE", "unit_price_minor": 10000}],
            "partners": [
                {"partner_id": "CUSTOMER", "service_level": {"penalty_per_late_order_minor": 50000}}
            ],
            "supplier_offers": [
                {
                    "offer_id": "DIRECT",
                    "sku": "COFFEE",
                    "available_qty": 60,
                    "unit_price_minor": 6000,
                    "shipping_minor": 10000,
                    "delivery_latest": "2026-10-18T00:00:00Z",
                    "expires_at": "2026-10-18T00:00:00Z",
                    "route_location_ids": [],
                },
                {
                    "offer_id": "SEA",
                    "sku": "COFFEE",
                    "available_qty": 60,
                    "unit_price_minor": 4000,
                    "shipping_minor": 10000,
                    "delivery_latest": "2026-10-18T00:00:00Z",
                    "route_location_ids": ["SEA-HORMUZ"],
                },
            ],
            "signals": [
                {
                    "signal_id": "NOTICE",
                    "source": "benchmark-synthetic",
                    "title": "Commercial ships attacked near Hormuz",
                    "published_at": CLOCK.isoformat(),
                    "payload": {"location_id": "SEA-HORMUZ"},
                }
            ],
        }
    )


def plan_for(sample):
    return benchmark.planner_mod.build_plan(sample, sku="COFFEE", location_id="DEST", as_of=CLOCK)


def failures(sample, plan):
    return [
        row
        for row in benchmark.reference.validate_plan(sample, "COFFEE", "DEST", CLOCK, plan)
        if not row["passed"]
    ]


def test_reference_hand_calculated_example(sample):
    expected = benchmark.reference.expected_plan(sample, "COFFEE", "DEST", CLOCK)
    assert expected["exposure"]["demand_by_deadline"] == 100  # not the later 999 units
    assert expected["exposure"]["shortage_qty"] == 80
    assert expected["baseline_exposure"]["shortage_qty"] == 0
    assert expected["internal_options"] == {"DONOR": 20}
    assert expected["internal_used_qty"] == 20
    assert expected["supplier_qty"] == 60
    assert expected["selected_offer_ids"] == {"DIRECT"}
    assert expected["margin_check"] == {
        "recovery_cost_minor": 370000,
        "protected_revenue_minor": 800000,
        "penalty_avoided_minor": 50000,
        "net_benefit_minor": 480000,
        "verdict": "worth_it",
    }
    assert expected["surplus_forecast"]["expected_surplus_qty"] == 80
    assert not failures(sample, plan_for(sample))


def test_reference_never_imports_application_logic():
    tree = ast.parse((benchmark.HERE / "reference.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module in {"datetime"}
        elif isinstance(node, ast.Import):
            assert all(item.name == "re" for item in node.names)


def test_expected_pair_selection_does_not_trust_planner(sample, monkeypatch):
    monkeypatch.setattr(benchmark.planner_mod, "build_plan", lambda *a, **k: {})
    assert benchmark.at_risk_pairs(sample) == [("COFFEE", "DEST")]


@pytest.mark.parametrize(
    "field",
    [
        "exposure.shortage_qty",
        "exposure.supply_by_deadline",
        "internal_used_qty",
        "supplier_qty",
        "recovered_qty",
        "margin_check.recovery_cost_minor",
        "margin_check.protected_revenue_minor",
        "margin_check.penalty_avoided_minor",
        "margin_check.net_benefit_minor",
        "surplus_forecast.expected_surplus_qty",
    ],
)
def test_wrong_numbers_are_detected(sample, field):
    plan = plan_for(sample)
    parts = field.split(".")
    container = plan
    for part in parts[:-1]:
        container = container[part]
    container[parts[-1]] += 1
    assert any(row["check"] == field for row in failures(sample, plan))


def test_missing_supplier_data_does_not_auto_pass(sample):
    plan = plan_for(sample)
    plan["supplier_options"], plan["selected_offer_id"] = [], None
    assert failures(sample, plan)


@pytest.mark.parametrize(
    "fields",
    [
        {"available_qty": 0},
        {"expires_at": "2000-01-01T00:00:00Z"},
        {"delivery_latest": "2099-01-01T00:00:00Z"},
        {"route_location_ids": ["SEA-HORMUZ"]},
    ],
)
def test_raw_constraints_are_checked_even_if_planner_ignores_them(sample, fields):
    old_plan = plan_for(sample)
    quote = sample.get_by_id("supplier_offers", "DIRECT")
    sample.upsert("supplier_offers", "DIRECT", {**quote, **fields})
    assert failures(sample, old_plan)


def test_equal_cost_optimal_offer_is_valid(sample):
    quote = sample.get_by_id("supplier_offers", "DIRECT")
    sample.upsert("supplier_offers", "TIE", {**quote, "offer_id": "TIE"})
    plan = plan_for(sample)
    plan["selected_offer_id"] = "TIE"
    assert not failures(sample, plan)


def test_covered_orders_are_checked_not_silently_dropped(sample):
    shipment = sample.get_by_id("shipments", "SHIP")
    sample.upsert("shipments", "SHIP", {**shipment, "risk_zone": "safe"})
    result = benchmark.section_correctness(sample)
    assert result["covered_plans"] == result["plans_checked"] == 1
    assert result["all_passed"]


def test_empty_dataset_is_not_success():
    assert not benchmark.section_correctness(benchmark.SnapshotStore({}))["all_passed"]


def test_failure_diagnostics_include_non_money_errors(sample, monkeypatch):
    plan = plan_for(sample)
    plan["supplier_options"][0]["reason"] = ""
    monkeypatch.setattr(benchmark.planner_mod, "build_plan", lambda *a, **k: plan)
    result = benchmark.section_correctness(sample)
    assert not result["all_passed"]
    assert any(row["check"].endswith("reason_present") for row in result["violations"])


def test_mutation_negative_controls(sample):
    result = benchmark.section_mutations(sample)
    assert result["baseline_control_passed"]
    assert result["detected"] == result["total"] == 16
    assert result["all_passed"]


def test_resilience_uses_current_keys_and_restores_state():
    keys = benchmark.config.GEMINI_API_KEYS
    models = benchmark.config.GEMINI_MODELS
    cooldowns = deepcopy(benchmark.gemini_mod._key_cooldown)
    result = benchmark.section_resilience()
    assert result["passed"] == result["total"] == 5
    assert benchmark.config.GEMINI_API_KEYS is keys
    assert benchmark.config.GEMINI_MODELS is models
    assert benchmark.gemini_mod._key_cooldown == cooldowns


def test_offline_guard_blocks_connections():
    with (
        benchmark.offline_network(),
        socket.socket() as connection,
        pytest.raises(RuntimeError, match="Outbound network disabled"),
    ):
        connection.connect(("127.0.0.1", 9))


@pytest.mark.parametrize(
    "row", [None, [], ["bad row"], [{"shipment_id": "SHIP", "status": "invented"}]]
)
def test_live_response_validation_rejects_missing_or_invalid_rows(sample, monkeypatch, row):
    monkeypatch.setattr(benchmark.config, "GEMINI_API_KEYS", ["offline-test"])
    monkeypatch.setattr(benchmark.gemini_mod, "judge_shipment_risk", lambda **kwargs: row)
    result = benchmark.section_gemini_live(sample, runs=1)
    assert result["validated_responses"] == 0
    assert result["validated_response_rate"] == 0
    assert not result["all_passed"]


def test_live_section_accepts_status_contract_and_measures_failures(sample, monkeypatch):
    monkeypatch.setattr(benchmark.config, "GEMINI_API_KEYS", ["offline-test"])
    responses = iter(
        [
            [{"shipment_id": "SHIP", "status": "affected"}],
            None,
            [{"shipment_id": "SHIP", "status": "affected"}],
        ]
    )
    monkeypatch.setattr(
        benchmark.gemini_mod, "judge_shipment_risk", lambda **kwargs: next(responses)
    )
    result = benchmark.section_gemini_live(sample, runs=3)
    assert result["validated_response_rate"] == 2 / 3
    assert result["consistent_shipments"] == 1
    assert result["accuracy_measured"] is False
    assert not result["all_passed"]


def test_main_returns_failure_when_a_section_fails(sample, monkeypatch, tmp_path):
    monkeypatch.setattr(benchmark, "load_snapshot", lambda *a: sample)
    monkeypatch.setattr(benchmark, "make_disrupted_store", lambda *a: sample)
    monkeypatch.setattr(benchmark, "provenance", lambda *a: {})
    monkeypatch.setattr(benchmark, "section_latency", lambda *a: {})
    monkeypatch.setattr(benchmark, "section_resilience", lambda: {"all_passed": False})
    monkeypatch.setattr(benchmark, "write_report", lambda *a: None)
    assert benchmark.main(["--runs", "1", "--output-dir", str(tmp_path)]) == 1


def test_non_positive_iterations_are_rejected():
    with pytest.raises(SystemExit) as error:
        benchmark.main(["--runs", "0"])
    assert error.value.code == 2


def test_fixed_clock_produces_repeatable_validation(sample):
    assert benchmark.section_correctness(sample) == benchmark.section_correctness(sample)


def test_junit_counts_are_read_not_hard_coded(tmp_path):
    file = tmp_path / "junit.xml"
    file.write_text(
        '<testsuites><testsuite tests="7" failures="1" errors="1" skipped="2" /></testsuites>'
    )
    result = benchmark.regression_result(file)
    assert result["passed"] == 3
    assert not result["all_passed"]


def test_duplicate_input_ids_are_rejected(tmp_path):
    file = tmp_path / "order_lines.json"
    file.write_text('[{"line_id":"duplicate"},{"line_id":"duplicate"}]')
    with pytest.raises(ValueError, match="Duplicate record IDs"):
        benchmark.load_snapshot(tmp_path)


def test_old_disruption_does_not_block_an_offer(sample):
    notice = sample.get_by_id("signals", "NOTICE")
    sample.upsert("signals", "NOTICE", {**notice, "published_at": "2000-01-01T00:00:00Z"})
    expected = benchmark.reference.expected_plan(sample, "COFFEE", "DEST", CLOCK)
    assert expected["selected_offer_ids"] == {"SEA"}
    assert not failures(sample, plan_for(sample))


def test_cited_cancellation_resolves_only_that_notice(sample):
    quote = "The strike was cancelled before it began."
    sample.upsert(
        "signals",
        "NOTICE",
        {
            "signal_id": "NOTICE",
            "source": "benchmark-synthetic",
            "title": "Strike cancelled",
            "published_at": CLOCK.isoformat(),
            "payload": {"location_id": "SEA-HORMUZ", "notice_text": quote},
        },
    )
    shipment = sample.get_by_id("shipments", "SHIP")
    sample.upsert(
        "shipments",
        "SHIP",
        {
            **shipment,
            "risk_assessment": {
                "event_status": "cancelled",
                "evidence": [{"signal_id": "NOTICE", "quote": quote}],
            },
        },
    )
    assert benchmark.reference.blocked_places(sample, CLOCK) == set()
    assert not failures(sample, plan_for(sample))
    sample.upsert(
        "signals",
        "OTHER",
        {
            "signal_id": "OTHER",
            "source": "benchmark-synthetic",
            "title": "Independent attack",
            "published_at": CLOCK.isoformat(),
            "payload": {"location_id": "SEA-HORMUZ"},
        },
    )
    assert benchmark.reference.blocked_places(sample, CLOCK) == {"SEA-HORMUZ"}
    assert not failures(sample, plan_for(sample))


@pytest.mark.parametrize("kind", ["integer_flag", "float_quantity", "float_internal_stock"])
def test_numeric_types_are_not_silently_coerced(sample, kind):
    plan = plan_for(sample)
    if kind == "integer_flag":
        plan["supplier_options"][0]["feasible"] = 1
    elif kind == "float_quantity":
        plan["supplier_qty"] = float(plan["supplier_qty"])
    else:
        plan["internal_options"][0]["free_qty"] = 20.0
    assert failures(sample, plan)
