"""Scan active shipments and build recovery plans for anything at risk.

The API process runs the weather and news scan on a timer while it is up.
You can also run one pass by hand:
    python -m backend.worker.main
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone

from ..adapters import news as news_adapter
from ..adapters import weather as weather_adapter
from ..ai import gemini as gemini_mod
from ..core import config
from ..core.logging import get_logger
from ..core.store import get_store
from ..domain import ingestion as ingestion_mod
from ..domain import planner as planner_mod
from ..domain import triage as triage_mod
from .route_monitor import signal_scan_location_ids

log = get_logger("worker")


# --- on-demand scan (frontend-triggered) -------------------------------------
# As of now we deliberately do NOT use Google Cloud Scheduler, to keep the demo
# on the free tier. Instead the frontend calls POST /scan on every page load /
# refresh, which keeps live weather + news fresh for whoever is viewing the
# dashboard. In production this exact entry point moves to Cloud Scheduler ->
# Cloud Run on a fixed cron, so data refreshes even with nobody watching.
# The scan runs in a background thread (never blocks the page) and is throttled
# so repeated refreshes don't hammer the free APIs or the Gemini quota.
_scan_lock = threading.Lock()
_scan_state: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_summary": None,
    "last_error": None,
}


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def scan_status() -> dict:
    """JSON-friendly view of the scan state for the frontend."""
    finished = _scan_state["finished_at"]
    return {
        "running": _scan_state["running"],
        "last_started_at": _iso(_scan_state["started_at"]),
        "last_finished_at": _iso(finished),
        "seconds_since_last_scan": round(time.time() - finished) if finished else None,
        "last_summary": _scan_state["last_summary"],
        "last_error": _scan_state["last_error"],
    }


def trigger_scan(*, min_interval: int | None = None, background: bool = True, scan_fn=None) -> dict:
    """Start a weather+news scan unless one is running or ran recently.

    Returns immediately. `min_interval` (seconds) throttles repeated triggers so
    page refreshes don't start a new scan every time.
    """
    if min_interval is None:
        min_interval = config.SCAN_MIN_INTERVAL_SECONDS
    scan_fn = scan_fn or scan_route_signals
    now = time.time()
    with _scan_lock:
        if _scan_state["running"]:
            return {"status": "running", **scan_status()}
        finished = _scan_state["finished_at"]
        if finished is not None and (now - finished) < min_interval:
            return {"status": "fresh", **scan_status()}
        _scan_state.update(running=True, started_at=now, last_error=None)

    if background:
        threading.Thread(target=_run_scan, args=(scan_fn,), name="signal-scan", daemon=True).start()
    else:
        _run_scan(scan_fn)
    return {"status": "started", **scan_status()}


def _run_scan(scan_fn) -> None:
    try:
        results = scan_fn()
        _scan_state["last_summary"] = {
            "locations_scanned": len(results),
            "news_found": sum(r.get("news_count", 0) for r in results),
        }
    except Exception as exc:  # a failed scan must never crash the server
        log.exception("On-demand scan failed")
        _scan_state["last_error"] = type(exc).__name__
    finally:
        _scan_state.update(running=False, finished_at=time.time())


def scan_route_signals(store=None) -> list[dict]:
    """Check live weather + news for every location on an active route.

    Saves each result to the `signals` collection (backend/domain/ingestion.py)
    so there is a durable record, not just a log line. This is the "watch
    the world" half of monitoring. See docs/scheduler.md.
    """
    store = store or get_store()
    locations = {loc["location_id"]: loc for loc in store.list("locations")}
    results: list[dict] = []
    # The news adapter spaces out GDELT calls and falls back to Google News itself.
    for location_id in signal_scan_location_ids():
        location = locations.get(location_id)
        if not location:
            continue
        weather = (
            weather_adapter.get_weather_risk(location["lat"], location["lon"])
            if location.get("lat") is not None
            else {"ok": False, "risk": "unknown", "error": "no coordinates"}
        )
        # Our own warehouses are not in the news; ports and sea areas are.
        if location.get("type") in ("dc", "dark_store"):
            news = {"ok": True, "count": 0, "articles": []}
        else:
            news = news_adapter.search_disruptions(location.get("news_query") or location.get("name", location_id))
        ingestion_mod.ingest_weather_signal(location, weather, store=store)
        ingestion_mod.ingest_news_signals(location, news, store=store)
        articles = news.get("articles") or []
        results.append(
            {
                "location_id": location_id,
                "name": location.get("name"),
                "weather_risk": weather.get("risk"),
                "weather_ok": weather.get("ok", False),
                "max_wind_gust_kmh": weather.get("max_wind_gust_kmh"),
                "max_precip_mm": weather.get("max_precip_mm"),
                "news_ok": news.get("ok", False),
                "news_count": news.get("count", 0),
                "news_error": news.get("error"),
                "headlines": [a.get("title") for a in articles[:3]],
            }
        )
        log.info(
            "Signal scan %s: weather=%s, news=%s",
            location_id,
            weather.get("risk"),
            news.get("count", news.get("error")),
        )
    judgments = gemini_mod.judge_shipment_risk(
        shipments=store.list("shipments"),
        signals=store.list("signals"),
        locations=store.list("locations"),
        products=store.list("products"),
        lanes=store.list("lanes"),
    )
    if judgments is None:
        log.warning("Triage skipped. Gemini did not answer, so risk flags were left unchanged.")
        return results
    log.info("Triage source=gemini model=%s", config.GEMINI_MODEL)
    for row in triage_mod.run_triage(store, judgments=judgments):
        log.info(
            "Triage %s @ %s: risk_zone=%s shortage=%s decision=%s",
            row["sku"],
            row["location_id"],
            row["risk_zone"],
            row["shortage_qty"],
            row["triage_decision"],
        )
    run_monitoring_once(store)
    return results


async def signal_scan_loop(stop: asyncio.Event) -> None:
    """Call the weather and news scan on a timer until `stop` is set.

    Started with the API process and cancelled when that process exits.
    The scan itself runs in a thread so Open-Meteo and GDELT do not block
    other HTTP requests.
    """
    while not stop.is_set():
        started = time.monotonic()
        try:
            # Go through the same guarded entry point as the frontend trigger,
            # so the loop and page-load scans never run on top of each other.
            trigger_scan(min_interval=0)
        except Exception:
            log.exception("Signal scan failed")
        if stop.is_set():
            return
        remaining = config.SIGNAL_SCAN_INTERVAL_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            await asyncio.sleep(0)
            continue
        try:
            await asyncio.wait_for(stop.wait(), timeout=remaining)
        except asyncio.TimeoutError:
            continue


def run_monitoring_once(store=None) -> list[dict]:
    """Build a plan only for exposures triage marked risk. Returns those plans.

    Safe rows are skipped. The four recovery steps (exposure, internal stock,
    supplier, margin, surplus) run inside planner.build_plan — plain code,
    no language-model loop.
    """
    store = store or get_store()
    seen: set[tuple[str, str]] = set()
    plans: list[dict] = []
    for exposure in store.list("exposures"):
        if exposure.get("risk_zone") != "risk":
            continue
        key = (exposure["sku"], exposure["location_id"])
        if key in seen:
            continue
        seen.add(key)
        plan = planner_mod.build_plan(store, sku=key[0], location_id=key[1])
        if plan.get("status") == "awaiting_approval":
            plans.append(plan)
            log.info("Recovery needed: %s", plan["narrative"])
    if not plans:
        log.info("No recovery needed. All open orders are covered.")
    return plans


if __name__ == "__main__":
    scan_route_signals()
