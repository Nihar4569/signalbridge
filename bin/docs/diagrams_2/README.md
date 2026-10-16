# SignalBridge — current architecture and submission review

Reviewed on **13 October 2026**, against repository commit **0126731**. These documents describe the code that exists, then label proposed improvements separately. Application code and fixtures were not changed by this review.

Start here:

1. [HLD: the big picture](HLD.md) — which parts exist and how they connect.
2. [LLD: what runs inside each request](LLD.md) — functions, endpoints, monitoring, approval, and persistence.
3. [Assessment and priorities](ASSESSMENT.md) — rating, verified gaps, realistic problem framing, and the submission plan.
4. [Better Gemini usage](GEMINI_IMPROVEMENTS.md) — actual AI behavior, strongest next capability, and evaluation cases.
5. [UI walkthrough](UI_WALKTHROUGH.md) — screenshots of the current local journey and evidence limits.

Open the diagrams directly:

- [Current HLD image](current-hld.svg) / [PNG](current-hld.png)
- [Current approval LLD image](current-approval-lld.svg) / [PNG](current-approval-lld.png)
- [Recommended next architecture](proposed-next-architecture.svg) / [PNG](proposed-next-architecture.png)

Mermaid diagrams are embedded in the Markdown documents. Graphviz `.dot` sources accompany the exported images so the figures remain editable without an AI image generator. The recommended diagram is a **proposal**, not the deployed architecture.

**Plain-language conclusion:** the project has a useful planning engine and an understandable dashboard. The next decisive step is to prove that an approved recovery changes the correct sandbox stock and order coverage, survives retries, and can be traced back to reliable event evidence.

## What was checked

- Read the actual frontend, FastAPI routes, Gemini integration, worker, domain logic, adapters, store, tests, and existing documentation.
- Ran the local suite: **51 tests passed**.
- Ran the documented jacket terminal demo: it returned **no action needed**, because the current jacket shipment fixture is safe. This does not exercise the approval path.
- Ran `ruff check .`: **22 findings** under the resolved configuration. These include conventional FastAPI `Depends` warnings; they are not 22 business-logic failures.
- Inspected the local browser flow with Gemini disabled, monitoring disabled, local data, and simulated email. No paid inference, cloud writes, real purchase, or real message was made.
- Built the frontend into a temporary directory; see the assessment for the result.

The reviewed local UI does not establish production deployment, model accuracy, carrier ETA accuracy, real supplier availability, or business savings. Those need separate evidence.
