# SignalBridge — prototype assessment and best next steps

**Reviewed: 13 October 2026. Verdict: a promising planning prototype, but not yet a strong winning submission on the evidence inspected. My current assessment is 6.1/10.** This is an engineering judgment against the public rubric, not an organizer score, predicted rank, or probability of winning. Other entries and live cloud deployment were not evaluated.

## 1. What is already good

- A specific retail problem with a clear event → threatened order → recovery workflow.
- Useful deterministic modules for internal stock, supplier constraints, economics, governance and surplus.
- Gemini affects shipment-risk judgment in the actual monitor, not just the explanation panel.
- An understandable React dashboard and a recovery modal with baseline/disrupted comparison.
- Local mode, integer money fields, synthetic fixtures, an implemented Firestore adapter, and 51 passing tests.
- A complete frontend production build succeeded during this review.

These are worth preserving. The weakness is proof of the core outcome, rather than the number of pages or cloud products.

## 2. Rubric-based rating

The official weights are technical merit/GenAI 40%, problem alignment/impact 25%, innovation 25%, and UX 10%. [Official judging criteria](https://aibuildercup.com/themes.html).

| Criterion | My score / 10 | Weighted contribution / 10 | Reason |
|---|---:|---:|---|
| Technical merit and meaningful GenAI | 5.0 | 2.00 | Useful planning and risk judgment, but unsafe partial model output, missing authenticated/versioned approval, and no verified stock/coverage mutation. |
| Problem alignment and potential impact | 8.0 | 2.00 | Strong retail use case; current benefits remain synthetic and economic assumptions need clearer treatment. |
| Innovation and creativity | 5.5 | 1.375 | Connecting disruption and recovery is useful, but established vendors offer monitoring, contextual relevance and response workflows. Distinctive execution/evidence is not yet proven. |
| UX and integration | 7.5 | 0.75 | Clear visual hierarchy and plan comparison; source labeling, completion claims, evidence drill-down and result refresh need work. |
| **Total** | | **6.125 ≈ 6.1** | **Good foundation; closing the loop should come first.** |

Prototype judgment is lighter than a production audit. A prototype need not integrate every real carrier or supplier. It should, however, correctly implement the sandbox action it says completed. That issue materially affects both technical merit and demonstrated impact.

## 3. The real problem to pitch

Avoid claiming that companies have no connection between external news and their databases. Existing supply-chain platforms already sell contextual monitoring, scenario planning, and action workflows. For example, [Everstream's product page](https://www.everstream.ai/platform/global-monitoring/) describes those capabilities; that is a vendor description, not independently validated performance.

Use this narrower statement:

> Retail planners receive external disruption alerts but still need to establish whether the event applies to an uncompleted shipment leg, which customer commitments would actually become short, and which feasible recovery action can be approved and verified without creating another shortage or duplicate purchase.

The difficult part is not displaying a storm or matching a port name. It is establishing applicability, calculating time-dependent exposure, selecting a defensible action, and checking the resulting business state.

### Questions a real planner would ask

1. Is the report active, planned, cancelled, old, or just a drill?
2. Does it affect our terminal and cargo operation while our shipment is still there?
3. Is an arrival date carrier-confirmed or just our scenario assumption?
4. Which order lines fail at each deadline, after other arrivals and existing allocations?
5. Can we transfer our own stock without threatening the donor location's orders?
6. Is the supplier quote current, reservable, on time, product-equivalent, and affordable?
7. What new cost does this action create, including the original shipment arriving later?
8. Did the hold and allocation persist, and what happens if the response is lost or the hold expires?

These questions should organize the product and demo. Map movement and broad chat are supporting features.

## 4. Verified gaps, in priority order

### A. Approval does not complete the business action

[Reservation code](../../../backend/domain/reservations.py#L44) calls a simulator that returns a random receipt. [Supplier simulator](../../../backend/adapters/supplier.py#L14) does not decrement availability. Reservation writes operation and plan documents, but neither it nor [fulfillment](../../../backend/domain/fulfillment.py#L80) applies stock balances, supplier stock or per-order recovery coverage. The `order_update` is a description.

**Observed in the browser:** a receipt said “Order marked covered by recovery.” Immediately afterward, `GET /incidents` still reported 80 units short and `GET /plans/JACKET-NAVY-M/WH-ZLO` still returned `awaiting_approval`. This is the most important mismatch to fix.

**Acceptance:** show supplier available stock before/after, internal reserved stock before/after, exact order allocation references, operation receipt and authoritative read-back. Physical on-hand stock must stay unchanged until goods arrive.

### B. Supplier quantity includes internally sourced units

[Reservation](../../../backend/domain/reservations.py#L44) passes total `recovered_qty`; [fulfillment](../../../backend/domain/fulfillment.py#L30) correctly subtracts `internal_used_qty` for its PO. In the isolated jacket fixture, total recovery was 80, internal stock 20, supplier remainder 60, but the supplier hold requested 80.

**Acceptance:** one 20-unit internal hold and one 60-unit supplier hold, consistent with the plan, PO, cost and allocations. Internal-only recovery must also work; it currently has no selected supplier and is rejected by the approval path.

### C. Approval is a label, not an enforced authorization

[Approval endpoint](../../../backend/app/routers/plans.py#L47) uses only a store dependency. [Auth is still a TODO](../../../backend/app/deps.py#L12). The displayed governance tier does not verify that the caller is the required approver. Approval recomputes a plan instead of accepting the exact version the user reviewed.

**Acceptance:** verified identity, tenant membership, role/spend limit, immutable plan/version and quote expiry. Reject changed plans and unauthorized callers. Keep isolated synthetic demo sessions easy for judges to use.

### D. Retry and persistence guarantees are incomplete

[Reservation](../../../backend/domain/reservations.py#L36) reads then acts without a transaction, caches success before durable writes, and can invoke a supplier twice concurrently. [Fulfillment history](../../../backend/domain/fulfillment.py#L18) is process-local even in Firestore mode. [Approval](../../../backend/app/routers/plans.py#L64) sends notifications before fulfillment deduplication, so repeating approval repeats sends.

**Acceptance:** transactionally persist correct owned holds, order claims, operation and outbox. Track immutable arguments. A restart, double-click or lost response returns the same result, does not repeat notification side effects, and never oversells. A new event/plan version cannot reserve the same order demand again. Expiry/cancellation releases claims and revokes planned coverage.

### E. Partial Gemini output can clear real risk

[_parse_judgments](../../../backend/ai/gemini.py#L366) tolerates empty/partial/mistyped outputs. [_zone_for_shipment](../../../backend/domain/triage.py#L119) treats a missing shipment as safe. Isolated examples with an empty list, unknown IDs, missing `risk`, string `"true"`, or contradictory duplicates produced unsafe clearing behavior.

**Acceptance:** strict types, exact expected shipment coverage, uniqueness, evidence IDs and explicit `unknown/review`. Invalid output must not silently erase risk. Current no-response behavior preserves old flags; retain that distinction and add a visible stale/unknown status.

### F. Exposure and time constraints need stronger handling

- [Planner](../../../backend/domain/planner.py#L23) evaluates the earliest deadline. A case with 100 units of stock, an early 50-unit order and a later 500-unit order returned no action needed, hiding the later 450-unit shortage.
- [Exposure](../../../backend/domain/exposure.py#L75) uses assumed arrivals for every shipment in a disrupted SKU/location scenario, including safe sibling shipments.
- [Offer selection](../../../backend/domain/planner.py#L158) does not reject expired quotes. The isolated jacket offer expired on 10 October but remained selectable on 13 October.
- The current semantic input lacks precise source dates, affected operation, terminal scope and remaining-leg times. Location names and general route risk are insufficient proof of shipment delay.

**Acceptance:** time-phased supply/demand across all deadlines; per-shipment confirmed/expected/scenario dates; quote freshness; and operational applicability with assumptions visible.

### G. The economic claim needs a clearer baseline

The modal presents revenue plus penalties minus replacement cost as net benefit. That is a decision heuristic, not observed profit saved. A real decision also depends on original purchase obligations, incremental recovery costs, transfer/freight costs, contribution margin, whether penalties are contractually applicable, and eventual surplus.

**Acceptance:** label projected revenue exposure, simulated commitment and assumptions. Add a deterministic do-nothing comparison. Do not claim measured savings from fictional numbers or treat every lost unit of revenue as lost profit.

### H. Failed data reads can look safe, and popup content needs escaping

[Dashboard](../../../frontend/src/pages/Dashboard.jsx#L20) and [Incidents](../../../frontend/src/pages/Incidents.jsx#L19) suppress read failures before showing empty/safe messages. The header checks HTTP success, not the health body's degraded status. Show acquisition failure, freshness, model/fallback mode and unknown risk distinctly from a verified safe state.

[MapView](../../../frontend/src/components/MapView.jsx#L100) interpolates alert titles into popup HTML; external news can supply those titles. Escape text or use safe DOM text nodes. This is a code-reviewed injection risk, not a runtime exploit tested during the audit.

## 5. The strongest differentiator to build

**“Why this order is affected, why this recovery wins, and proof it completed.”**

Make one compact decision record with four layers:

| Layer | What a judge sees |
|---|---|
| Evidence | Original notice, source/time, extracted status, exact supporting text, and terminal/operation scope. |
| Applicability | Remaining shipment leg and time overlap; unaffected shipments explicitly excluded. |
| Alternatives | Do nothing, transfer internally, and supplier recovery, with deterministic quantities/costs and rejection reasons. |
| Verification | Authorized action, correct holds/allocations, persisted receipt, read-back and replay-safe result. |

Add a negative scenario: a report says the strike was cancelled, so the system explains why it does **not** recommend a purchase. Pair it with a positive case using differently worded or multilingual operational text. That demonstrates semantic AI value beyond keyword matching. The system should not assert certainty from conflicting or inadequate evidence.

This is a proposed focus, not a claim that no competitor has similar features. Strong execution and measured results are the defensible differentiation.

## 6. Best use of Gemini and Google products

Keep the existing deterministic planner. Use Gemini for typed event interpretation, semantic applicability proposals, identifying conflicting evidence, and explaining constrained alternatives. Return evidence references, status and unresolved fields; validate them before affecting operational state. Use deterministic read-only tools for quantities and comparisons. Never ask the model to perform authoritative money calculations or write stock.

See [the detailed Gemini plan](GEMINI_IMPROVEMENTS.md). A scanned manifest or multilingual notice can be a useful stretch demo, but adding multimodal processing is lower priority than correct recovery execution.

| Priority | Google capability | Specific contribution |
|---|---|---|
| Core | Gemini | Interpret unstructured operational evidence; distinguish active/cancelled/partial events. |
| Core | Firestore transactions | Persist owned stock holds, demand allocations, action ledger and outbox correctly. |
| Core | Firebase Authentication | Enforce the user and approval tier. |
| Submission | Cloud Run + Firebase Hosting | Accessible, functioning deployed prototype. |
| Durability | Cloud Tasks + Scheduler | Bounded retries and scheduled acquisition outside the API's process timer. |
| Optional | ADK ordered workflow | Real inspectable stages with typed tools and evaluations, if adopted in the actual running path. |
| Stretch | Document AI or Gemini document understanding | Extract an authorized manifest while retaining source anchors. |

Do not add Cloud SQL, a vector database, several hosting platforms or more agent names just to increase the product count. The public rubric scores meaningful AI and functioning implementation. The Google model must be verified available in the actual account; pin a supported model rather than relying only on rolling aliases and unmeasured fallback chains.

## 7. Work plan from 13 to 18 October

The current official site lists submission on **18 October 2026**, with team formation ending **14 October**. Verify the portal's exact cutoff/time zone. These dates supersede earlier planning assumptions. [Official timeline](https://aibuildercup.com/), [FAQ](https://aibuildercup.com/Faqs.html).

| When | Outcome to finish |
|---|---|
| 13–14 October | Correct sandbox recovery: quantities, current quotes, durable holds/allocations, versioned approval, read-back. |
| 14–15 October | Strict model output and evidence/time/status contract; positive, cancelled and ambiguous notices. |
| 15–16 October | Deadline/safe-sibling/internal-only cases; concurrent/retry/restart tests; identity and role checks. |
| 16 October | Deploy and test from a fresh judge session; validate model access and degraded-mode labels. |
| 17 October | Record measured evaluation, rehearse a 2:45 demo, complete public repo/deck and verify links. |
| 18 October | Submit with buffer before the verified cutoff; maintain judge access. |

If the team cannot finish everything, freeze expansion and complete one end-to-end scenario accurately. A transparent limitation is preferable to a green success claim unsupported by state.

## 8. Submission evidence and proposed evaluation

Create an evaluation set before tuning prompts: active closure, cancelled strike, reopening, old report, partial terminal suspension, navigation drill, translated alias, unrelated port, shipment already past the port, weather without closure, conflicting notices and unavailable source. Add paraphrases without the current disruption keywords.

Measure semantic applicability precision/recall and abstentions; compare a keyword baseline with Gemini. Separately verify exact shortage/currency/time calculations and database state. Include missing/duplicate model rows, concurrent approvals, changed plans, expired quotes, lost response, failed persistence, internal-only recovery, new-plan duplicate demand, cancellation/expiry and process restart.

Report actual sample count, failures, model/config, p50/p95 latency, tokens and measured cost. No Gemini evaluation was run in this read-only review, so no accuracy or performance numbers are claimed here.

Suggested demo sequence:

1. A clearly labeled synthetic retailer and owned disruption notice.
2. Gemini interpretation plus quoted evidence, including why other shipments are excluded.
3. Exact threatened order and do-nothing/internal/supplier comparisons.
4. Manager approval and correct sandbox stock changes.
5. Refresh/read-back proving planned coverage; duplicate retry proves one effect.
6. Cancelled/irrelevant notice demonstrating no unnecessary recommendation.

The FAQ requires a working deployed link, public repository, deck and a video under three minutes. [Submission requirements](https://aibuildercup.com/Faqs.html).

## 9. Review evidence and limits

| Check | Result |
|---|---|
| Unit suite | 51 passed in the existing local environment. |
| Frontend build | Passed; output was written outside the repository. |
| Documented terminal demo | Ran successfully but returned no action needed for the safe jacket fixture. |
| Lint | 22 findings; includes broad exception handling, unused variables and conventional FastAPI dependency warnings. No automatic fixes applied. |
| Browser journey | Dashboard → threatened orders → recovery plan → simulated receipt captured. |
| Post-approval read-back | Still 80 short and awaiting approval in the current Mexico fixture. |
| Domain review reproductions | Correctness failures above reproduced using isolated local stores/fake suppliers/senders. |
| Paid model/cloud integration | Not exercised. |
| Deployment availability | Not verified; repository contains deployment instructions/config, not a verified live URL. |
| Real customers/supplier access | Not validated in this review. |

The review changed only documentation/diagram assets in this folder. The app was run locally with synthetic data, Gemini disabled and simulated emails. Passing tests demonstrate the cases encoded by those tests, not correctness of all advertised behavior.
