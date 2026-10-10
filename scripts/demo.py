"""Show the recovery decision the app would make on the current data.

No API key. Uses whatever DATA_BACKEND points at (local fixtures or Firestore).

    python -m scripts.demo

A recovery plan is built only when a shipment's risk_zone is already "risk"
(set by triage from a weather or news signal). Otherwise the order is covered.
"""
from __future__ import annotations

from backend.core.store import get_store
from backend.domain import planner as planner_mod

SKU = "JACKET-BLUE-M"
LOCATION = "WH-MUM"


def rupees(minor: int) -> str:
    return f"\u20b9{minor / 100:,.0f}"


def main() -> None:
    store = get_store()

    print("=" * 64)
    print(f"  SignalBridge demo  -  {SKU} @ {LOCATION}")
    print("=" * 64)

    plan = planner_mod.build_plan(store, sku=SKU, location_id=LOCATION)
    picture = plan.get("exposure") or {}
    print(f"\nDeadline: {picture.get('deadline')}")
    print(f"  Supply {picture.get('supply_by_deadline')}  "
          f"demand {picture.get('demand_by_deadline')}  "
          f"shortage {picture.get('shortage_qty')}")

    print("\n--- Building recovery plan ---")
    if plan.get("status") == "no_action_needed":
        print("  No shipment is marked risk. Nothing to buy.")
        print(f"  Shortage            : {plan['exposure']['shortage_qty']}")
        print("\nDone.")
        return

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
