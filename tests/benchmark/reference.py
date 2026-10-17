"""Independent reference calculations for the benchmark's documented policy.

Only standard-library imports are allowed here. Do not call application domain
helpers or reuse the planner's amounts, feasibility flags or explanation text.
This is an oracle for the current sample-data policy, not real-world ground truth.
"""

import re
from datetime import datetime, timedelta, timezone

DISRUPTION_WORDS = (
    "strike",
    "closure",
    "closed",
    "suspended",
    "congestion",
    "blocked",
    "shutdown",
    "cyclone",
    "storm",
    "flood",
    "attack",
    "attacked",
    "drone",
    "missile",
    "seized",
    "diverted",
    "blockade",
)
APPROVAL_LIMITS = [("local_planner", 5_000_000), ("regional_manager", 50_000_000)]
MISSING = "<missing>"


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Benchmark timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def order_pairs(store):
    """Enumerate inputs, including covered orders, without consulting the planner."""
    return sorted(
        {
            (row["sku"], row["location_id"])
            for row in store.list("order_lines")
            if row.get("status") == "open"
        }
    )


def blocked_places(store, as_of):
    """Current route-safety policy, independently evaluated from source records.

    Policy: stored high-risk weather, or news within the trailing 72 hours,
    blocks a sea waypoint on a risk-flagged shipment. A cited cancellation can
    resolve that notice only, unless its text also describes an attack.
    """
    signals = {row["signal_id"]: row for row in store.list("signals")}
    sea = {
        row["location_id"] for row in store.list("locations") if row.get("type") == "sea_waypoint"
    }
    lanes = {row["lane_id"]: row for row in store.list("lanes")}
    result = set()
    for shipment in store.list("shipments"):
        if shipment.get("risk_zone") != "risk":
            continue
        assessment = shipment.get("risk_assessment") or {}
        cancelled = set()
        if assessment.get("event_status") == "cancelled":
            for citation in assessment.get("evidence", []):
                source = signals.get(citation.get("signal_id"), {})
                body = (source.get("payload") or {}).get("notice_text") or source.get("title", "")
                quote = citation.get("quote", "")
                if (
                    quote
                    and quote in body
                    and not any(
                        word in body.lower() for word in ("attack", "missile", "drone", "seized")
                    )
                    and re.search(
                        r"\b(cancelled|canceled|cancels|called off|lifted|reopened|resumed)\b",
                        quote,
                        re.IGNORECASE,
                    )
                ):
                    cancelled.add(citation["signal_id"])
        route = {
            point.get("location_id")
            for point in lanes.get(shipment.get("lane_id"), {}).get("points", [])
        }
        for signal_id, source in signals.items():
            payload = source.get("payload") or {}
            place = payload.get("location_id")
            if signal_id in cancelled or place not in sea.intersection(route):
                continue
            if source.get("source") == "open-meteo":
                disruptive = payload.get("risk") == "high"
            else:
                # The current application policy uses the lower age bound only.
                try:
                    current = timestamp(source["published_at"]) >= as_of - timedelta(hours=72)
                except (KeyError, ValueError, TypeError):
                    current = False
                disruptive = current and (
                    bool(payload.get("event_type"))
                    or any(word in source.get("title", "").lower() for word in DISRUPTION_WORDS)
                )
            if disruptive:
                result.add(place)
    return result


