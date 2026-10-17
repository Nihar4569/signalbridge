# How one request travels through SignalBridge

The frontend is a React app in `frontend/src`. The backend is FastAPI in `backend/app`. They communicate over HTTP. The production Docker image can serve both from one Cloud Run URL.

## Follow a recovery review

1. The **Threatened orders** page calls `GET /incidents` through [api.js](../frontend/src/api.js).
2. The [incidents route](../backend/app/routers/incidents.py) groups open order lines by SKU/location and calculates shortages at the earliest deadline. Already-approved pairs are excluded.
3. **AI Plan** opens [AiPlanModal](../frontend/src/components/AiPlanModal.jsx).
4. The modal loads `GET /plans/{sku}/{location_id}/brief`. That endpoint assembles a private read snapshot and returns stored evidence together with a calculated plan.
5. A separate explanation request can call Gemini. The authoritative figures come from [planner.py](../backend/domain/planner.py), not the generated explanation.
6. A planner reviews evidence, assumptions and alternatives. **Approve & execute** calls the approval endpoint only when the displayed proposal has a supplier offer and a positive benefit verdict.
7. The backend rebuilds/checks the current plan, creates a simulated supplier receipt, saves plan/operation records and assembles follow-up descriptions. Email is simulated unless SMTP is configured.

This approval is not proof that inventory moved or goods were delivered. See [approval boundaries](after_plan_approval.md).

## Follow a signal scan

The operational frontend also requests `POST /scan` when it loads. The worker fetches weather/news, stores signals, requests a validated Gemini interpretation and updates assessments/exposures. This is different from `GET /incidents`, which reads and calculates rather than fetching disruption sources.

The scan trigger is throttled per process. An optional timer is off by default. Cloud Scheduler remains planned.

## Main endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Application/store status. |
| `GET /overview`, `GET /map` | Dashboard KPIs and schematic route view. |
| `GET /incidents` | Short SKU/location pairs. |
| `GET /plans/{sku}/{location_id}` | Calculated proposal. |
| `GET /plans/{sku}/{location_id}/brief` | Evidence plus plan from one read snapshot/clock. |
| `GET /plans/{sku}/{location_id}/explain` | Gemini or labelled fallback explanation. |
| `POST /plans/{sku}/{location_id}/ask` | Plan-specific questions. |
| `POST /assistant/ask` | Network-wide questions. |
| `POST /plans/{sku}/{location_id}/approve` | Supported simulated execution workflow. |
| `GET /fulfillments`, `GET /fulfillments/{operation_id}` | Process-local fulfilment history. |
| `GET /signals/{location_id}` | Fetch live weather/news for a place. |
| `POST /scan`, `GET /scan/status` | Trigger/check operational scanning. |
| `GET /decision-demo/cases`, `POST /decision-demo/cases/{case_id}/run` | Isolated reference or live-model walkthrough. |

The frontend's `/#/decision-demo` is a browser route. The backend's `/decision-demo/cases/...` paths are API routes.

## What to run

Use [local setup](start.md): backend port **8000**, Vite development port **3000**, production preview port **5173**. The old no-build frontend is retained in `frontend-legacy/`, not used by the current application.

Gemini also interprets shipment risk and supports both assistants; it is not limited to an explanation button. See [AI responsibilities](agents.md).
