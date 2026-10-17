# SignalBridge documentation

SignalBridge helps retail planners connect disruption evidence to customer commitments and review a calculated recovery proposal. Gemini interprets evidence. Python calculates the business impact. A person initiates the supported approval workflow.

These documents describe the repository as reviewed on **18 October 2026**. They distinguish implemented behavior from optional integrations and proposed work. A code review does not establish the latest cloud configuration or live model availability.

| Read | Purpose |
|---|---|
| [Architecture](architecture.md) | Current components, Google product roles and end-to-end flow. |
| [Local setup](start.md) | Run the API, React frontend, reference walkthrough and tests. |
| [Simple walkthrough](simple.md) | Follow a request through the actual files. |
| [Gemini and ADK](agents.md) | AI responsibilities, validation and the separate optional agent. |
| [Calculations](calculation.md) | Formulas, a reproducible example and modeled constraints. |
| [Data contract](schema.md) | Stored records, calculated responses and persistence boundaries. |
| [Monitoring](scheduler.md) | Current scan triggers and planned Cloud Scheduler integration. |
| [External sources](external_api.md) | Weather/news adapters, fallback behavior and usage limits. |
| [Decision walkthrough](decision_walkthrough.md) | Active/cancelled examples, reference replay and live Gemini. |
| [Approval workflow](after_plan_approval.md) | Simulation, records, notifications and execution limitations. |
| [Frontend](frontend_setup.md) | Ports, pages, build configuration and hosting choices. |
| [Map](map_setup.md) | Tile configuration and the distinction from carrier telemetry. |
| [Cloud setup](manual_work.md) | Credentials, deployment preparation and security prerequisites. |
| [Roadmap](roadmap.md) | Agreed direction, remaining safeguards and completion criteria. |
| [Design evolution](blueprint.md) | How the initial proposal differs from the implemented architecture. |
| [Offline benchmark](../tests/benchmark/README.md) | Reproducible policy checks, measurements and interpretation limits. |

## Status vocabulary

- **Implemented:** the checked-in code contains the behavior, within its documented limits.
- **Optional:** a separate runnable path or configuration, not automatically part of the web workflow.
- **Planned:** not a current capability. Acceptance criteria explain what must be built and verified.
- **Historical:** a dated review or proposal retained for context, not the current contract.

The deployment uses Cloud Run with a combined frontend/API container and Firestore as the operational storage path. Cloud Build and Artifact Registry support container deployment. Optional ADK and Firebase Hosting configurations are separate. Cloud Scheduler, role-enforced approvals and durable inventory execution remain roadmap work.

Historical material under [bin/docs/diagrams_2](../bin/docs/diagrams_2/README.md) contains old screenshots, assessments and diagrams. Use this index for current behavior.
