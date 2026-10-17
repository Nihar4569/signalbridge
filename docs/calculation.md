# Recovery calculations

Authoritative quantities and money are calculated in Python. Gemini interprets evidence and explains results; it does not supply the planner's financial arithmetic.

The reproducible example below uses [decision_demo/cases.json](../fixtures/decision_demo/cases.json) at its fixed scenario clock, **17 October 2026, 09:00 UTC**. It is synthetic and separate from changing operational fixtures.

## 1. Deadline-based exposure

The planner uses the earliest open order deadline for one SKU/location pair.

```text
supply_by_deadline = destination_on_hand + incoming_arriving_by_deadline
demand_by_deadline = open_order_quantity_due_by_deadline
shortage = max(0, demand_by_deadline - supply_by_deadline)
```

[Exposure code](../backend/domain/exposure.py) includes planned/in-transit incoming shipments. When the pair is in a disrupted scenario, supplied assumed-arrival values replace expected arrivals where present. The planner selects that scenario when a relevant shipment is marked risk or confirmed delayed.

This is a SKU/location scenario calculation, not a full remaining-leg simulator. Destination exposure uses on-hand directly, without subtracting `reserved_qty`. Do not describe it as complete net available-to-promise allocation.

### Coffee walkthrough

| Input | Value |
|---|---|
| Demand | 100 units due 19 October 2026, 12:00 UTC |
| Destination on-hand | 20 units |
| Inbound shipment | 80 units, expected 18 October |
| Declared disrupted arrival | 21 October |
| Internal stock at another DC | 20 on-hand, zero reserved |

Baseline supply is 20 + 80 = 100, so shortage is zero. Under the active closure's declared delay scenario, inbound supply misses the deadline: supply is 20 and shortage is **80**.

A validated cancelled-strike interpretation leaves the expected arrival available in this example. Shortage remains zero. This conclusion concerns the supplied notice, not every possible real-world risk.

## 2. Internal availability

[Internal balancing](../backend/domain/network_balance.py) searches other active DC/dark-store locations for the SKU:

```text
free = on_hand - reserved
internal_used = min(shortage, sum(positive_internal_free))
external_remainder = shortage - internal_used
```

Options default to largest free quantity first. Distance can be calculated; the main planner does not select a globally optimal transport plan.

In the example: 80 short - 20 internal = **60 units** still needed.

On-hand minus reserved does not establish donor surplus after donor demand. Transfer permissions, transit time/cost and coordinated allocation across simultaneous plans are not fully enforced. If internal stock alone covers the shortage, the current planner can still return `no_feasible_option` because approval expects an external offer. Internal-only execution remains planned.

## 3. Supplier feasibility and selection

[The planner](../backend/domain/planner.py) considers offers for the SKU and matching destination (or no destination restriction). A selected offer must:

- Cover the entire external remainder with its stated capacity.
- Have `delivery_latest` on or before the earliest deadline.
- Have no expired/invalid supplied expiry. An absent expiry is currently allowed.
- Avoid identified disrupted sea waypoints from at-risk shipment lanes and stored disruptive signals.

This is a modeled chokepoint check, not proof that every segment of every supplier route is safe. The planner selects one cheapest feasible offer; it does not combine several partial supplier offers.

```text
external_cost_minor = external_quantity * unit_price_minor + shipping_minor
```

The direct coffee offer costs ₹60 per unit plus ₹100 shipping:

```text
60 * 6,000 + 10,000 = 370,000 paise = ₹3,700
```

The cheaper sea offer is rejected in the active-closure case because it crosses the disrupted fictional passage. Quote validity uses the fixed scenario clock in the walkthrough, not the date the browser is opened.

## 4. Estimated recovery benefit

[The benefit check](../backend/domain/margin.py) is:

```text
revenue_exposed = shortage * product_sell_price
estimated_benefit = revenue_exposed + potential_penalty - external_recovery_cost
worth_it = estimated_benefit > 0
```

For coffee: 80 * ₹100 + ₹0 - ₹3,700 = **₹4,300 estimated benefit**.

This is not profit or contribution margin. It does not subtract all original acquisition, transfer, handling or opportunity costs. In partial-recovery cases it still uses the full shortage in the revenue estimate. Treat the figure as a review aid under the stated policy, not realized savings.

The planner's potential penalty sums configured per-late-order amounts for matching open lines due by the earliest deadline. It is not a legal determination that a penalty is owed.

## 5. Illustrative surplus

[Surplus code](../backend/domain/surplus.py) calculates:

```text
expected_surplus = min(late_shipment_units, recovered_qty)
```

It returns zero when the original is not still arriving or recovery is zero. The main planner passes `original_still_arriving=True` and counts units on risk-flagged shipments. The coffee example therefore flags **80 units** and suggests a markdown.

This is a heuristic warning, not a demand forecast, predicted delivery confirmation or automatic markdown action.

## 6. Governance

[Governance](../backend/domain/governance.py) maps external recovery cost to configured tiers:

| Cost | Tier | Intended approver |
|---|---|---|
| Up to ₹50,000 | local_planner | Warehouse Operations Manager |
| Above ₹50,000 through ₹5,00,000 | regional_manager | Regional Supply Chain Manager |
| Above ₹5,00,000 | executive | Head of Supply Chain |

The coffee proposal maps to the local tier. The API checks for a selected supplier and positive benefit on approval, but does not verify the caller's identity/role. See [approval](after_plan_approval.md).

## Reproduce and interpret

Use **Reference replay** at `/#/decision-demo` for the fixed example. It passes an authored interpretation through validation, triage and planning without a model call. Live Gemini mode uses the same case but its actual interpretation must be inspected.

`DATA_BACKEND=local python -m scripts.demo` instead reads the current operational jacket records. Its outcome can be no action needed and is not guaranteed to match any older jacket example.

See the [offline benchmark](../tests/benchmark/README.md) for independent checks of the declared sample-data policy. Passing those checks does not remove the modeling limitations above.
