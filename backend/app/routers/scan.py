"""On-demand signal scan, triggered by the frontend on page load / refresh.

Keeps live weather + news fresh without a cron job or Cloud Scheduler: the
dashboard pings POST /scan when it loads, and the scan runs in the background
(throttled, see worker.trigger_scan).

As of now we rely on this page-load trigger to stay on the free tier. Later,
Google Cloud Scheduler will call this same endpoint on a fixed schedule so the
data refreshes even when no one is watching the dashboard.
"""
import os

from fastapi import APIRouter

from ...worker import main as worker

router = APIRouter(tags=["scan"])

# Cloud Run throttles CPU once the HTTP response returns, which would stall a
# background thread. On Cloud Run (K_SERVICE is always set) run the scan inline
# so it finishes inside the request's CPU window; stay background locally so
# page loads never block.
_RUN_INLINE = bool(os.getenv("K_SERVICE"))


@router.post("/scan")
def start_scan() -> dict:
    """Kick off a weather+news scan. Returns when done on Cloud Run, else immediately.

    status: "started" (a new scan began), "running" (one is already in progress),
    or "fresh" (one ran recently, within the throttle window).
    """
    return worker.trigger_scan(background=not _RUN_INLINE)


@router.get("/scan/status")
def scan_status() -> dict:
    """Current scan state: running? how long since the last scan finished?"""
    return worker.scan_status()
