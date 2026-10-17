# Data contract and persistence

The data contract supports retail recovery planning without asking the model to calculate authoritative numbers. This page describes implemented storage and response shapes, then identifies schema-only and planned work.

Source contracts: [collection models](../backend/models/collections.py), [IDs](../backend/models/ids.py), [decision models](../backend/models/decision.py) and [store implementations](../backend/core/store.py).

## 1. Representation rules

- Quantities are whole units. Business money calculations use integer minor units and a currency code; the current examples/UI use INR and paise.
- Timestamps should be timezone-qualified ISO-8601 values. The application normally emits UTC.
- Derived availability is calculated, not a separately maintained `free_to_use` field.
- Stored stock totals and shipment/order records are inputs. Calculated exposure/plan views are derived results, not a stock ledger.
- Models reserve fields for future work. Field presence does not establish an implemented workflow.
- Some records have `version`, but current writes do not implement universal optimistic locking or automatic version increments.
- The operational tenant is selected by server configuration, not by authenticated per-user membership.

## 2. Store modes

| Store | Reads | Writes and lifetime |
|---|---|---|
| `LocalStore` | JSON in `fixtures/`, cached within the process. | In-memory overlay. Runtime writes do not change fixture files and disappear after restart. |
| `SnapshotStore` | Deep copy of explicitly supplied collections. Missing collections remain empty. | Private memory only. Used by the decision walkthrough and offline benchmark. |
| `FirestoreStore` | `tenants/{TENANT_ID}/{collection}/{doc_id}`. Collection reads have a 15-second process-local cache. | Document `set`/`delete`, cache invalidation and batched seeding. Runtime approval writes are not one cross-document transaction. |

A materialized snapshot used by the decision brief gives subsequent calculations a stable private input set and clock. It is not an atomic snapshot read across Firestore collections.

## 3. Collection inventory

There are 15 modeled collection types. Nine are included in `SEED_COLLECTIONS`. Runtime behavior is narrower than the complete model inventory.

| Collection | Key / important fields | Current behavior |
|---|---|---|
| `products` | `sku`, price/cost in minor units, currency, product metadata. | Seed/read. Perishable/substitution fields do not implement rescue or substitution logic. |
| `locations` | `location_id`, type, coordinates, active, aliases, transfer metadata. | Seed/read. Types include dc, dark_store, store, port, supplier_site and sea_waypoint. Transfer permissions are not a complete planner constraint. |
| `partners` | `partner_id`, roles, email, service-level metadata. | Seed/read. Late-penalty amounts are used; VIP allocation is not implemented. |
| `lanes` | `lane_id`, endpoints, `points[]`, `legs[]`. | Seed/read for routes and interpretation. Remaining-leg timing is not a complete model. |
| `stock_balances` | `{location_id}__{sku}`, on_hand, reserved, incoming, outgoing, version. | Seed/read. Current approval does not reserve donor balances or maintain these buckets transactionally. |
| `order_lines` | `line_id`, SKU/location, quantity, due_at, status, coverage fields. | Seed/read. Coverage fields exist but approval does not update them in the operational store. |
| `shipments` | `shipment_id`, items, lane, expected/assumed/confirmed arrivals, risk flags, assessment. | Seed/read. Triage writes risk/assessment metadata. Stored arrival assumptions are not carrier telemetry or AI-predicted ETAs. |
| `supplier_offers` | `offer_id`, supplier, SKU, capacity, price/shipping, expiry, latest delivery, route IDs. | Seed/read. Feasibility is calculated; the simulator does not decrement capacity. |
| `events` | `event_id`, structured what/when/where/why and verification metadata. | Seeded model/data. The current scan does not create a full validated event-revision chain. |
| `signals` | `signal_id`, source, URL, title, timestamps, payload. | Worker ingestion upserts successful readings/news. See below. |
| `exposures` | `EXP-{sku}__{location_id}`, deadline, supply, demand, shortage, risk and affected line IDs. | Triage upserts one current result per pair; recomputation overwrites it. Not immutable history. |
| `plans` | `PLAN-{sku}-{location_id}` fallback ID, calculated proposal and approved status. | Calculated on read. Reservation saves an approved plan. Worker-generated candidates are built/logged, not all saved. |
| `operations` | Deterministic operation ID, idempotency key, supplier quantity, receipt, status. | Reservation saves a succeeded simulated operation. There is no atomic pending/claim/execution state machine. |
| `allocations` | `line_id`, claims, version. | Model/ID contract exists. Current approval does not write allocation claims. |
| `stock_movements` | `movement_id`, delta, bucket, reason and reference. | Model/ID contract exists. Current approval does not append a stock ledger. |

