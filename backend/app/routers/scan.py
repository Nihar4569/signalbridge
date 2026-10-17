"""On-demand signal scan, triggered by the frontend on page load / refresh.

Keeps live weather + news fresh without a cron job or Cloud Scheduler: the
dashboard pings POST /scan when it loads, and the scan runs in the background
(throttled, see worker.trigger_scan).

As of now we rely on this page-load trigger to stay on the free tier. Later,
Google Cloud Scheduler will call this same endpoint on a fixed schedule so the
data refreshes even when no one is watching the dashboard.
"""
from fastapi import APIRouter

from ...worker import main as worker

router = APIRouter(tags=["scan"])


@router.post("/scan")
def start_scan() -> dict:
    """Kick off a weather+news scan in the background. Returns immediately.

    status: "started" (a new scan began), "running" (one is already in progress),
    or "fresh" (one ran recently, within the throttle window).
    """
    return worker.trigger_scan()


@router.get("/scan/status")
def scan_status() -> dict:
    """Current scan state: running? how long since the last scan finished?"""
    return worker.scan_status()
