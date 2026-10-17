"""Independently recompute every at-risk plan from raw data and compare.

Deliberately does NOT import the app's planner/exposure/margin code: the math
here is written from first principles against the raw Firestore documents, so a
bug in the app cannot hide behind the same bug in the check.
"""
import sys
from datetime import datetime

sys.path.insert(0, "/Users/nihasahu/Desktop/WorkSpace/BuildX/signalbridge")
from backend.core.store import get_store  # noqa: E402

TIERS = [("local_planner", 5_000_000), ("regional_manager", 50_000_000), ("executive", None)]
INTERNAL_TYPES = ("dc", "dark_store")


def ts(v):
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


def money(minor):
    return f"Rs {minor/100:,.0f}"


s = get_store()
shipments = s.list("shipments")
orders = s.list("order_lines")
balances = s.list("stock_balances")
offers = s.list("supplier_offers")
products = {p["sku"]: p for p in s.list("products")}
partners = {p["partner_id"]: p for p in s.list("partners")}
locations = {loc["location_id"]: loc for loc in s.list("locations")}
lanes = {ln["lane_id"]: ln for ln in s.list("lanes")}
signals = s.list("signals")

# Chokepoints with a live disruptive signal (same definition the app uses).
KEYWORDS = ("strike", "closure", "closed", "suspended", "congestion", "blocked", "shutdown",
            "cyclone", "storm", "flood", "attack", "attacked", "drone", "missile", "seized",
            "diverted", "blockade")
disrupted_places = set()
for sig in signals:
    pay = sig.get("payload") or {}
    if sig.get("source") == "open-meteo":
        if pay.get("risk") == "high":
            disrupted_places.add(pay.get("location_id"))
    elif any(w in (sig.get("title") or "").lower() for w in KEYWORDS):
        disrupted_places.add(pay.get("location_id"))

blocked = {}
for sh in shipments:
    if sh.get("risk_zone") != "risk":
        continue
    for pt in (lanes.get(sh.get("lane_id")) or {}).get("points", []):
        pid = pt.get("location_id")
        if pid in disrupted_places and (locations.get(pid) or {}).get("type") == "sea_waypoint":
            blocked[pid] = locations[pid].get("name", pid)

pairs = sorted({(o["sku"], o["location_id"]) for o in orders if o.get("status") == "open"})
problems = []
checked = 0
total_revenue_at_risk = 0

print(f"Verifying {len(pairs)} SKU/location pairs against raw data\n" + "=" * 78)