def expected_plan(store, sku, location_id, as_of):
    """Calculate expectations exclusively from input records and explicit policy."""
    orders = [
        row
        for row in store.list("order_lines")
        if row.get("sku") == sku
        and row.get("location_id") == location_id
        and row.get("status") == "open"
    ]
    if not orders:
        return {"status": "no_open_orders", "selected_offer_ids": {None}}
    deadline = min(timestamp(row["due_at"]) for row in orders)
    due = [row for row in orders if timestamp(row["due_at"]) <= deadline]
    demand = sum(int(row["quantity"]) for row in due)
    shipments = [
        row
        for row in store.list("shipments")
        if row.get("destination_location_id") == location_id
        and any(item.get("sku") == sku for item in row.get("items", []))
    ]
    disrupted = any(
        row.get("risk_zone") == "risk" or row.get("delay_state") == "confirmed_delayed"
        for row in shipments
    )
    balance = next(
        (
            row
            for row in store.list("stock_balances")
            if row.get("sku") == sku and row.get("location_id") == location_id
        ),
        {},
    )
    on_hand = int(balance.get("on_hand_qty", 0))

    def exposure(use_delayed):
        incoming = 0
        for row in shipments:
            if row.get("status") not in ("in_transit", "planned"):
                continue
            arrival = (row.get("assumed_arrival_at") if use_delayed else None) or row[
                "expected_arrival_at"
            ]
            if timestamp(arrival) <= deadline:
                incoming += sum(
                    int(item["quantity"]) for item in row.get("items", []) if item.get("sku") == sku
                )
        return {
            "deadline": deadline.isoformat(),
            "on_hand_qty": on_hand,
            "incoming_by_deadline": incoming,
            "demand_by_deadline": demand,
            "supply_by_deadline": on_hand + incoming,
            "shortage_qty": max(0, demand - on_hand - incoming),
            "scenario": "disrupted" if use_delayed else "baseline",
        }

    actual_exposure = exposure(disrupted)
    result = {
        "exposure": actual_exposure,
        "baseline_exposure": exposure(False),
        "selected_offer_ids": {None},
    }
    shortage = actual_exposure["shortage_qty"]
    if shortage == 0:
        return {**result, "status": "no_action_needed"}
    locations = {row["location_id"]: row for row in store.list("locations")}
    internal = {}
    for row in store.list("stock_balances"):
        donor = locations.get(row.get("location_id"), {})
        if (
            row.get("sku") != sku
            or row.get("location_id") == location_id
            or donor.get("type") not in ("dc", "dark_store")
            or not donor.get("active", True)
        ):
            continue
        free = int(row.get("on_hand_qty", 0)) - int(row.get("reserved_qty", 0))
        if free > 0:
            internal[row["location_id"]] = free
    internal_used = min(shortage, sum(internal.values()))
    remainder = shortage - internal_used
    blocked = blocked_places(store, as_of)
    options = {}
    for offer in store.list("supplier_offers"):
        if offer.get("sku") != sku or offer.get("deliver_to_location_id") not in (
            None,
            location_id,
        ):
            continue
        try:
            valid_quote = not offer.get("expires_at") or timestamp(offer["expires_at"]) > as_of
        except (ValueError, TypeError):
            valid_quote = False
        available = int(offer["available_qty"])
        feasible = bool(
            remainder > 0
            and valid_quote
            and available >= remainder
            and timestamp(offer["delivery_latest"]) <= deadline
            and not blocked.intersection(offer.get("route_location_ids") or [])
        )
        qty = remainder if feasible else min(available, remainder)
        options[offer["offer_id"]] = {
            "feasible": feasible,
            "qty": qty,
            "available_qty": available,
            "cost_minor": qty * int(offer["unit_price_minor"]) + int(offer["shipping_minor"])
            if qty > 0
            else None,
            "arrives_at": offer["delivery_latest"],
            "expires_at": offer.get("expires_at"),
        }
    candidates = {key: row for key, row in options.items() if row["feasible"]}
    cost = min(row["cost_minor"] for row in candidates.values()) if candidates else 0
    chosen = {key for key, row in candidates.items() if row["cost_minor"] == cost}
    recovered = internal_used + (remainder if candidates else 0)
    products = {row["sku"]: row for row in store.list("products")}
    partners = {row["partner_id"]: row for row in store.list("partners")}
    revenue = shortage * int(products.get(sku, {}).get("unit_price_minor", 0))
    penalty = sum(
        int(
            (partners.get(row.get("customer_id"), {}).get("service_level") or {}).get(
                "penalty_per_late_order_minor", 0
            )
        )
        for row in due
    )
    net = revenue + penalty - cost
    tier = next((name for name, ceiling in APPROVAL_LIMITS if cost <= ceiling), "executive")
    late = sum(
        int(item["quantity"])
        for row in shipments
        if row.get("risk_zone") == "risk"
        for item in row.get("items", [])
        if item.get("sku") == sku
    )
    surplus = min(late, recovered) if recovered > 0 else 0
    result.update(
        status="awaiting_approval" if candidates else "no_feasible_option",
        internal_options=internal,
        internal_used_qty=internal_used,
        supplier_options=options,
        selected_offer_ids=chosen or {None},
        supplier_qty=remainder if candidates else 0,
        recovered_qty=recovered,
        margin_check={
            "recovery_cost_minor": cost,
            "protected_revenue_minor": revenue,
            "penalty_avoided_minor": penalty,
            "net_benefit_minor": net,
            "verdict": "worth_it" if net > 0 else "not_worth_it",
        },
        approval={"tier": tier},
        surplus_forecast={
            "expected_surplus_qty": surplus,
            "suggested_action": "markdown" if surplus > 0 else None,
        },
    )
    return result


