"""Offline benchmark: real execution measurements on bundled sample records.

    python tests/benchmark/benchmark.py --runs 5000 --output-dir /path/to/results

reference.py independently calculates expectations from raw inputs. The fixed
scenario clock makes expiry and injected notices reproducible. Only --gemini
permits network access and opts in to live model calls. Local timings exclude
Gemini, HTTP, Firestore, browser rendering, concurrency and cold starts.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.adapters import news as news_mod
from backend.ai import gemini as gemini_mod
from backend.app.routers import dashboard
from backend.core import config
from backend.core.store import SnapshotStore
from backend.domain import exposure as exposure_mod
from backend.domain import planner as planner_mod

spec = importlib.util.spec_from_file_location("benchmark_reference", HERE / "reference.py")
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)

SCENARIO_CLOCK = datetime(2026, 10, 17, 9, tzinfo=timezone.utc)
DISRUPTED = [
    "SEA-HORMUZ",
    "SEA-BLACK",
    "SEA-REDSEA",
    "SEA-BAB",
    "SEA-ADEN",
    "SEA-ANDAMAN",
    "SEA-BOB",
]
COLLECTIONS = [
    "locations",
    "lanes",
    "products",
    "partners",
    "shipments",
    "order_lines",
    "stock_balances",
    "supplier_offers",
    "signals",
    "alerts",
    "exposures",
    "events",
]


@contextmanager
def offline_network():
    """Fail closed if any unmocked code attempts an outbound connection."""

    def blocked(*args, **kwargs):
        raise RuntimeError("Outbound network disabled by the offline benchmark")

    with ExitStack() as stack:
        for target in (
            "socket.socket.connect",
            "socket.socket.connect_ex",
            "socket.create_connection",
        ):
            stack.enter_context(patch(target, blocked))
        yield


def load_snapshot(fixtures_dir=None):
    directory = Path(fixtures_dir or ROOT / "fixtures")
    records = {}
    for name in COLLECTIONS:
        file = directory / f"{name}.json"
        records[name] = json.loads(file.read_text()) if file.exists() else []
    store = SnapshotStore(records)
    for name, rows in records.items():
        if len(store.list(name)) != len(rows):
            raise ValueError(f"Duplicate record IDs in {name}; refusing a silently reduced dataset")
    return store


def copy_store(store):
    return SnapshotStore({name: store.list(name) for name in COLLECTIONS})


def make_disrupted_store(fixtures_dir=None, as_of=SCENARIO_CLOCK):
    """Inject explicitly synthetic notices and risk flags in a private snapshot."""
    store = load_snapshot(fixtures_dir)
    for place in DISRUPTED:
        store.upsert(
            "signals",
            f"BENCH-{place}",
            {
                "signal_id": f"BENCH-{place}",
                "source": "benchmark-synthetic",
                "title": f"Synthetic benchmark notice: commercial ships attacked near {place}",
                "published_at": as_of.isoformat(),
                "payload": {"location_id": place},
            },
        )
    lanes = {row["lane_id"]: row for row in store.list("lanes")}
    for shipment in store.list("shipments"):
        points = lanes.get(shipment.get("lane_id"), {}).get("points", [])
        if shipment.get("status") == "in_transit" and any(
            point.get("location_id") in DISRUPTED for point in points
        ):
            store.upsert(
                "shipments",
                shipment["shipment_id"],
                {
                    **shipment,
                    "risk_zone": "risk",
                    "risk_reason": "controlled benchmark disruption",
                },
            )
    return store


def at_risk_pairs(store, as_of=SCENARIO_CLOCK):
    """Identify expected shortages from raw inputs, never the system under test."""
    return [
        (sku, loc)
        for sku, loc in reference.order_pairs(store)
        if reference.expected_plan(store, sku, loc, as_of)["exposure"]["shortage_qty"] > 0
    ]


def bench(fn, runs, warmup=25):
    if runs < 1:
        raise ValueError("runs must be positive")
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(runs):
        started = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    samples.sort()
    return {
        "runs": runs,
        "warmup_excluded": warmup,
        "avg_ms": round(statistics.fmean(samples), 6),
        "p50_ms": round(statistics.median(samples), 6),
        "p95_ms": round(samples[math.ceil(0.95 * runs) - 1], 6),
        "min_ms": round(samples[0], 6),
        "max_ms": round(samples[-1], 6),
    }


def section_correctness(store, pairs=None, as_of=SCENARIO_CLOCK):
    pairs = reference.order_pairs(store) if pairs is None else pairs
    cases = []
    for sku, location_id in pairs:
        plan = planner_mod.build_plan(store, sku=sku, location_id=location_id, as_of=as_of)
        comparisons = reference.validate_plan(store, sku, location_id, as_of, plan)
        cases.append(
            {
                "sku": sku,
                "location_id": location_id,
                "expected_shortage": reference.expected_plan(store, sku, location_id, as_of)[
                    "exposure"
                ]["shortage_qty"],
                "comparisons": comparisons,
                "all_passed": all(row["passed"] for row in comparisons),
            }
        )
    comparisons = [row for case in cases for row in case["comparisons"]]
    violations = [
        {"sku": case["sku"], "location_id": case["location_id"], **row}
        for case in cases
        for row in case["comparisons"]
        if not row["passed"]
    ]
    return {
        "plans_checked": len(cases),
        "shortage_plans": sum(case["expected_shortage"] > 0 for case in cases),
        "covered_plans": sum(case["expected_shortage"] == 0 for case in cases),
        "plans_passed": sum(case["all_passed"] for case in cases),
        "comparisons_passed": sum(row["passed"] for row in comparisons),
        "comparisons_total": len(comparisons),
        "violations": violations,
        "all_passed": bool(cases) and not violations,
        "cases": cases,
    }


def section_latency(store, runs, as_of=SCENARIO_CLOCK):
    pairs = at_risk_pairs(store, as_of)
    if not pairs:
        raise ValueError("No reference-calculated shortage plans to time")
    index = 0

    def build_cycle():
        nonlocal index
        sku, loc = pairs[index % len(pairs)]
        index += 1
        return planner_mod.build_plan(store, sku=sku, location_id=loc, as_of=as_of)

    sku, loc = pairs[0]
    expected = reference.expected_plan(store, sku, loc, as_of)["exposure"]
    inputs = {
        "sku": sku,
        "location_id": loc,
        "deadline": expected["deadline"],
        "on_hand_qty": expected["on_hand_qty"],
        "shipments": store.list("shipments"),
        "order_lines": store.list("order_lines"),
        "scenario": expected["scenario"],
    }
    with patch.object(planner_mod, "utc_now", return_value=as_of):
        return {
            "assess_exposure": bench(lambda: exposure_mod.assess_exposure(**inputs), runs),
            "build_recovery_plan": bench(build_cycle, runs),
            "dashboard_overview_assembly": bench(lambda: dashboard.overview(store), min(runs, 250)),
        }


class FakeResp:
    def __init__(self, status, payload=None, content=b""):
        self.status_code, self._payload, self.content = status, payload, content

    def json(self):
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise news_mod.requests.HTTPError(str(self.status_code))


def section_resilience():
    """Synthetic HTTP failures. No actual provider requests or credentials."""
    results = {}
    rss = (
        b"<rss><channel><item><title>Port closed</title>"
        b"<link>https://example.test/news</link>"
        b"<pubDate>Sat, 17 Oct 2026 09:00:00 GMT</pubDate></item></channel></rss>"
    )

    def fake_get(url, **kwargs):
        return FakeResp(429) if "gdelt" in url else FakeResp(200, content=rss)

    with (
        patch.object(news_mod, "_cache", {}),
        patch.object(news_mod, "_gdelt_paused_until", 0),
        patch.object(news_mod, "_last_gdelt_call", 0),
        patch.object(news_mod.requests, "get", side_effect=fake_get),
        patch.object(news_mod.time, "sleep", return_value=None),
    ):
        result = news_mod.search_disruptions("Benchmark port")
        results["news_429_to_rss"] = result.get("ok") and result.get("source") == "google-news"

    success = {
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": "offline response"}]}}
        ]
    }
    for scenario in ("model_503", "key_429", "no_keys", "all_models_unavailable"):
        calls = []

        def post(url, *, calls=calls, scenario=scenario, **kwargs):
            calls.append((url, kwargs["headers"]["X-goog-api-key"]))
            if scenario == "no_keys":
                raise AssertionError("No-key mode must not call HTTP")
            if scenario == "all_models_unavailable":
                return FakeResp(503)
            if len(calls) == 1:
                return FakeResp(429 if scenario == "key_429" else 503)
            return FakeResp(200, payload=success)

        keys = [] if scenario == "no_keys" else ["offline-primary"]
        if scenario == "key_429":
            keys.append("offline-secondary")
        with (
            patch.object(config, "GEMINI_API_KEYS", keys),
            patch.object(config, "GEMINI_MODELS", ["offline-a", "offline-b"]),
            patch.object(gemini_mod, "_cooldown", {}),
            patch.object(gemini_mod, "_key_cooldown", {}),
            patch.object(gemini_mod.requests, "post", side_effect=post),
        ):
            result = gemini_mod._call("offline test", fallback="local summary", timeout=5)
        if scenario == "model_503":
            ok = (
                result["source"].startswith("gemini")
                and len(calls) == 2
                and "offline-b" in calls[-1][0]
            )
        elif scenario == "key_429":
            ok = (
                result["source"].startswith("gemini")
                and len(calls) == 2
                and calls[0][0] == calls[1][0]
                and calls[0][1] != calls[1][1]
            )
        elif scenario == "no_keys":
            ok = not calls and result["text"] == "local summary"
        else:
            ok = (
                len(calls) == 2
                and result["source"].startswith("fallback")
                and "local summary" in result["text"]
            )
        results[scenario] = bool(ok)
    return {
        "checks": results,
        "passed": sum(results.values()),
        "total": len(results),
        "all_passed": all(results.values()),
        "mode": "mocked HTTP failure injection",
    }


def section_mutations(store, as_of=SCENARIO_CLOCK):
    """Prove sensitivity to selected faults, not application or AI accuracy."""
    plans = [
        (sku, loc, planner_mod.build_plan(store, sku=sku, location_id=loc, as_of=as_of))
        for sku, loc in reference.order_pairs(store)
    ]
    eligible = [row for row in plans if row[2].get("selected_offer_id")]
    if not eligible:
        return {
            "all_passed": False,
            "error": "No supplier plan for negative controls",
            "detected": 0,
            "total": 0,
            "cases": [],
        }
    sku, loc, original = eligible[0]
    baseline_valid = all(
        row["passed"] for row in reference.validate_plan(store, sku, loc, as_of, original)
    )
    cases = []

    def assess(name, snapshot, plan):
        failures = [
            row["check"]
            for row in reference.validate_plan(snapshot, sku, loc, as_of, plan)
            if not row["passed"]
        ]
        cases.append(
            {
                "fault": name,
                "detected": baseline_valid and bool(failures),
                "failed_checks": failures,
            }
        )

    fields = [
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
    ]
    for field in fields:
        plan = deepcopy(original)
        container = plan
        parts = field.split(".")
        for part in parts[:-1]:
            container = container[part]
        container[parts[-1]] += 1
        assess(f"altered_{field}", store, plan)
    plan = deepcopy(original)
    plan["selected_offer_id"], plan["supplier_options"] = None, []
    assess("missing_supplier_choice_and_options", store, plan)
    plan = deepcopy(original)
    plan["approval"]["tier"] = "invalid_tier"
    assess("wrong_approval_tier", store, plan)
    offer_id = original["selected_offer_id"]
    raw = next(row for row in store.list("supplier_offers") if row["offer_id"] == offer_id)
    changes = {
        "ignored_quote_expiry": {"expires_at": (as_of - timedelta(days=1)).isoformat()},
        "ignored_supplier_capacity": {"available_qty": 0},
        "ignored_delivery_deadline": {"delivery_latest": "2099-01-01T00:00:00Z"},
    }
    blocked = sorted(reference.blocked_places(store, as_of))
    if blocked:
        changes["ignored_blocked_route"] = {"route_location_ids": [blocked[0]]}
    for name, values in changes.items():
        snapshot = copy_store(store)
        snapshot.upsert("supplier_offers", offer_id, {**raw, **values})
        assess(name, snapshot, deepcopy(original))
    return {
        "baseline_control_passed": baseline_valid,
        "case_sku": sku,
        "case_location_id": loc,
        "detected": sum(row["detected"] for row in cases),
        "total": len(cases),
        "cases": cases,
        "all_passed": baseline_valid and all(row["detected"] for row in cases),
    }


def section_gemini_live(store, runs=3):
    """Optional paid requests. Response validity is not predictive accuracy."""
    if runs < 1:
        raise ValueError("runs must be positive")
    if not config.GEMINI_API_KEYS:
        return {"skipped": "No Gemini API keys configured", "all_passed": False}
    expected_ids = {
        row["shipment_id"]
        for row in store.list("shipments")
        if row.get("status") in ("in_transit", "planned")
    }
    if not expected_ids:
        return {"skipped": "No active shipments to assess", "all_passed": False}
    decisions, durations, errors = [], [], []
    for _ in range(runs):
        started = time.perf_counter()
        rows = gemini_mod.judge_shipment_risk(
            shipments=store.list("shipments"),
            signals=store.list("signals"),
            locations=store.list("locations"),
            products=store.list("products"),
            lanes=store.list("lanes"),
        )
        durations.append((time.perf_counter() - started) * 1000)
        valid = (
            isinstance(rows, list)
            and len(rows) == len(expected_ids)
            and all(isinstance(row, dict) for row in rows)
            and {row.get("shipment_id") for row in rows} == expected_ids
            and all(row.get("status") in ("affected", "unaffected", "unknown") for row in rows)
        )
        if valid:
            decisions.append({row["shipment_id"]: row["status"] for row in rows})
        else:
            errors.append("Unavailable or invalid/incomplete validated interpretation")
    consistent = (
        sum(len({run[key] for run in decisions}) == 1 for key in expected_ids)
        if len(decisions) >= 2
        else None
    )
    return {
        "attempts": runs,
        "validated_responses": len(decisions),
        "validated_response_rate": len(decisions) / runs,
        "avg_attempt_ms": statistics.fmean(durations),
        "consistent_shipments": consistent,
        "shipments": len(expected_ids),
        "successful_runs_compared": len(decisions),
        "errors": errors,
        "accuracy_measured": False,
        "all_passed": len(decisions) == runs,
    }


def provenance(fixtures_dir):
    files = list(Path(fixtures_dir).glob("*.json"))
    code = list((ROOT / "backend").rglob("*.py")) + [Path(__file__), HERE / "reference.py"]

    def hashes(paths):
        return {
            str(file.relative_to(ROOT)) if file.is_relative_to(ROOT) else str(file): hashlib.sha256(
                file.read_bytes()
            ).hexdigest()
            for file in sorted(paths)
        }

    return {
        "fixture_sha256": hashes(files),
        "implementation_sha256": hashes(code),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
    }


def regression_result(junit):
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    totals = {
        key: sum(int(row.get(key, 0)) for row in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    totals["passed"] = totals["tests"] - sum(
        totals[key] for key in ("failures", "errors", "skipped")
    )
    return {
        **totals,
        "source_junit": str(Path(junit).resolve()),
        "all_passed": totals["tests"] > 0 and totals["failures"] == totals["errors"] == 0,
    }


def overall_passed(data):
    return (
        all(row["all_passed"] for row in data["validation"].values())
        and data["resilience"]["all_passed"]
        and data["checker_sensitivity"]["all_passed"]
        and data.get("regression", {"all_passed": True})["all_passed"]
        and data.get("gemini_live", {"all_passed": True})["all_passed"]
    )


def write_report(data, output_dir):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SignalBridge measured offline benchmark",
        "",
        f"Measured at {data['generated_at_utc']}. Fixed scenario clock: {data['scenario_clock']}.",
        "",
        "## Scope",
        "",
        (
            "Actual local execution measurements on bundled sample records, with a separate "
            "controlled disruption scenario. These are not live customer outcomes, cloud API "
            "latencies, AI accuracy scores or production capacity measurements."
        ),
        "",
        (
            "Outbound network connections are blocked by default. No Firestore writes, "
            "reservations, purchases or emails occur. Fallbacks use mocked HTTP responses."
        ),
        "",
        "## Dataset",
        "",
        "| Record type | Count |",
        "|---|---:|",
    ]
    lines += [f"| {name} | {count} |" for name, count in data["scale"].items()]
    lines += [
        "",
        "## Independent validation",
        "",
        (
            "The reference calculator reads raw orders, stock, routes, signals and offers. "
            "It does not call the application calculator or trust its feasibility flags. "
            "It validates the current documented sample-data policy, not all operational risks."
        ),
        "",
        "| Scenario | Plans matched | Shortage / covered | Field comparisons |",
        "|---|---:|---:|---:|",
    ]
    for name, result in data["validation"].items():
        lines.append(
            f"| {name} | {result['plans_passed']}/{result['plans_checked']} | "
            f"{result['shortage_plans']} / {result['covered_plans']} | "
            f"{result['comparisons_passed']}/{result['comparisons_total']} |"
        )
    lines += [
        "",
        (
            "Comparisons include demand, incoming supply, shortage, internal free stock, "
            "offer coverage, capacity, delivery deadline, expiry, blocked routes, supplier "
            "selection, cost, revenue exposure, penalties, surplus and approval tier. "
            "Equal-cost optimal offers are accepted. Reason text is checked for presence only."
        ),
        "",
        "## Local latency",
        "",
        (
            "Warm in-process calls, sequential execution. Each operation excludes 25 warm-ups. "
            "Recovery plans rotate across independently identified shortage cases. "
            "p95 uses the nearest-rank method. These numbers exclude network and model latency."
        ),
        "",
        "| Operation | Samples | Mean ms | Median ms | p95 ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, result in data["latency"].items():
        lines.append(
            f"| {name} | {result['runs']} | {result['avg_ms']:.4f} | "
            f"{result['p50_ms']:.4f} | {result['p95_ms']:.4f} |"
        )
    res, sensitivity = data["resilience"], data["checker_sensitivity"]
    lines += [
        "",
        "## Simulated resilience",
        "",
        f"{res['passed']}/{res['total']} mocked failure scenarios passed.",
        "",
    ]
    lines += [f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in res["checks"].items()]
    lines += [
        "",
        "## Benchmark negative controls",
        "",
        (
            f"{sensitivity['detected']}/{sensitivity['total']} deliberately injected faults "
            "detected. This measures sensitivity to these selected faults, not AI accuracy."
        ),
        "",
    ]
    lines.append(
        f"Control case: {sensitivity.get('case_sku')} at {sensitivity.get('case_location_id')}. "
        "Faults target this selected recovery case, not every plan."
    )
    lines += [
        f"- {row['fault']}: {'DETECTED' if row['detected'] else 'MISSED'}"
        for row in sensitivity["cases"]
    ]
    if "regression" in data:
        result = data["regression"]
        lines += [
            "",
            "## Offline regression",
            "",
            (
                f"JUnit records {result['passed']} passed, {result['failures']} failed, "
                f"{result['errors']} errors and {result['skipped']} skipped tests."
            ),
        ]
    lines += [
        "",
        "## Limitations",
        "",
        "- Business records are bundled sample data. Injected disruption notices are synthetic.",
        "- Arrival delays are scenario assumptions, not Gemini-predicted ETAs.",
        "- Individual plans do not prove simultaneous recovery feasibility across shared stock.",
        "- Internal availability excludes reservations but not donor demand or transit time.",
        "- Margin figures are decision estimates, not realized savings or profit.",
        "- Offline results do not measure live Gemini, cold starts, concurrent load or uptime.",
        "",
        f"Overall benchmark status: {'PASS' if overall_passed(data) else 'FAIL'}.",
        "",
        "Full comparisons, violations, fixture/code hashes and environment are in results.json.",
    ]
    for name, result in data["validation"].items():
        if result["violations"]:
            lines += [
                "",
                f"## Violations: {name}",
                "",
                "```json",
                json.dumps(result["violations"], indent=2),
                "```",
            ]
    if "gemini_live" in data:
        lines += [
            "",
            "## Optional live Gemini results",
            "",
            "```json",
            json.dumps(data["gemini_live"], indent=2),
            "```",
        ]
    (directory / "report.md").write_text("\n".join(lines) + "\n")
    (directory / "results.json").write_text(json.dumps(data, indent=2) + "\n")


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=positive_int, default=1000)
    parser.add_argument("--as-of", type=reference.timestamp, default=SCENARIO_CLOCK)
    parser.add_argument("--fixtures-dir", type=Path, default=ROOT / "fixtures")
    parser.add_argument("--output-dir", type=Path, default=HERE)
    parser.add_argument("--regression-junit", type=Path)
    parser.add_argument("--gemini", action="store_true", help="OPT IN to paid/live model calls")
    args = parser.parse_args(argv)
    with ExitStack() as stack:
        if not args.gemini:
            stack.enter_context(offline_network())
        baseline = load_snapshot(args.fixtures_dir)
        controlled = make_disrupted_store(args.fixtures_dir, args.as_of)
        data = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "scenario_clock": args.as_of.isoformat(),
            "network_blocked": not args.gemini,
            "live_gemini_requested": args.gemini,
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "machine": platform.machine(),
                "logical_cpu_count": os.cpu_count(),
            },
            "provenance": provenance(args.fixtures_dir),
            "scale": {name: len(baseline.list(name)) for name in COLLECTIONS[:9]},
            "validation": {
                "stored_snapshot": section_correctness(baseline, as_of=args.as_of),
                "controlled_disruption": section_correctness(controlled, as_of=args.as_of),
            },
            "latency": section_latency(controlled, args.runs, args.as_of),
            "resilience": section_resilience(),
            "checker_sensitivity": section_mutations(controlled, args.as_of),
        }
        if args.regression_junit:
            data["regression"] = regression_result(args.regression_junit)
        if args.gemini:
            data["gemini_live"] = section_gemini_live(controlled)
        write_report(data, args.output_dir)
    summary = {
        "overall_passed": overall_passed(data),
        "network_blocked": data["network_blocked"],
        "validation": {
            name: {key: value for key, value in row.items() if key not in ("cases", "violations")}
            for name, row in data["validation"].items()
        },
        "latency": data["latency"],
        "resilience": data["resilience"],
        "checker_sensitivity": {
            key: value for key, value in data["checker_sensitivity"].items() if key != "cases"
        },
        "report": str(args.output_dir / "report.md"),
    }
    print(json.dumps(summary, indent=2))
    return 0 if overall_passed(data) else 1


if __name__ == "__main__":
    raise SystemExit(main())
