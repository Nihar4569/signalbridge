# SignalBridge roadmap

Updated **18 October 2026**. This roadmap strengthens the existing React/FastAPI/Gemini/domain/store architecture. Items below are proposed work unless explicitly identified as implemented.

## Current foundation

- Evidence-linked Gemini interpretation with strict ID/quote/coverage validation.
- Operational decision briefs and network-wide/per-plan assistants.
- Deterministic exposure, internal availability, supplier feasibility, cost, benefit, surplus estimate and approval-tier calculation.
- Isolated active-closure/cancelled-strike walkthrough with a fixed clock and reference replay.
- Combined Cloud Run packaging, Firestore store, local/snapshot modes and independent offline benchmarking.
- Simulated supplier execution and default simulated email. Authenticated role enforcement, transactional inventory allocation and durable fulfilment are not implemented.

## Priority 1: trustworthy unattended operation

| Work | Why it matters | Completion criteria |
|---|---|---|
| Authenticated Cloud Scheduler scans | Freshness should not depend on a dashboard visit. | Verify OIDC/service identity and endpoint authorization, bounded completion, retries, persisted completion state and duplicate-run protection. Test with no browser open. |
| Authentication and approval authorization | A calculated approval tier is not access control. | Verify user identity, tenant scope and required role on every write/approval. Tighten public endpoint exposure and CORS deliberately. |
| Durable execution and audit | A proposal/receipt should not be mistaken for changed stock. | Transactional allocation and ledger updates, version/revalidation checks, persistent fulfilment state and explicit partial-failure handling. Test concurrency, restart and retry behavior. |
| Notification deduplication | Repeated approval currently can resend email. | Persist an outbox/delivery key and track attempted, simulated, delivered and failed states. Verify a configured real channel before claiming delivery. |
| Internal-only recovery | Existing approval expects a supplier offer. | Introduce valid internal-only plan/execution states and test stock, timing and donor constraints. |

Cloud Scheduler is a planned trigger, not a replacement for these execution safeguards. In-app alerts, scheduled scanning and outbound notifications are separate capabilities.

## Priority 2: stronger decision support

| Work | Intended scope | Completion criteria |
|---|---|---|
| Live Gemini semantic evaluation | Labelled active, cancelled, historical, unrelated, conflicting and insufficient-evidence notices. | Record actual model/configuration, evidence validity, false alerts, misses, abstentions, failures and latency. Keep a holdout set and compare with a simple baseline. |
| Read-only what-if analysis | Wait under the stored assumption, exclude a supplier or compare supported alternatives. | Calculate each result in a private snapshot. Never reserve, approve or invent prices. |
| Donor-safe transfers | Protect donor demand and consider time/cost/route eligibility. | Demonstrate that a transfer covers the destination without creating an unsupported shortage elsewhere. |
| Better economic model | Distinguish exposed revenue, avoided penalties, recovery cost and contribution margin. | Include the required cost inputs and handle partial recovery consistently. Do not label estimates realized savings. |
| Evidence lifecycle | Stable assessment/version records and source revisions. | Trace decisions to the assessed evidence and clock, and request review when records change. |

The existing deterministic benchmark is not a live semantic evaluation. The two reference walkthrough cases are implemented, but do not establish general AI accuracy.

## Later business extensions

- VIP/SLA-aware allocation when competing orders need scarce stock.
- Penalty/insurance evidence bundles and draft claims, with human review.
- Perishables rescue using validated expiry, handling and destination constraints.
- Mobile/push alerts after authentication and reliable notification delivery.
- Carrier/supplier confirmations, delivery webhooks and authorized ERP integrations.
- Optional read-only ADK assistant tools if they add value beyond the current REST context path.

Reserved schema fields and disabled UI labels do not mean these workflows exist. Specific Google products for extensions are design options, not current usage or promises to deploy them.

## Cost and architecture discipline

Reuse current components first. Measure request volume, model tokens, scan duration, reads/writes, build/image storage and egress before publishing cost estimates. Check account eligibility and current pricing rather than promising a zero bill. See [cloud setup](manual_work.md).

No new database, multi-agent framework, predictive ETA model or managed service is required solely to make the architecture look larger.
