# scheduler.md — Weather and news on a timer

While the API process is running, SignalBridge checks live weather and news
every 2 minutes. When you stop the API, the checks stop too.

This is a task inside the FastAPI process. It is not Unix cron, and it is not
Google Cloud Scheduler.

---

## What runs

`backend/app/main.py` starts `signal_scan_loop()` on startup and cancels it on
shutdown. Each tick calls `scan_route_signals()` in `backend/worker/main.py`:

- Open-Meteo for the weather risk
- GDELT for disruption news

Locations: every in-transit shipment destination, plus every active port.
With the demo fixtures that is `WH-MUM` and `IN-JNPA`. News calls are spaced
5 seconds apart so GDELT does not return HTTP 429.

The scan runs in a background thread, so it does not block `/incidents` or
`/plans`. Results are written to the API log. They are not saved to Firestore.

Interval: `SIGNAL_SCAN_INTERVAL_SECONDS` in `.env` (default `120`). Set it to
`0` to turn the loop off.

Start the API as usual:

```bash
uvicorn backend.app.main:app --reload --port 8000
```

One scan by hand, without leaving it running:

```bash
python -m backend.worker.main
```

That command also rebuilds recovery plans once. The in-app timer only does
weather and news.
