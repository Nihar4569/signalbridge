"""The planner assembles a full recovery plan from the smaller domain pieces.

Flow for one SKU at one location:
  1. exposure   -> how many units short by the deadline
  2. internal   -> use our own free stock first
  3. supplier   -> buy the remainder from the cheapest feasible offer
  4. margin     -> is the whole thing worth it?
  5. surplus    -> will the late shipment create overstock later?
  6. governance -> who must approve it?

Everything here is deterministic. The AI agent calls this; it does not replace it.
"""
from __future__ import annotations

from . import exposure as exposure_mod
from . import governance as governance_mod
from . import margin as margin_mod
from . import network as network_mod
from . import network_balance as nb_mod
from . import surplus as surplus_mod


def _earliest_deadline(order_lines: list[dict], sku: str, location_id: str):
    opens = [
        line
        for line in order_lines
        if line.get("sku") == sku
        and line.get("location_id") == location_id
        and line.get("status") == "open"
    ]
    if not opens:
        return None
    return min(exposure_mod.parse_ts(line["due_at"]) for line in opens)


def _delayed_units(shipments: list[dict], sku: str, location_id: str) -> int:
    """Units on shipments triage has marked risk for this SKU/location."""
    total = 0
    for shipment in shipments:
        if shipment.get("destination_location_id") != location_id:
            continue
        if shipment.get("risk_zone") != "risk":
            continue
        for item in shipment.get("items", []):
            if item.get("sku") == sku:
                total += int(item["quantity"])
    return total


def _disrupted_chokepoints(shipments, lanes, locations, signals) -> dict[str, str]:
    """Chokepoints delaying our shipments right now: {location_id: name}.

    A sea waypoint counts when it is on an at-risk shipment's lane AND has a live
    disruptive signal (high-risk weather or a news report) at that place.
    """
    sea = {loc["location_id"]: loc for loc in locations if loc.get("type") == "sea_waypoint"}
    disrupted = {(s.get("payload") or {}).get("location_id") for s in signals if network_mod.is_disruptive(s)}
    found: dict[str, str] = {}
    for shipment in shipments:
        if shipment.get("risk_zone") != "risk":
            continue
        for point in (lanes.get(shipment.get("lane_id")) or {}).get("points", []):
            place = point.get("location_id")
            if place in sea and place in disrupted:
                found[place] = sea[place].get("name", place)
    return found


def _penalty_at_risk(order_lines, partners, sku, location_id) -> int:
    """Sum of late-delivery penalties for affected VIP/SLA customers."""
    partner_by_id = {p["partner_id"]: p for p in partners}
    penalty = 0
    for line in order_lines:
        if line.get("sku") != sku or line.get("location_id") != location_id:
            continue
        if line.get("status") != "open":
            continue
        partner = partner_by_id.get(line.get("customer_id"), {})
        service = partner.get("service_level") or {}
        penalty += int(service.get("penalty_per_late_order_minor", 0))
    return penalty


