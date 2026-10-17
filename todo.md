# SignalBridge work plan

Updated **18 October 2026**. The detailed priorities and acceptance criteria are in [docs/roadmap.md](docs/roadmap.md). This checklist separates working code from remaining operational safeguards.

## Implemented foundation

- [x] React/Vite control tower, seven routable pages, Leaflet schematic map and light/dark themes.
- [x] FastAPI views, planning, evidence brief, scan/status, chat, approval and fulfilment endpoints.
- [x] Gemini REST interpretation, strict evidence/ID validation and actual model/fallback attribution.
- [x] Global and per-plan Gemini assistants.
- [x] Weather/news collection with Google News RSS fallback and process-local caching/throttling.
- [x] Deterministic shortage, internal availability, offer constraints, cost, estimated benefit, surplus and approval-tier calculations.
- [x] Local, Firestore and private snapshot stores.
- [x] Fixed-clock active/cancelled decision walkthrough with reference and live-model modes.
- [x] Combined frontend/API Docker packaging for Cloud Run.
- [x] Independent offline benchmark with negative controls and mocked resilience checks.
- [x] Supplier simulation, approved plan/operation persistence and default simulated email.
- [x] Optional single ADK weather/news agent and alternative Firebase Hosting configuration.

Implemented does not mean complete production guarantees. The map is not carrier telemetry; economic estimates are not realized profit; approval does not implement transactional inventory allocation.

## Next safeguards

- [ ] Authenticated scheduled monitoring without a dashboard visit.
- [ ] User/tenant identity and role enforcement for approval/write endpoints.
- [ ] Transactional allocation, stock ledger and current-quote/version revalidation.
- [ ] Durable fulfilment state across restarts/instances.
- [ ] Deduplicated notification delivery/outbox and real-channel verification.
- [ ] Internal-only recovery execution and donor-safe transfer constraints.
- [ ] Labelled live Gemini evaluation, with failures/abstentions reported separately.
- [ ] Read-only what-if alternatives from isolated snapshots.
- [ ] Versioned decision/evidence records and changed-source review.

## Later business extensions

VIP/SLA allocation, penalty/insurance drafts, perishables rescue, mobile alerts and authorized carrier/ERP/supplier integrations remain future work. Optional ADK assistant-tool integration should be added only if useful; a multi-agent rewrite is not an agreed requirement.

See [roadmap](docs/roadmap.md) for scope and completion criteria, [cloud setup](docs/manual_work.md) for environment prerequisites and [documentation index](docs/README.md) for current references.
