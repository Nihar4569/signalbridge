# Evidence-backed decisions and the judge walkthrough

Open **Decision walkthrough** in the sidebar, or `/#/decision-demo` on the deployed frontend.

The walkthrough compares two synthetic notices with the same retail order, stock and supplier offers. A suspension creates an 80-unit shortage under the declared delay assumption. The calculated proposal uses 20 internal units and 60 units from a backup supplier for an external cost of ₹3,700. A cheaper sea offer crosses the affected channel and is rejected. The cancelled-strike notice creates no additional shortage or purchase proposal. An unrelated inland shipment remains excluded.

## Reference replay and live Gemini

- **Reference replay** uses an authored interpretation. It makes no model call and is labelled accordingly. The response still passes the same evidence validator, triage and planner as the live mode.
- **Assess with Gemini** sends the supplied synthetic notice and route IDs to the configured Gemini model. It validates the actual response and displays its real model source and elapsed time.
- Missing keys, quota errors, malformed output or incomplete results produce an unavailable/review state. Live mode never substitutes the reference answer.
- Every run creates a new `SnapshotStore`. It never reads or resets the operational Firestore tenant, creates a hold, sends an email or executes a purchase. Visiting the walkthrough directly also skips the operational page-load scan.

The scenario clock is fixed at **17 October 2026, 09:00 UTC**. Source age, quote expiry, demand and disrupted-arrival calculations use that same clock, so the example remains reproducible during judging. Actual execution time is displayed separately. All places, notices and retailer records in this example are synthetic.

## Operational decision brief

The recovery modal reads `GET /plans/{sku}/{location_id}/brief`. This joins the saved shipment interpretation, exact evidence excerpts, source publication/fetch times and deterministic plan fields. The response includes the plan from the same materialized read snapshot and assessment clock, so the brief's figures match the displayed plan. It does not initiate another model call or change risk state.

On each successful scan, the worker stores a validated `risk_assessment` with each shipment. An older flag without this metadata appears as unverified, and its related signals are marked context rather than model citations. A failed latest attempt preserves the previous risk and evidence while exposing the failed attempt. A changed or stale source requires review.

## Validation and decision boundaries

Gemini returns one typed interpretation for every active shipment: affected, unaffected or unknown, event status, reason, supplied evidence IDs, exact quotes and unresolved fields. Python rejects missing/duplicate/unknown shipment IDs, unsupported evidence, invented quotes, invalid statuses and affected decisions with no route-linked evidence. Unknown results do not clear an existing risk.

The request uses the Gemini REST API's `generationConfig.responseFormat.text` schema contract with the `APPLICATION_JSON` MIME enum. It sends a portable schema subset because configured models reject some Pydantic constraints. Full strict validation, field limits and quote/ID checks still run in Python. The entire model fallback chain shares one time budget. See the [official API reference](https://ai.google.dev/api/generate-content#TextResponseFormat).

The existing severe-route safety rule remains in place. A validated cancellation can exclude its cited notice from that rule, while an independent attack/closure continues to flag risk. The interface shows policy overrides separately from Gemini's interpretation.

Python calculates all quantities and money. Supplier holds use only the external remainder. Quote validity is checked at the assessment time. Approval rejects a plan whose configured recovery-benefit check fails. The UI labels revenue exposure and estimated recovery benefit rather than claiming realized profit.

## Scope

Arrival delay comes from an explicit scenario assumption, not an AI-predicted ETA. Internal availability remains on-hand minus reservations, with transfer cost/time and donor demand requiring review. The walkthrough is read-only and intentionally has no approval action. Operational supplier execution remains simulated through the existing adapter.

These changes reuse the existing React, FastAPI, Gemini, domain and store layers. They add no managed services, databases or agent framework migration.

## Run and test

```bash
uv run python -m pytest -q
uv run python -m scripts.demo
cd frontend
npm run build
```

`tests/test_decision.py` covers the evidence contract, active/cancelled outcomes, an unrelated route, independent conflicting disruption, private replay isolation, expiry, external reservation quantities and unavailable-AI handling. Mocked tests establish integration behavior, not live model accuracy.

For a live smoke check, start the usual API with its existing Gemini key, open the walkthrough and run both notices using **Assess with Gemini**. Record the actual model/status and inspect the quotes before using the result in a demo. No new key is needed for reference mode.
