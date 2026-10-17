# Evidence-backed decision walkthrough

The walkthrough compares an active channel closure with a cancelled strike using the same synthetic retail records. It makes the relationship between evidence interpretation and calculated recovery explicit.

Open `/#/decision-demo` in the frontend, or choose **Decision walkthrough** in the sidebar. For local development, use [http://localhost:3000/#/decision-demo](http://localhost:3000/#/decision-demo).

## Fixed case and expected reference outcomes

[Fixture](../fixtures/decision_demo/cases.json): 100 coffee units due, 20 on-hand, 80 inbound, 20 internal units elsewhere and two supplier offers. Scenario clock: **17 October 2026, 09:00 UTC**.

| Notice | Reference result |
|---|---|
| Active channel closure | 80-unit shortage under the declared delayed-arrival assumption. Use 20 internal units and 60 supplier units for ₹3,700 external cost. Reject the cheaper offer crossing the disrupted passage. |
| Strike cancelled before starting | Zero shortage under the expected arrival. No additional recovery purchase proposal. |

The independent inland shipment is unrelated to the fictional passage in both examples. All notices, places and business records here are synthetic.

## Reference replay versus live Gemini

- **Reference replay** uses an authored interpretation with no model call. It still exercises the evidence validator, triage policy and deterministic planner.
- **Assess with Gemini** sends the supplied notice and route records to the configured model. It displays actual source/model metadata when successful.
- Missing keys, quota errors or invalid/incomplete output produce unavailable/review states. Live mode never silently substitutes the reference answer.
- A model's valid response is not guaranteed to agree with the authored expectation. Inspect evidence, uncertainty and policy overrides.

Every run creates a private `SnapshotStore`. It does not read/reset the operational Firestore tenant, reserve stock, send email or execute a purchase. Visiting this frontend route directly skips the operational page-load scan.

The fixed scenario clock controls source age, offer validity and planning assumptions. Actual execution timestamp/duration are separate. The displayed duration covers the walkthrough request's work, not isolated model inference only.

## API contract

| Endpoint | Purpose |
|---|---|
| `GET /decision-demo/cases` | Case catalogue, fixed clock, synthetic flag and whether a Gemini key is configured. |
| `POST /decision-demo/cases/{case_id}/run` | Run with `{"mode":"reference"}` or `{"mode":"gemini"}`. |

Configured keys do not establish available quota or successful model access.

[The route](../backend/app/routers/decision_demo.py) returns assessment state, plan, brief, shipment assessments, mode, scenario clock and actual execution metadata.

## Operational evidence brief

`GET /plans/{sku}/{location_id}/brief` joins saved shipment assessments, exact source excerpts, timestamps and a plan calculated from the same materialized input snapshot/clock. It does not initiate a model call or alter risk.

The recovery modal loads that brief and its embedded plan. Its separate explanation request can rebuild from a different read time, so it is not a version-locked explanation/approval transaction.

Older shipment flags without evidence metadata appear unverified. Failed latest attempts preserve earlier evidence/risk while exposing failure. Stale or changed sources request review.

## Interpretation checks and policy

Python requires complete, unique supplied shipment IDs, strict output types, known evidence IDs, exact excerpts, current cited evidence and route-linked support for affected decisions. Unknown results do not clear existing risk.

The REST request uses a portable `generationConfig.responseFormat.text` schema with the `APPLICATION_JSON` enum. Python applies full validation independently of the portable subset. See [implementation](../backend/ai/gemini.py) and [output models](../backend/models/decision.py).

A deterministic severe-route floor can override an unaffected result. A cited validated cancellation excludes only supported notices, not an independent attack/closure. This bounded rule is not a complete event-revision/timing model.

## Scope and validation

The delay is an explicit stored assumption, not an AI-predicted ETA. Internal availability is on-hand minus reserved; donor demand, transfer time/cost and full shared-stock allocation require further work. Supplier approval elsewhere in the application remains simulated.

[tests/test_decision.py](../tests/test_decision.py) covers the evidence contract, active/cancelled outcomes, unrelated routes, conflicting severe evidence, snapshot isolation, expiry, supplier-only quantities and unavailable-AI handling.

Use the [documented offline test command](start.md). Reference tests do not establish live model accuracy. Only select live Gemini mode when intentionally using available model quota.

See [calculations](calculation.md) and [roadmap](roadmap.md).
