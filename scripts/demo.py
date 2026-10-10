"""The 60-second demo. Runs the whole recovery loop on the bundled fixtures.

No cloud, no API key, no internet. Just:
    python -m scripts.demo

It proves the core idea: a port delay turns a healthy order into an 80-unit
shortage, and SignalBridge finds a governed recovery plan.
"""
from __future__ import annotations

from backend.core.store import get_store
from backend.domain import exposure as exposure_mod
from backend.domain import planner as planner_mod

SKU = "JACKET-BLUE-M"
LOCATION = "WH-MUM"


def rupees(minor: int) -> str:
    return f"\u20b9{minor / 100:,.0f}"


def main() -> None:
    store = get_store()
    order_lines = store.list("order_lines")
    shipments = store.list("shipments")
    deadline = planner_mod._earliest_deadline(order_lines, SKU, LOCATION)
    on_hand = next(
        int(b["on_hand_qty"])
        for b in store.list("stock_balances")
        if b["sku"] == SKU and b["location_id"] == LOCATION
    )

    print("=" * 64)
    print(f"  SignalBridge demo  -  {SKU} @ {LOCATION}")
    print("=" * 64)

    baseline = exposure_mod.assess_exposure(
        sku=SKU, location_id=LOCATION, deadline=deadline, on_hand_qty=on_hand,
        shipments=shipments, order_lines=order_lines, scenario="baseline",
    )
    disrupted = exposure_mod.assess_exposure(
        sku=SKU, location_id=LOCATION, deadline=deadline, on_hand_qty=on_hand,
        shipments=shipments, order_lines=order_lines, scenario="disrupted",
    )

    print(f"\nDeadline: {baseline['deadline']}")
    print(f"  Normal    : supply {baseline['supply_by_deadline']:>4}  "
          f"demand {baseline['demand_by_deadline']:>4}  "
          f"shortage {baseline['shortage_qty']:>4}")
    print(f"  Disrupted : supply {disrupted['supply_by_deadline']:>4}  "
          f"demand {disrupted['demand_by_deadline']:>4}  "
          f"shortage {disrupted['shortage_qty']:>4}  <-- port delay")

    print("\n--- Building recovery plan ---")
    plan = planner_mod.build_plan(store, sku=SKU, location_id=LOCATION)

    print(f"  Internal stock used : {plan['internal_used_qty']} units")
    print(f"  Chosen supplier     : {plan['selected_offer_id']}")
    print(f"  Total recovered     : {plan['recovered_qty']} / "
          f"{plan['exposure']['shortage_qty']} units")
    m = plan["margin_check"]
    print(f"  Recovery cost       : {rupees(m['recovery_cost_minor'])}")
    print(f"  Revenue protected   : {rupees(m['protected_revenue_minor'])}")
    print(f"  Verdict             : {m['verdict']}")
    s = plan["surplus_forecast"]
    print(f"  Future surplus      : {s['expected_surplus_qty']} units "
          f"(action: {s['suggested_action']})")
    print(f"  Needs approval from : {plan['approval']['tier']}")

    print("\nNarrative:")
    print(f"  {plan['narrative']}")
    print("\nDone. No stock was really bought - this is a simulation.")


if __name__ == "__main__":
    main()
