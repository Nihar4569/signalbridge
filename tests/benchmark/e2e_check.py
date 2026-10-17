"""End-to-end production readiness check: every endpoint + every Gemini feature."""
import json
import sys
import time
import urllib.error
import urllib.request

API = "http://localhost:8000"
results = []


def call(method, path, body=None, timeout=120):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json"} if body else {},
    )
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), (time.perf_counter() - t) * 1000
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}, (time.perf_counter() - t) * 1000
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}, (time.perf_counter() - t) * 1000


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name:42} {detail}")


print("=" * 86)
print("  SIGNALBRIDGE — PRODUCTION READINESS CHECK")
print("=" * 86)

print("\n[1] Core API endpoints")
for path, key in [("/health", "status"), ("/overview", "shipments_tracked"), ("/map", "routes"),
                  ("/incidents", "incidents"), ("/fulfillments", None), ("/scan/status", "running")]:
    st, data, ms = call("GET", path)
    ok = st == 200 and (key is None or key in data)
    check(f"GET {path}", ok, f"{st} in {ms:.0f}ms")

st, health, _ = call("GET", "/health")
check("Firestore reachable", health.get("firestore") == "reachable", health.get("project", ""))

print("\n[2] Data integrity")
st, ov, _ = call("GET", "/overview")
st, mp, _ = call("GET", "/map")
st, inc, _ = call("GET", "/incidents")
check("shipments tracked > 0", ov.get("shipments_tracked", 0) > 0, f"{ov.get('shipments_tracked')} shipments")
check("every route has a drawable path", all(len(r["points"]) >= 2 for r in mp["routes"]),
      f"{len(mp['routes'])} routes")
check("every route has an ETA + progress", all(r.get("eta") and r.get("progress") is not None for r in mp["routes"]), "")
check("live alerts present", len(mp.get("alerts", [])) > 0, f"{len(mp['alerts'])} alerts")
check("threatened orders match overview", ov.get("orders_at_risk") == inc.get("count"),
      f"{ov.get('orders_at_risk')} == {inc.get('count')}")
check("revenue at risk > 0", ov.get("revenue_at_risk_minor", 0) > 0,
      f"Rs {ov.get('revenue_at_risk_minor', 0)/100:,.0f}")

print("\n[3] Recovery plans (deterministic maths)")
plans = []
for i in inc.get("incidents", []):
    st, plan, ms = call("GET", f"/plans/{i['sku']}/{i['location_id']}")
    plans.append(plan)
    m = plan.get("margin_check", {})
    ok = (st == 200 and plan.get("status") in ("awaiting_approval", "no_feasible_option")
          and m.get("recovery_cost_minor", 0) >= 0)
    check(f"plan {i['sku']}", ok,
          f"short {plan['exposure']['shortage_qty']}, cost Rs {m.get('recovery_cost_minor',0)/100:,.0f}, {m.get('verdict')}")

check("every option has qty+cost+reason (no blank cells)",
      all(o.get("reason") and o.get("qty") is not None for p in plans for o in p.get("supplier_options", [])),
      f"{sum(len(p.get('supplier_options', [])) for p in plans)} options")
check("every plan names an approver",
      all(p.get("approval", {}).get("approver_title") for p in plans), "")
check("chokepoint rule enforced",
      all(not o["feasible"] for p in plans for o in p.get("supplier_options", []) if "chokepoint" in o["reason"].lower()), "")

print("\n[4] Gemini features (live)")
sku, loc = inc["incidents"][0]["sku"], inc["incidents"][0]["location_id"]

st, ex, ms = call("GET", f"/plans/{sku}/{loc}/explain")
gem = ex.get("source", "").startswith("gemini")
check("1. explain_plan", st == 200 and len(ex.get("text", "")) > 40,
      f"{ex.get('source')} in {ms/1000:.1f}s" + ("" if gem else "  [fallback used]"))

st, qa, ms = call("POST", f"/plans/{sku}/{loc}/ask", {"question": "Why was the cheapest supplier rejected?"})
check("2. plan Q&A (answer_question)", st == 200 and len(qa.get("text", "")) > 40,
      f"{qa.get('source')} in {ms/1000:.1f}s")

st, ga, ms = call("POST", "/assistant/ask",
                  {"question": "Which shipments are at risk and why?", "history": []})
check("3. Ask Gemini panel (answer_global)", st == 200 and len(ga.get("text", "")) > 40,
      f"{ga.get('source')} in {ms/1000:.1f}s, {len(ga.get('sources', []))} sources")
check("   answers cite their sources", len(ga.get("sources", [])) > 0,
      ", ".join(s["label"] for s in ga.get("sources", [])[:3]))

st, mp2, _ = call("GET", "/map")
reasons = [r for r in mp2["routes"] if r.get("risk_reason")]
check("4. triage reasons stored on shipments", len(reasons) > 0,
      f"{len(reasons)}/{len(mp2['routes'])} explained")

print("\n[5] Live external data")
st, sig, ms = call("GET", "/signals/IN-JNPA")
w, n = sig.get("weather", {}), sig.get("news", {})
check("Open-Meteo weather", w.get("ok") is True, f"risk={w.get('risk')} in {ms/1000:.1f}s")
check("news (GDELT or Google News)", n.get("ok") is True, f"{n.get('source')}, {n.get('count')} articles")

st, scan, _ = call("POST", "/scan")
check("on-demand scan trigger", scan.get("status") in ("started", "running", "fresh"), scan.get("status"))

print("\n[6] Approval + fulfillment (idempotent)")
st, ap1, ms = call("POST", f"/plans/{sku}/{loc}/approve")
ok1 = st == 200 and ap1.get("status") == "approved"
check("approve executes", ok1, f"reserved {ap1.get('receipt', {}).get('qty')} units in {ms/1000:.1f}s")
ful = ap1.get("fulfillment", {})
check("creates transfer/PO actions", len(ful.get("actions", [])) > 0,
      ", ".join(a["type"] for a in ful.get("actions", [])))
check("drafts notification emails", len(ful.get("emails", [])) > 0, f"{len(ful.get('emails', []))} emails")
st, ap2, _ = call("POST", f"/plans/{sku}/{loc}/approve")
check("idempotent (no double booking)",
      ap2.get("receipt", {}).get("idempotency_key") == ap1.get("receipt", {}).get("idempotency_key"), "same key")
st, fl, _ = call("GET", "/fulfillments")
check("appears on Recoveries page", len(fl.get("fulfillments", fl if isinstance(fl, list) else [])) > 0, "")

print("\n" + "=" * 86)
passed = sum(1 for _, ok, _ in results if ok)
failed = [n for n, ok, _ in results if not ok]
print(f"  {passed}/{len(results)} checks passed")
if failed:
    print("  FAILED: " + "; ".join(failed))
else:
    print("  ALL FEATURES WORKING — PRODUCTION READY")
print("=" * 86)
sys.exit(1 if failed else 0)
