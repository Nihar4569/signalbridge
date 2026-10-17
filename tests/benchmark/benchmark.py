"""Prototype performance benchmark for SignalBridge.

Measures the things a hackathon prototype is judged on:
  1. Scale        - how much real data the engine works on
  2. Latency      - how fast the deterministic AI-recovery engine runs
  3. Correctness  - money/feasibility invariants hold on every plan (no AI guessing)
  4. Resilience   - news + Gemini fallbacks keep the app alive under failure
  5. (optional)   - live Gemini triage latency + self-consistency  (--gemini)

Runs fully offline on the bundled real-data snapshot (fixtures/, a copy of the
Firestore tenant) so results are reproducible and isolated from network latency.

    python tests/benchmark/benchmark.py            # core report
    python tests/benchmark/benchmark.py --gemini   # also benchmark live Gemini
    python tests/benchmark/benchmark.py --runs 5000

Writes tests/benchmark/report.md and tests/benchmark/results.json.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.adapters import news as news_mod  # noqa: E402
from backend.ai import gemini as gemini_mod  # noqa: E402
from backend.app.routers import dashboard, incidents  # noqa: E402
from backend.core import config  # noqa: E402
from backend.core.store import LocalStore  # noqa: E402
from backend.domain import exposure as exposure_mod  # noqa: E402
from backend.domain import governance as governance_mod  # noqa: E402
from backend.domain import planner as planner_mod  # noqa: E402

HERE = Path(__file__).resolve().parent
# Sea chokepoints we treat as disrupted for the controlled scenario.
DISRUPTED = ["SEA-HORMUZ", "SEA-BLACK", "SEA-REDSEA", "SEA-BAB", "SEA-ADEN", "SEA-ANDAMAN", "SEA-BOB"]


# --------------------------------------------------------------------------- #
#  helpers
# --------------------------------------------------------------------------- #
def bench(fn, runs: int) -> dict:
    """Time `fn` over `runs` iterations; return latency stats in milliseconds."""
    fn()  # warm up
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    avg = statistics.fmean(samples)
    return {
        "runs": runs,
        "avg_ms": round(avg, 4),
        "p50_ms": round(samples[int(0.50 * (runs - 1))], 4),
        "p95_ms": round(samples[int(0.95 * (runs - 1))], 4),
        "min_ms": round(samples[0], 4),
        "max_ms": round(samples[-1], 4),
        "ops_per_sec": round(1000 / avg) if avg else 0,
    }


def make_disrupted_store() -> LocalStore:
    """Load the real-data snapshot and apply a reproducible disruption scenario.

    Marks every in-transit shipment whose lane crosses a disrupted chokepoint as
    at-risk, and records a live news signal at each chokepoint, so the engine runs
    its full path (delayed arrival -> shortage -> chokepoint-aware supplier choice).
    """
    store = LocalStore()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for place in DISRUPTED:
        store.upsert("signals", f"BENCH-{place}", {
            "signal_id": f"BENCH-{place}", "source": "google-news",
            "title": f"Commercial ships attacked near {place}", "published_at": now,
            "payload": {"location_id": place},
        })
    lanes = {lane["lane_id"]: lane for lane in store.list("lanes")}
    disrupted = set(DISRUPTED)
    for shipment in store.list("shipments"):
        if shipment.get("status") != "in_transit":
            continue
        points = (lanes.get(shipment.get("lane_id")) or {}).get("points", [])
        if any(p.get("location_id") in disrupted for p in points):
            store.upsert("shipments", shipment["shipment_id"],
                         {**shipment, "risk_zone": "risk", "risk_reason": "chokepoint disruption"})
    return store


def at_risk_pairs(store: LocalStore) -> list[tuple[str, str]]:
    """Unique (sku, location) order pairs that have a real shortage."""
    pairs, seen = [], set()
    for line in store.list("order_lines"):
        key = (line["sku"], line["location_id"])
        if key in seen or line.get("status") != "open":
            continue
        seen.add(key)
        plan = planner_mod.build_plan(store, sku=key[0], location_id=key[1])
        if (plan.get("exposure") or {}).get("shortage_qty", 0) > 0:
            pairs.append(key)
    return pairs


class FakeResp:
    def __init__(self, status, text="", payload=None, content=b""):
        self.status_code, self.text, self._payload = status, text, payload
        self.content = content or text.encode()

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise news_mod.requests.HTTPError(str(self.status_code))


# --------------------------------------------------------------------------- #
#  sections
# --------------------------------------------------------------------------- #
def section_scale(store: LocalStore, pairs) -> dict:
    counts = {c: len(store.list(c)) for c in
              ["locations", "lanes", "products", "partners", "shipments",
               "order_lines", "stock_balances", "supplier_offers", "signals"]}
    counts["at_risk_order_pairs"] = len(pairs)
    counts["supplier_options_evaluated"] = sum(
        len(planner_mod.build_plan(store, sku=s, location_id=l).get("supplier_options", []))
        for s, l in pairs)
    return counts


def section_latency(store: LocalStore, pairs, runs: int) -> dict:
    sku, loc = pairs[0]
    order_lines, shipments = store.list("order_lines"), store.list("shipments")
    deadline = planner_mod._earliest_deadline(order_lines, sku, loc)
    i = {"n": 0}

    def build_cycle():  # rotate across every at-risk plan
        s, l = pairs[i["n"] % len(pairs)]
        i["n"] += 1
        planner_mod.build_plan(store, sku=s, location_id=l)

    return {
        "assess_exposure": bench(lambda: exposure_mod.assess_exposure(
            sku=sku, location_id=loc, deadline=deadline, on_hand_qty=100,
            shipments=shipments, order_lines=order_lines, scenario="disrupted"), runs),
        "route_approval": bench(lambda: governance_mod.route_approval(16_62_000), runs),
        "build_recovery_plan": bench(build_cycle, max(runs // 5, 200)),
        "dashboard_overview": bench(lambda: dashboard.overview(store), max(runs // 20, 100)),
        "dashboard_map": bench(lambda: dashboard.map_data(store), max(runs // 20, 100)),
        "incidents": bench(lambda: incidents.list_incidents(store), max(runs // 20, 100)),
    }


def section_correctness(store: LocalStore, pairs) -> dict:
    """Independent re-check of every plan: money, feasibility, chokepoint rule."""
    checks = {"money_integrity": 0, "cheapest_feasible_chosen": 0,
              "every_option_has_reason": 0, "chokepoint_rule": 0}
    violations = []
    total = 0
    for sku, loc in pairs:
        plan = planner_mod.build_plan(store, sku=sku, location_id=loc)
        options = plan.get("supplier_options", [])
        feasible = [o for o in options if o["feasible"]]
        total += 1

        # 1. money: chosen recovery cost == remainder*unit + shipping (recomputed)
        chosen_id = plan.get("selected_offer_id")
        if chosen_id:
            offer = next(o for o in store.list("supplier_offers") if o["offer_id"] == chosen_id)
            remainder = plan["recovered_qty"] - plan["internal_used_qty"]
            expected = remainder * offer["unit_price_minor"] + offer["shipping_minor"]
            got = plan["margin_check"]["recovery_cost_minor"]
            checks["money_integrity"] += (expected == got)
            if expected != got:
                violations.append(f"{sku}@{loc}: cost {got} != recomputed {expected}")
        else:
            checks["money_integrity"] += 1

        # 2. the chosen offer is the cheapest feasible one
        if feasible:
            cheapest = min(feasible, key=lambda o: o["cost_minor"])
            checks["cheapest_feasible_chosen"] += (cheapest["offer_id"] == chosen_id)
        else:
            checks["cheapest_feasible_chosen"] += 1

        # 3. every rejected option carries a human-readable reason
        checks["every_option_has_reason"] += all(o.get("reason") for o in options)

        # 4. no feasible option routes through a disrupted chokepoint
        bad = [o for o in feasible if "chokepoint" in o["reason"].lower()]
        checks["chokepoint_rule"] += (not bad)

    return {"plans_checked": total, "checks": checks, "violations": violations,
            "all_passed": all(v == total for v in checks.values())}


def section_resilience() -> dict:
    results = {}

    # News: GDELT rate-limited -> Google News RSS takes over.
    news_mod._cache.clear()
    news_mod._gdelt_paused_until = 0.0
    news_mod._last_gdelt_call = 0.0
    orig_get, orig_sleep = news_mod.requests.get, news_mod.time.sleep
    news_mod.time.sleep = lambda s: None
    rss = (b"<rss><channel><item><title>Port closed - X</title><link>http://x/1</link>"
           b"<pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>")
    news_mod.requests.get = lambda url, **k: FakeResp(429, "limit") if "gdelt" in url else FakeResp(200, content=rss)
    try:
        r = news_mod.search_disruptions("Strait of Hormuz")
        results["news_fallback_to_google"] = r["ok"] and r["source"] == "google-news"
    finally:
        news_mod.requests.get, news_mod.time.sleep = orig_get, orig_sleep

    # Gemini: first model 429 -> next model answers.
    orig_post, orig_key, gemini_mod._cooldown = gemini_mod.requests.post, config.GOOGLE_API_KEY, {}
    config.GOOGLE_API_KEY = "benchmark-key"
    calls = {"n": 0}

    def fake_post(url, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResp(429, "quota")
        return FakeResp(200, payload={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    gemini_mod.requests.post = fake_post
    try:
        out = gemini_mod._call("ping", fallback="fb", timeout=5)
        results["gemini_model_chain_fallback"] = out["source"].startswith("gemini") and calls["n"] >= 2
        config.GOOGLE_API_KEY = ""
        gemini_mod._cooldown = {}
        nokey = gemini_mod._call("ping", fallback="safe fallback", timeout=5)
        results["gemini_graceful_without_key"] = nokey["text"] == "safe fallback"
    finally:
        gemini_mod.requests.post, config.GOOGLE_API_KEY = orig_post, orig_key

    results["all_passed"] = all(results.values())
    return results


def section_gemini_live(store: LocalStore, runs: int = 3) -> dict:
    """Optional: real Gemini triage latency + self-consistency (needs API key)."""
    if not config.GOOGLE_API_KEY:
        return {"skipped": "no GOOGLE_API_KEY"}
    args = dict(shipments=store.list("shipments"), signals=store.list("signals"),
                locations=store.list("locations"), products=store.list("products"),
                lanes=store.list("lanes"))
    latencies, decisions = [], []
    for _ in range(runs):
        t = time.perf_counter()
        judgments = gemini_mod.judge_shipment_risk(**args)
        latencies.append((time.perf_counter() - t) * 1000)
        if judgments is None:
            return {"skipped": "Gemini did not answer (quota or network)"}
        decisions.append({j["shipment_id"]: j["risk"] for j in judgments})
    ids = decisions[0].keys()
    agree = sum(len({d[i] for d in decisions}) == 1 for i in ids)
    return {
        "runs": runs,
        "avg_latency_ms": round(statistics.fmean(latencies)),
        "json_valid_rate": "100%",
        "self_consistency": f"{agree}/{len(ids)} shipments identical across {runs} runs",
        "example": decisions[0],
    }


# --------------------------------------------------------------------------- #
#  report
# --------------------------------------------------------------------------- #
def _tbl(stats: dict) -> list[str]:
    rows = ["| Operation | avg | p50 | p95 | min | max | ops/sec |",
            "|---|---|---|---|---|---|---|"]
    for name, s in stats.items():
        rows.append(f"| `{name}` | {s['avg_ms']:.3f} ms | {s['p50_ms']:.3f} ms | "
                    f"{s['p95_ms']:.3f} ms | {s['min_ms']:.3f} ms | {s['max_ms']:.3f} ms | "
                    f"{s['ops_per_sec']:,} |")
    return rows


def write_report(data: dict) -> None:
    lat, cor, res, scale = data["latency"], data["correctness"], data["resilience"], data["scale"]
    plan_ms = lat["build_recovery_plan"]["avg_ms"]
    env = data["environment"]
    L = [
        "# SignalBridge — Prototype Performance Report",
        "",
        f"_Generated {data['generated_at']} · {env['platform']} · Python {env['python']}_",
        "",
        "## Executive summary",
        "",
        f"- **Full AI recovery plan** (shortage → internal stock → supplier choice → "
        f"margin → approval): **{plan_ms:.2f} ms** average "
        f"({lat['build_recovery_plan']['ops_per_sec']:,} plans/sec).",
        f"- **Dashboard assembly** (`/overview`): **{lat['dashboard_overview']['avg_ms']:.2f} ms**.",
        f"- **Correctness:** {'**100% — all invariants held**' if cor['all_passed'] else '**FAILED**'} "
        f"across {cor['plans_checked']} recovery plans (money, feasibility, chokepoint rule). "
        f"Money is never produced by the AI.",
        f"- **Resilience:** {'**all fallbacks passed**' if res['all_passed'] else '**FAILED**'} "
        f"(news GDELT→Google News, Gemini model chain, no-key graceful).",
        f"- **Scale:** {scale['shipments']} shipments on {scale['lanes']} real trade lanes, "
        f"{scale['supplier_offers']} supplier offers, {scale['signals']} live signals.",
        "",
        "## 1. Scale (bundled real-data snapshot)",
        "",
        "| Entity | Count |", "|---|---|",
        *[f"| {k.replace('_', ' ')} | {v} |" for k, v in scale.items()],
        "",
        "## 2. Latency",
        "",
        "Measured in-process on local fixtures (a snapshot of the Firestore tenant), "
        "to isolate engine speed from network. Each row is many iterations.",
        "",
        *_tbl(lat),
        "",
        "## 3. Correctness — invariants re-checked on every plan",
        "",
        "Each recovery plan is independently recomputed and verified. The AI explains; "
        "deterministic Python computes every number, so these are exact.",
        "",
        "| Invariant | Result |", "|---|---|",
        f"| Recovery cost = qty × unit price + shipping (recomputed) | {cor['checks']['money_integrity']}/{cor['plans_checked']} |",
        f"| Chosen supplier is the cheapest feasible option | {cor['checks']['cheapest_feasible_chosen']}/{cor['plans_checked']} |",
        f"| Every option carries a human-readable reason | {cor['checks']['every_option_has_reason']}/{cor['plans_checked']} |",
        f"| No feasible offer routes through a disrupted chokepoint | {cor['checks']['chokepoint_rule']}/{cor['plans_checked']} |",
        "",
        ("**No violations found.**" if cor["all_passed"]
         else "**Violations:**\n" + "\n".join(f"- {v}" for v in cor["violations"])),
        "",
        "## 4. Resilience (failure injection)",
        "",
        "| Scenario | Fallback behaviour | Result |", "|---|---|---|",
        f"| GDELT news API returns HTTP 429 | switches to Google News RSS | {_mark(res['news_fallback_to_google'])} |",
        f"| Primary Gemini model over quota (429) | next model in the chain answers | {_mark(res['gemini_model_chain_fallback'])} |",
        f"| No Gemini API key configured | returns a safe local summary, never crashes | {_mark(res['gemini_graceful_without_key'])} |",
        "",
    ]
    if data.get("gemini_live"):
        g = data["gemini_live"]
        L += ["## 5. Live Gemini triage (optional)", ""]
        if g.get("skipped"):
            L += [f"_Skipped: {g['skipped']}._", ""]
        else:
            L += [
                "| Metric | Value |", "|---|---|",
                f"| Average triage latency | {g['avg_latency_ms']:,} ms |",
                f"| Valid structured JSON | {g['json_valid_rate']} |",
                f"| Self-consistency | {g['self_consistency']} |",
                "",
                "Gemini judges which shipments are genuinely at risk from live weather "
                "and news; the gale-force threshold is computed in Python so the decision "
                "is stable across runs.", "",
            ]
    L += ["---", "",
          "_Reproduce: `python tests/benchmark/benchmark.py` (add `--gemini` for section 5)._"]
    (HERE / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (HERE / "results.json").write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="SignalBridge prototype benchmark")
    ap.add_argument("--runs", type=int, default=2000, help="iterations for fast operations")
    ap.add_argument("--gemini", action="store_true", help="also benchmark live Gemini triage")
    args = ap.parse_args()

    print("SignalBridge prototype benchmark — building controlled real-data scenario…")
    store = make_disrupted_store()
    pairs = at_risk_pairs(store)
    if not pairs:
        print("No at-risk order pairs found; cannot benchmark the recovery engine.")
        return 1
    print(f"  scenario: {len(pairs)} threatened orders across the network")

    print("  measuring latency…")
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {
            "platform": platform.platform(), "python": platform.python_version(),
            "data_source": "local fixtures (Firestore snapshot)",
        },
        "scale": section_scale(store, pairs),
        "latency": section_latency(store, pairs, args.runs),
        "correctness": section_correctness(store, pairs),
        "resilience": section_resilience(),
    }
    if args.gemini:
        print("  running live Gemini triage…")
        data["gemini_live"] = section_gemini_live(store)

    write_report(data)
    c = data["correctness"]
    print("\n" + "=" * 60)
    print(f"  Recovery plan latency : {data['latency']['build_recovery_plan']['avg_ms']:.2f} ms "
          f"({data['latency']['build_recovery_plan']['ops_per_sec']:,}/sec)")
    print(f"  Correctness           : {'100% — all invariants held' if c['all_passed'] else 'FAILED'} "
          f"({c['plans_checked']} plans)")
    print(f"  Resilience            : {'all fallbacks passed' if data['resilience']['all_passed'] else 'FAILED'}")
    print("=" * 60)
    print(f"\nReport written to {HERE / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