Dashboard helpers also accept an optional `alerts` collection. It has an ID mapping, but is not one of the 15 collection models or the nine standard seed collections. The map also derives alerts from signals.

## 4. Signals and assessments

Weather signal IDs are `SIG-WEATHER-{location_id}`: a successful refresh replaces the previous reading for that place. News IDs are `SIG-NEWS-{URL SHA-1 prefix}`; repeated URLs overwrite the corresponding record. News `raw_hash` hashes the URL, not a complete article body.

The weather payload includes location, summarized risk and forecast metrics. News payloads include location and provider metadata. Normal news evidence is a headline, not a downloaded full article. The synthetic walkthrough supplies explicit `notice_text`.

Current ingestion sets `ttl_at` to null. It does not configure retention or populate expiry timestamps. Configuring a future TTL policy requires a suitable timestamp field and cloud setup; TTL deletes have separate billing, not free usage. See [Firestore quotas](https://firebase.google.com/docs/firestore/quotas).

A shipment's `risk_assessment` can contain:

```text
status: affected | unaffected | unknown
event_status: active | planned | cancelled | none | uncertain
reason
evidence: [{signal_id, quote}]
unresolved_fields
source, assessed_at
last_attempt_status, last_attempt_at
policy_override, policy_evidence_ids
```

Backend code assigns source/time metadata. A failed latest attempt preserves earlier evidence/risk and records unknown latest-attempt status. A structured unknown result preserves the earlier risk flag while exposing the new uncertainty. See [AI validation](agents.md).

The stored exposure's `event_id` is currently null, and its penalty field is zero in the triage writer. The planner calculates applicable penalty estimates separately. Do not infer a complete event/profit audit chain from the existence of those model fields.

## 5. Calculated plan contract

The runtime planner returns plain dictionaries. A proposal can include:

- `status`: no_open_orders, no_action_needed, awaiting_approval or no_feasible_option.
- `exposure` and `baseline_exposure`.
- `internal_options`, `internal_used_qty`.
- `supplier_options`, `selected_offer_id`, `supplier_qty`.
- `recovered_qty`, `margin_check`, `surplus_forecast`, `approval`, `narrative`, `version`.

Availability, offer costs and approval tier come from Python. The base `narrative` is also constructed in Python; Gemini explanations are returned separately. A Pydantic `Plan` model is not proof that every runtime dictionary is round-tripped through that model.

A supplier option exposes feasibility and its reason, latest delivery, expiry, quantity and computed cost. Supplier-only quantity is:

```text
supplier_qty = recovered_qty - internal_used_qty
```

The reservation validates that quantity, sends only it to the simulator, and records supplier quantity as operation `qty` and `reservation.qty`. Receipts also include total `recovered_qty` and `internal_qty`.

Approval-tier fields identify the intended approver. They do not prove that the caller has that role.

## 6. Approval persistence and coverage

Current sequence:

```text
rebuild/check plan
→ look for an existing succeeded operation
→ simulated supplier hold if needed
→ write operation
→ write approved plan
→ build transfer/PO/order-update descriptions
→ send or simulate email
→ save fulfilment in process memory
```

There is no transaction covering these steps. A succeeded operation can be reused on a sequential retry, but concurrent calls, partial failures and duplicate notification delivery are not fully protected. Email happens before the fulfilment-memory deduplication.

The dashboard excludes a SKU/location pair with an approved plan from threatened lists. That display rule is not the same as allocating inventory, changing the order line's coverage quantity or confirming delivery.

Fulfilment's `order_update` is a response description, not a persisted order-line mutation. Its history is lost on process restart and is not shared across Cloud Run instances. See [approval details](after_plan_approval.md).

## 7. Access and future safeguards

The browser calls the API, but API identity, tenant membership and role checks are not implemented. Firestore server SDK access uses deployment identity/IAM; illustrative browser security rules do not secure an unauthenticated API route.

The repository's `firebase.json` configures Hosting only. It does not declare deployed Firestore rules/indexes, and there is no checked-in `infra/` deployment package.

Transactional ledger/allocations, versioned decisions, persistent fulfilment, notification outbox and authenticated approvals are [roadmap work](roadmap.md). Tenant-scoped paths are an implemented storage convention, not production tenant-isolation assurance.
