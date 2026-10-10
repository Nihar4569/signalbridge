"""Scan active shipments and build recovery plans for anything at risk.

In production this is woken by Cloud Scheduler. Here you can just run it once:
    python -m backend.worker.main
"""
from __future__ import annotations

from ..adapters import news as news_adapter
from ..adapters import weather as weather_adapter
from ..core.logging import get_logger
from ..core.store import get_store
from ..domain import planner as planner_mod
from .route_monitor import active_shipment_locations

log = get_logger("worker")


def scan_route_signals() -> list[dict]:
    """Check live weather + news for every location on an active route.

    This is the "watch the world" half of monitoring. See docs/scheduler.md.
    """
    locations = {loc["location_id"]: loc for loc in get_store().list("locations")}
    results: list[dict] = []
    for location_id in active_shipment_locations():
        location = locations.get(location_id)
        if not location:
            continue
        weather = (
            weather_adapter.get_weather_risk(location["lat"], location["lon"])
            if location.get("lat") is not None
            else {"risk": "unknown"}
        )
        news = news_adapter.search_disruptions(location.get("name", location_id))
        results.append(
            {
                "location_id": location_id,
                "weather_risk": weather.get("risk"),
                "news_count": news.get("count", 0),
            }
        )
        log.info(
            "Signal scan %s: weather=%s, news=%s",
            location_id,
            weather.get("risk"),
            news.get("count", news.get("error")),
        )
    return results


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