def build_plan(store, *, sku: str, location_id: str) -> dict:
    """Produce a complete recovery plan dict for one SKU at one location."""
    products = {p["sku"]: p for p in store.list("products")}
    shipments = store.list("shipments")
    order_lines = store.list("order_lines")
    stock_balances = store.list("stock_balances")
    locations = store.list("locations")
    offers = store.list("supplier_offers")
    partners = store.list("partners")

    product = products.get(sku, {})
    balance = next(
        (b for b in stock_balances if b["sku"] == sku and b["location_id"] == location_id),
        None,
    )
    on_hand = int(balance["on_hand_qty"]) if balance else 0

    deadline = _earliest_deadline(order_lines, sku, location_id)
    if deadline is None:
        return {"sku": sku, "location_id": location_id, "status": "no_open_orders"}

    # Delayed arrival is used only after triage sets risk_zone from a live signal.
    scenario = "disrupted" if exposure_mod.is_disrupted(shipments, sku, location_id) else "baseline"
    exposure = exposure_mod.assess_exposure(
        sku=sku,
        location_id=location_id,
        deadline=deadline,
        on_hand_qty=on_hand,
        shipments=shipments,
        order_lines=order_lines,
        scenario=scenario,
    )
    # The "nothing went wrong" picture, so the UI can show before vs after.
    baseline_exposure = exposure_mod.assess_exposure(
        sku=sku,
        location_id=location_id,
        deadline=deadline,
        on_hand_qty=on_hand,
        shipments=shipments,
        order_lines=order_lines,
        scenario="baseline",
    )
    shortage = exposure["shortage_qty"]
    if shortage == 0:
        return {
            "sku": sku,
            "location_id": location_id,
            "status": "no_action_needed",
            "exposure": exposure,
            "baseline_exposure": baseline_exposure,
        }

    # Step 2: use our own free internal stock first.
    internal = nb_mod.find_internal_surplus(
        sku=sku,
        exclude_location_id=location_id,
        stock_balances=stock_balances,
        locations=locations,
        origin_location_id=location_id,
    )
    internal_free = sum(option["free_qty"] for option in internal)
    internal_used = min(internal_free, shortage)
    remainder = shortage - internal_used

    # Step 3: cheapest feasible supplier offer for the remainder. An offer that
    # sails through a chokepoint that is already delaying our shipments is no rescue.
    lanes = {lane["lane_id"]: lane for lane in store.list("lanes")}
    blocked = _disrupted_chokepoints(shipments, lanes, locations, store.list("signals"))
    options: list[dict] = []
    for offer in offers:
        if offer.get("sku") != sku:
            continue
        if offer.get("deliver_to_location_id") not in (None, location_id):
            continue
        in_time = exposure_mod.parse_ts(offer["delivery_latest"]) <= deadline
        enough = int(offer["available_qty"]) >= remainder
        crosses = [blocked[i] for i in offer.get("route_location_ids") or [] if i in blocked]
        feasible = in_time and enough and not crosses and remainder > 0
        cost = (
            remainder * int(offer["unit_price_minor"]) + int(offer["shipping_minor"])
            if feasible
            else None
        )
        if feasible:
            reason = "Covers the remaining units before the deadline."
        elif crosses:
            reason = f"Routes through a chokepoint that is delaying our shipments ({', '.join(crosses)})."
        elif not in_time:
            reason = "Arrives after the deadline."
        else:
            reason = "Not enough stock."
        options.append(
            {
                "offer_id": offer["offer_id"],
                "supplier_id": offer.get("supplier_id"),
                "ships_from": offer.get("ships_from"),
                "mode": offer.get("mode"),
                "route": offer.get("route"),
                "qty": remainder if feasible else 0,
                "cost_minor": cost,
                "arrives_at": offer["delivery_latest"],
                "feasible": feasible,
                "reason": reason,
            }
        )

    feasible_options = [o for o in options if o["feasible"]]
    feasible_options.sort(key=lambda o: o["cost_minor"])
    chosen = feasible_options[0] if feasible_options else None
    recovery_cost = chosen["cost_minor"] if chosen else 0
    recovered_qty = internal_used + (remainder if chosen else 0)

    # Step 4: margin.
    penalty = _penalty_at_risk(order_lines, partners, sku, location_id)
    margin = margin_mod.assess_margin(
        shortage_qty=shortage,
        unit_price_minor=int(product.get("unit_price_minor", 0)),
        recovery_cost_minor=recovery_cost,
        penalty_at_risk_minor=penalty,
    )

    # Step 5: surplus.
    surplus = surplus_mod.forecast_surplus(
        late_shipment_units=_delayed_units(shipments, sku, location_id),
        recovery_qty=recovered_qty,
        original_still_arriving=True,
    )

    # Step 6: governance (plain rules: cost -> tier -> default approver).
    approval = governance_mod.route_approval(recovery_cost)

    narrative = (
        f"{shortage} units of {sku} are uncovered at {location_id} by "
        f"{deadline.date()}. Used {internal_used} from internal stock; "
        f"{'bought ' + str(remainder) + ' from ' + chosen['offer_id'] if chosen else 'no feasible supplier found for the remainder'}"
        f". Recovery cost ₹{recovery_cost / 100:,.0f}; "
        f"verdict: {margin['verdict']}. Approval: {approval['approver_title']}."
    )

    return {
        "sku": sku,
        "location_id": location_id,
        "status": "awaiting_approval" if chosen else "no_feasible_option",
        "exposure": exposure,
        "baseline_exposure": baseline_exposure,
        "internal_options": internal,
        "internal_used_qty": internal_used,
        "supplier_options": options,
        "selected_offer_id": chosen["offer_id"] if chosen else None,
        "recovered_qty": recovered_qty,
        "margin_check": margin,
        "surplus_forecast": surplus,
        "approval": approval,
        "narrative": narrative,
        "version": 1,
    }
