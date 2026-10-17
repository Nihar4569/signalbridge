# Frontend setup and deployment

The dashboard uses React 18, Vite 5, React Router's `HashRouter` and Leaflet. It supports light/dark themes; first use defaults to **light**, then saves the selection in local storage.

## Install and run

```bash
cd frontend
npm ci
npm run dev
```

The development port is **3000**, configured in [vite.config.js](../frontend/vite.config.js). Start FastAPI separately on port 8000 as described in [local setup](start.md).

```bash
npm run build
npm run preview
```

Build output is `frontend/dist/`. Preview uses **5173**, configured in [package.json](../frontend/package.json). Bundle sizes depend on the current build; there is no fixed documented size guarantee.

## API base

[api.js](../frontend/src/api.js) resolves the base in this order:

1. `import.meta.env.VITE_API_BASE`, including an explicit empty string.
2. `window.SIGNALBRIDGE_API`.
3. `http://localhost:8000`.

A standalone frontend build needs the API URL:

```bash
VITE_API_BASE=https://YOUR-API-URL npm run build
```

The combined Docker build sets `VITE_API_BASE=""` so API requests are same-origin. A wrong build-time API base requires a rebuild; changing a backend environment variable does not rewrite an already-built frontend bundle.

## Pages and assistance

| Route | View |
|---|---|
| `/#/` | Overview, schematic route map, alerts and threatened pairs. |
| `/#/shipments` | Shipment records, route context, dates and derived progress/health. |
| `/#/incidents` | Short SKU/location pairs and recovery review. |
| `/#/recoveries` | Current process's fulfilment descriptions and timeline. |
| `/#/signals` | Weather/news lookup for a selected location. |
| `/#/decision-demo` | Isolated active/cancelled notice walkthrough. |
| `/#/capabilities` | Capability and roadmap labels. |

The global Gemini panel supports network-wide questions. The recovery modal includes plan-specific questions, a deterministic plan and stored source evidence.

Sidebar VIP allocation, penalty/claims, perishables and settings entries are disabled future items. Capability labels such as live map, margin optimization and automated fulfilment do not establish carrier telemetry, actual profit optimization or physical execution. See [calculation](calculation.md) and [approval](after_plan_approval.md).

## Recovery modal behavior

The modal requests `/brief` and uses its embedded plan. If the brief fails, it attempts the plan endpoint and shows an evidence warning. It requests an explanation separately, so explanation and proposal are not one version-locked transaction.

It enables approval only for an awaiting-approval plan with a selected offer and positive benefit. The backend rebuilds/checks the plan again. Caller-role verification remains planned.

Fulfilment UI presents generated actions and email results. Default email is simulated, and the timeline is not proof of delivery or inventory mutation.

## Scan and loading behavior

Operational frontend visits request `POST /scan`; direct walkthrough visits skip it. Scan throttling is per API process. Some loading text in conversational panels is timer-driven UI feedback, not a record of actual tool execution. Use returned model/source metadata to distinguish live AI and fallback.

## Hosting choices

### Combined Cloud Run service

The [Dockerfile](../Dockerfile) builds React, copies `dist/` into the Python image and serves it through FastAPI. This is the current deployment shape. See [cloud setup](manual_work.md).

### Optional Firebase Hosting

The existing [firebase.json](../firebase.json) points Hosting to `frontend/dist`, with SPA rewrites and cache headers. This configuration does not prove a deployed Hosting site or enable Firebase Authentication.

After choosing an intended project and deploying an appropriately secured API:

```bash
cd frontend
VITE_API_BASE=https://YOUR-API-URL npm run build
cd ..
firebase deploy --only hosting --project YOUR_PROJECT_ID
```

This command changes cloud resources; it is a deployment instruction, not part of local testing. An independently hosted frontend also needs an appropriate API access/CORS design.

## Map and legacy frontend

Map defaults and overrides are described in [map setup](map_setup.md). Movement is calculated from stored dates, not live GPS/AIS.

`frontend-legacy/` is the old no-build application. It is not the current source or build target.

## Troubleshooting

- Confirm which port the chosen npm command reports.
- Check `VITE_API_BASE` in the actual build environment.
- Inspect health JSON and read errors, not only an HTTP success badge.
- Distinguish empty, unavailable and stale data.
- Do not assume fulfilment history survives backend restarts.