def validate_plan(store, sku, location_id, as_of, plan):
    """Return every actual comparison, including diagnostics for every failure."""
    expected = expected_plan(store, sku, location_id, as_of)
    comparisons = []

    def equal(want, got):
        # Python considers True == 1 and 20.0 == 20; the data contract does not.
        if isinstance(want, dict):
            return (
                isinstance(got, dict)
                and want.keys() == got.keys()
                and all(equal(value, got[key]) for key, value in want.items())
            )
        if isinstance(want, list):
            return (
                isinstance(got, list)
                and len(want) == len(got)
                and all(equal(a, b) for a, b in zip(want, got, strict=True))
            )
        if type(want) in (int, bool):
            return type(got) is type(want) and want == got
        return want == got

    def check(name, want, got):
        ok = equal(want, got)
        comparisons.append({"check": name, "passed": ok, "expected": want, "actual": got})

    check("status", expected["status"], plan.get("status", MISSING))
    for section in ("exposure", "baseline_exposure"):
        for field, want in expected.get(section, {}).items():
            check(f"{section}.{field}", want, (plan.get(section) or {}).get(field, MISSING))
    choice = plan.get("selected_offer_id")
    check("selected_offer_is_optimal", True, choice in expected["selected_offer_ids"])
    if "supplier_options" not in expected:
        check("no_unneeded_supplier_options", [], plan.get("supplier_options", []))
        check("no_unneeded_recovery_quantity", 0, plan.get("recovered_qty", 0))
        return comparisons
    for field in ("internal_used_qty", "supplier_qty", "recovered_qty"):
        check(field, expected[field], plan.get(field, MISSING))
    internal_rows = plan.get("internal_options", [])
    check("internal_option_count", len(expected["internal_options"]), len(internal_rows))
    check(
        "internal_stock",
        expected["internal_options"],
        {row.get("location_id"): row.get("free_qty") for row in internal_rows},
    )
    rows = plan.get("supplier_options", [])
    actual_options = {row.get("offer_id"): row for row in rows}
    check("supplier_option_count", len(expected["supplier_options"]), len(rows))
    check(
        "supplier_option_ids",
        sorted(expected["supplier_options"]),
        sorted(str(key) for key in actual_options),
    )
    for offer_id, want in expected["supplier_options"].items():
        got = actual_options.get(offer_id, {})
        for field, value in want.items():
            check(f"offer.{offer_id}.{field}", value, got.get(field, MISSING))
        check(
            f"offer.{offer_id}.reason_present",
            True,
            isinstance(got.get("reason"), str) and bool(got["reason"].strip()),
        )
    for section in ("margin_check", "approval", "surplus_forecast"):
        for field, want in expected[section].items():
            check(f"{section}.{field}", want, (plan.get(section) or {}).get(field, MISSING))
    return comparisons
