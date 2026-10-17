# Monitoring now and scheduled monitoring later

## Current trigger

The operational React application requests `POST /scan` on load/refresh. Direct visits to `/#/decision-demo` skip this trigger.

The [worker guard](../backend/worker/main.py) prevents overlapping scans within one process and normally skips a new scan until `SCAN_MIN_INTERVAL_SECONDS` has elapsed since the last completion. Its default is **600 seconds**. It is not a distributed lock, and process restarts/multiple Cloud Run instances have separate state.

The optional startup loop is enabled only when `SIGNAL_SCAN_INTERVAL_SECONDS > 0`. Its default is **0**, so there is no always-on two-minute loop by default.

## Execution behavior

[POST /scan](../backend/app/routers/scan.py) runs the scan inline when `K_SERVICE` indicates Cloud Run, keeping work inside that request. Locally it can launch a daemon thread. Both use the guarded worker entry point.

`GET /scan/status` reports process-local running/start/finish/error information. It is not a durable audit of every instance's scans. Long scans, request termination and restarts remain operational considerations.

A scan:

1. Selects in-transit destinations plus all active ports and sea waypoints from the configured store.
2. Fetches Open-Meteo weather. News is skipped for DC/dark-store locations and fetched elsewhere through GDELT/Google News RSS.
3. Saves successful readings/articles as signals.
4. Requests Gemini interpretation for supplied active shipments.
5. Applies valid results to shipment assessments and calculated exposures, then builds/logs recovery proposals.
6. On unavailable/invalid AI output, preserves earlier risk/evidence, records the latest failure and skips that scan's triage/planning update.

This is broader location discovery followed by shipment-route interpretation, not precise remaining-leg-only monitoring.

## Manual scan

```bash
uv run python -m backend.worker.main
```

This performs real weather/news requests and can call Gemini and write to the configured store. It is **not** an offline demo or a harmless benchmark. Confirm backend, tenant and quota before using it.

## Planned Cloud Scheduler integration

Cloud Scheduler is not currently enabled by application code/configuration.

```text
Cloud Scheduler
→ authenticated scheduled request to Cloud Run
→ complete the bounded scan
→ persist completion/failure metadata
→ evaluate deduplicated alert delivery
```

Before claiming unattended operation:

- Implement/verify service identity, OIDC audience and endpoint authorization.
- Choose cadence, timeout and retry policy from measured scan duration and quota.
- Add shared duplicate-run protection and persisted scan status.
- Test failure, retry, instance restart and a run with no dashboard open.
- Verify the configured notification adapter and deduplication separately.

An in-app alert, a scheduled scan and an outbound notification are different outcomes. Default simulated email does not establish delivery.

## Cost

No fixed monthly cost is established here. Scheduler jobs, application execution, Firestore operations, builds/image storage, network and model tokens have separate usage. Check [Scheduler pricing](https://cloud.google.com/scheduler/pricing) and actual account eligibility before enabling jobs. See [roadmap](roadmap.md).