for sku, loc in pairs:
    open_lines = [o for o in orders if o["sku"] == sku and o["location_id"] == loc and o.get("status") == "open"]
    deadline = min(ts(o["due_at"]) for o in open_lines)

    # --- demand: open units due on or before the deadline
    demand = sum(int(o["quantity"]) for o in open_lines if ts(o["due_at"]) <= deadline)

    # --- is this pair disrupted? (any at-risk shipment carrying this sku here)
    at_risk = any(
        sh.get("destination_location_id") == loc and sh.get("risk_zone") == "risk"
        and any(i.get("sku") == sku for i in sh.get("items", []))
        for sh in shipments
    )

    # --- supply: on hand + what arrives by the deadline
    on_hand = next((int(b["on_hand_qty"]) for b in balances
                    if b["sku"] == sku and b["location_id"] == loc), 0)
    incoming = 0
    for sh in shipments:
        if sh.get("destination_location_id") != loc or sh.get("status") not in ("in_transit", "planned"):
            continue
        arrival = sh.get("expected_arrival_at")
        if at_risk and sh.get("assumed_arrival_at"):
            arrival = sh["assumed_arrival_at"]
        if ts(arrival) > deadline:
            continue
        incoming += sum(int(i["quantity"]) for i in sh.get("items", []) if i.get("sku") == sku)

    supply = on_hand + incoming
    shortage = max(0, demand - supply)
    if shortage == 0:
        continue
    checked += 1

    # --- internal free stock elsewhere
    internal = []
    for b in balances:
        if b["sku"] != sku or b["location_id"] == loc:
            continue
        if (locations.get(b["location_id"]) or {}).get("type") not in INTERNAL_TYPES:
            continue
        free = int(b.get("on_hand_qty", 0)) - int(b.get("reserved_qty", 0))
        if free > 0:
            internal.append((b["location_id"], free))
    internal_free = sum(f for _, f in internal)
    internal_used = min(internal_free, shortage)
    remainder = shortage - internal_used

    # --- supplier options
    feasible = []
    for off in offers:
        if off["sku"] != sku or off.get("deliver_to_location_id") not in (None, loc):
            continue
        in_time = ts(off["delivery_latest"]) <= deadline
        enough = int(off["available_qty"]) >= remainder
        crosses = [blocked[i] for i in off.get("route_location_ids") or [] if i in blocked]
        if in_time and enough and not crosses and remainder > 0:
            feasible.append((off, remainder * int(off["unit_price_minor"]) + int(off["shipping_minor"])))
    feasible.sort(key=lambda x: x[1])
    chosen, cost = feasible[0] if feasible else (None, 0)
    recovered = internal_used + (remainder if chosen else 0)

    # --- money
    price = int(products.get(sku, {}).get("unit_price_minor", 0))
    protected = shortage * price
    penalty = sum(int(((partners.get(o.get("customer_id")) or {}).get("service_level") or {})
                      .get("penalty_per_late_order_minor", 0)) for o in open_lines if ts(o["due_at"]) <= deadline)
    net = protected + penalty - cost
    tier = next(t for t, ceil in TIERS if ceil is None or cost <= ceil)
    total_revenue_at_risk += protected

    # --- compare with the app
    from backend.domain import planner as planner_mod
    plan = planner_mod.build_plan(s, sku=sku, location_id=loc)
    exp, mar = plan["exposure"], plan["margin_check"]

    def check(label, mine, theirs):
        if mine != theirs:
            problems.append(f"{sku}@{loc}: {label} — independent {mine} vs app {theirs}")
        return "OK " if mine == theirs else "MISMATCH"

    print(f"\n{sku} @ {loc}   (deadline {str(deadline)[:10]}, disrupted={at_risk})")
    print(f"  demand {demand:>6}  = open order units due by deadline            {check('demand', demand, exp['demand_by_deadline'])}")
    print(f"  supply {supply:>6}  = on-hand {on_hand} + arriving {incoming}     {check('supply', supply, exp['supply_by_deadline'])}")
    print(f"  short  {shortage:>6}  = demand - supply                            {check('shortage', shortage, exp['shortage_qty'])}")
    print(f"  own stock used {internal_used:>5} of {internal_free} free          {check('internal_used', internal_used, plan['internal_used_qty'])}")
    print(f"  buy    {remainder:>6} from {chosen['offer_id'] if chosen else 'none':<18}      {check('chosen offer', chosen['offer_id'] if chosen else None, plan['selected_offer_id'])}")
    print(f"  cost   {money(cost):>14}                              {check('recovery cost', cost, mar['recovery_cost_minor'])}")
    print(f"  revenue protected {money(protected):>12}                {check('protected revenue', protected, mar['protected_revenue_minor'])}")
    print(f"  penalty avoided   {money(penalty):>12}                {check('penalty', penalty, mar['penalty_avoided_minor'])}")
    print(f"  net benefit       {money(net):>12}                {check('net benefit', net, mar['net_benefit_minor'])}")
    print(f"  verdict {'worth_it' if net > 0 else 'not_worth_it':<12}                        {check('verdict', 'worth_it' if net > 0 else 'not_worth_it', mar['verdict'])}")
    print(f"  recovered {recovered:>5} units                                 {check('recovered_qty', recovered, plan['recovered_qty'])}")
    print(f"  approver tier {tier:<18}                    {check('tier', tier, plan['approval']['tier'])}")

# dashboard total
from backend.app.routers import dashboard  # noqa: E402
ov = dashboard.overview(s)
print("\n" + "=" * 78)
print(f"Dashboard revenue at risk: app {money(ov['revenue_at_risk_minor'])} vs independent {money(total_revenue_at_risk)}", end="  ")
if ov["revenue_at_risk_minor"] != total_revenue_at_risk:
    problems.append(f"dashboard revenue {ov['revenue_at_risk_minor']} vs independent {total_revenue_at_risk}")
    print("MISMATCH")
else:
    print("OK")
print(f"Dashboard orders threatened: {ov['orders_at_risk']} vs independent {checked}", end="  ")
if ov["orders_at_risk"] != checked:
    problems.append(f"orders threatened {ov['orders_at_risk']} vs {checked}")
    print("MISMATCH")
else:
    print("OK")

print("\n" + "=" * 78)
if problems:
    print(f"{len(problems)} PROBLEM(S) FOUND:")
    for p in problems:
        print("  -", p)
else:
    print(f"ALL CALCULATIONS CORRECT — {checked} plans verified independently, 0 mismatches.")
