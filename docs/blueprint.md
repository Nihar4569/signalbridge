# Design evolution

This page replaces the initial starter blueprint as a navigation/reference document. The original proposal described components that were never all implemented. It must not be used as proof of current services or execution guarantees.

The product direction remains: connect disruption evidence to retail order exposure and a recovery proposal that a human reviews.

## Original proposal versus implemented solution

| Original idea | Current implementation | Direction |
|---|---|---|
| Sequential ADK triage/recovery agents | Direct Gemini REST interpretation plus deterministic Python planning. One optional ADK weather/news agent. | Keep the current boundary. Add tool integration only if justified. |
| Separate API and managed worker services | One combined Cloud Run application. Optional in-process timer, off by default. | Authenticated scheduled invocation of the existing scan workflow. |
| Firebase-hosted TypeScript dashboard | React/JavaScript/Vite dashboard served by the combined container. Firebase Hosting is a configured alternative. | Preserve the current UI and hosting options. |
| Stored event/exposure/plan chain for every proposal | Signals, shipment assessments and exposures persist through the store. Plans are computed on read and saved on approval. | Versioned decision records and stronger auditability. |
| Transactional stock ledger and allocations | Models exist, but approval does not update those inventory/coverage records transactionally. | Build durable inventory execution before claiming stock/coverage mutation. |
| Cloud Tasks retrying execution | No Cloud Tasks integration in the current workflow. | Consider durable jobs if required after execution contracts are defined. |
| Role-controlled Firebase approvals | Approval tier calculation exists; authentication and role enforcement do not. | Enforce caller identity, tenant scope and approval authority. |
| Predictive arrival and network optimization | Stored arrival assumptions, local eligibility checks and a simple surplus formula. | Add verified timing and donor-safe feasibility before broader optimization claims. |

## Current architecture and roadmap

Use [architecture.md](architecture.md) for the running system, [schema.md](schema.md) for persistence and [roadmap.md](roadmap.md) for planned work. These references take precedence over historical diagrams.

Google Cloud Run, Firestore, Gemini, Cloud Build and Artifact Registry have defined roles in the current deployment path. ADK and Firebase Hosting remain optional integrations. Scheduler is planned. Document AI, BigQuery, Maps, FCM and managed agent runtimes are not current dependencies.

Dated reviews and screenshots under [the archive](../bin/docs/diagrams_2/README.md) preserve earlier observations. Their old test counts, file locations and unresolved defects are not automatically current.

No architecture migration is required for the immediate roadmap.
