# Cloud configuration and operational safeguards

The project already has a Cloud Run deployment path and an implemented Firestore store. This guide explains how to configure another environment or verify an existing one. It is not a record of a fresh cloud audit and does not create resources by itself.

Use [local setup](start.md) and reference replay before enabling paid/network integrations.

## 1. Gemini configuration

Obtain a key through [Google AI Studio](https://aistudio.google.com/apikey). Configure `GOOGLE_API_KEY` in untracked local secrets or deployment secret configuration. `GOOGLE_API_KEY_2` is optional. Never paste a real key into committed files, shell history or logs.

The main application uses the Gemini API-key REST path, not Vertex AI or Agent Engine. Key presence does not establish model access or remaining quota. `GEMINI_MODELS` configures the attempted model chain; verify available models in the actual account rather than promising every configured name works.

A key enables more than optional ADK: the scan interpretation, explanations, both assistants and live walkthrough also use it.

## 2. Firestore project, database and identity

Choose the intended project, database location and tenant before writing. Use a Firestore Native-mode database compatible with the configured server client. The current client uses its default database unless code/configuration is deliberately extended.

Local credentials can use Application Default Credentials. A deployed Cloud Run service should use a dedicated service account with narrowly scoped access. An emulator is an alternative for development, not evidence of real cloud persistence.

Relevant settings:

```dotenv
DATA_BACKEND=firestore
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
TENANT_ID=buildx-demo
FIRESTORE_EMULATOR_HOST=
SIGNAL_SCAN_INTERVAL_SECONDS=0
SCAN_MIN_INTERVAL_SECONDS=600
```

For an emulator, supply its actual host and port through `FIRESTORE_EMULATOR_HOST`. Do not point a demo/test at an operational tenant unintentionally.

### Seed safely

From the repository root, first validate without writing:

```bash
uv run python -m scripts.seed_firestore --dry-run --tenant YOUR_TENANT_ID
```

The dry run validates the nine seed collections and prints paths. It does not require a cloud write.

Only after checking the project, identity and tenant, intentionally run:

```bash
uv run python -m scripts.seed_firestore --tenant YOUR_TENANT_ID
```

This writes a tenant root and sets seed documents in batches. Existing matching documents can be overwritten. It is not a production data migration or a rollback-safe reset.

Paths are `tenants/{TENANT_ID}/{collection}/{doc_id}`. See [schema](schema.md).

## 3. Deployment shape

The multi-stage [Dockerfile](../Dockerfile) builds the React dashboard, packages it with FastAPI, sets a same-origin frontend API base and starts Uvicorn on Cloud Run's `PORT`.

The deployment path uses:

- **Cloud Run:** application runtime.
- **Cloud Build:** source/container builds.
- **Artifact Registry:** deployable container image storage.
- **Cloud Firestore:** operational data.
- **Gemini API:** model requests from the backend.

Before a deployment, verify the relevant APIs, billing/account eligibility, service-account permissions, image repository, build identity and region. Secret Manager can be used for deployment secrets, but repository configuration alone does not prove any particular secret resource exists.

Do not blindly redeploy an existing service or replace its environment/IAM configuration. Preserve its current settings, select the intended image/revision and review changes before applying them. A successful build is not proof of correct runtime permissions or data connectivity.

For a new environment, follow the [official Cloud Run source deployment guide](https://cloud.google.com/run/docs/deploying-source-code) and [secret configuration guide](https://cloud.google.com/run/docs/configuring/services/secrets), using the repository Dockerfile and intended runtime identity.

### Access model

The application does not currently verify Firebase user tokens or required approval roles. Do not treat a publicly reachable approval endpoint as production-ready. Use restricted service-level access for controlled environments until application authentication, tenant authorization and write protections are implemented.

A private Cloud Run service needs an appropriate authenticated access/proxy design for browser users. Hosting a separate public frontend does not by itself solve API identity.

## 4. Optional Firebase Hosting

The checked-in `firebase.json` configures Hosting for `frontend/dist` only. The current combined application does not require a separate Hosting site.

For a separately hosted frontend, build with `VITE_API_BASE` set to the secured API URL, select the intended project explicitly and deploy Hosting. See [frontend setup](frontend_setup.md).

The repository does not provide an active Firebase Auth flow or checked-in Firestore rules/index deployment configuration. Therefore `firebase deploy --only firestore` is not a complete working setup step for this checkout. Add/review the required configuration before using it.

Firestore browser rules do not replace IAM for server SDK access or authorization checks in API routes.

## 5. Monitoring and notifications

The default is page-load/refresh-triggered scanning with a process-local throttle. The optional timer is disabled. Cloud Run runs the scan inside the HTTP request; local mode can run a thread.

Cloud Scheduler is planned. Before activation, implement/verify authenticated invocation, request completion, shared duplicate protection, persistent run status and failure/retry handling. See [monitoring](scheduler.md).

Default email is simulated. SMTP is optional and can transmit real messages when configured. Approval can currently repeat email attempts, so do not use it as a reliable deduplicated alert service. In-app alerts, scheduled scans and delivered notifications must be verified separately.

## 6. Cost controls

No measured monthly production bill is established. Model requests, Cloud Run execution, Firestore operations, builds, image retention, egress and optional scheduled jobs can contribute separately. Set budgets/alerts and review actual usage. Budget alerts are not a hard spending cap.

Firestore's documented free quota is not a promise of a zero bill. TTL deletes are excluded from free usage, and current ingestion leaves `ttl_at` null. See [Firestore usage/limits](https://firebase.google.com/docs/firestore/quotas).

Check [Scheduler pricing](https://cloud.google.com/scheduler/pricing) and account eligibility before adding jobs. Do not assume the scheduler alone is the main cost, or claim it controls current scanning when it is not enabled.

External providers have separate licensing and limits. Open-Meteo's free endpoint is non-commercial; see [source guidance](external_api.md).

## 7. Verification checklist

Before describing a cloud capability as operational:

- Confirm the intended service revision, runtime identity, project and tenant.
- Read the health JSON, not just HTTP status.
- Confirm operational data and source timestamps without executing purchases or unsolicited messages.
- Verify the actual model source and distinguish fallback/reference responses.
- Keep real credentials and service-account files out of version control and frontend bundles.
- Enforce identity, tenant and approval roles before exposing write actions.
- Test concurrent retries and restarts before claiming durable exactly-once execution.
- Check notification mode and delivery evidence.
- Confirm the demo does not overwrite another user's operational data.

These are prerequisites, not a list of safeguards already implemented. See [roadmap](roadmap.md).
