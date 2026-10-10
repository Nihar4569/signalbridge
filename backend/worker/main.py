"""Scan active shipments and build recovery plans for anything at risk.

The API process runs the weather and news scan on a timer while it is up.
You can also run one pass by hand:
    python -m backend.worker.main
"""
from __future__ import annotations

import asyncio
import time

from ..adapters import news as news_adapter
from ..adapters import weather as weather_adapter
from ..core import config
from ..core.logging import get_logger
from ..core.store import get_store
from ..domain import ingestion as ingestion_mod
from ..domain import planner as planner_mod
from ..domain import triage as triage_mod
from .route_monitor import signal_scan_location_ids

log = get_logger("worker")


def scan_route_signals(store=None) -> list[dict]:
    """Check live weather + news for every location on an active route.

    Saves each result to the `signals` collection (backend/domain/ingestion.py)
    so there is a durable record, not just a log line. This is the "watch
    the world" half of monitoring. See docs/scheduler.md.
    """
    store = store or get_store()
    locations = {loc["location_id"]: loc for loc in store.list("locations")}
    results: list[dict] = []
    # GDELT allows about one search every 5 seconds. Space news calls out.
    for index, location_id in enumerate(signal_scan_location_ids()):
        location = locations.get(location_id)
        if not location:
            continue
        if index > 0:
            time.sleep(5)
        weather = (
            weather_adapter.get_weather_risk(location["lat"], location["lon"])
            if location.get("lat") is not None
            else {"ok": False, "risk": "unknown", "error": "no coordinates"}
        )
        news = news_adapter.search_disruptions(location.get("name", location_id))
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
    for row in triage_mod.run_triage(store):
        log.info(
            "Triage %s @ %s: risk_zone=%s shortage=%s decision=%s",
            row["sku"],
            row["location_id"],
            row["risk_zone"],
            row["shortage_qty"],
            row["triage_decision"],
        )
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
            await asyncio.to_thread(scan_route_signals)
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


def run_monitoring_once() -> list[dict]:
    """Build a plan for every SKU/location that has an open order. Returns plans."""
    store = get_store()
    order_lines = store.list("order_lines")

    seen: set[tuple[str, str]] = set()
    plans: list[dict] = []
    for line in order_lines:
        if line.get("status") != "open":
            continue
        key = (line["sku"], line["location_id"])
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
    run_monitoring_once()
