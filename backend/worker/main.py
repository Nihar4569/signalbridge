"""Scan active shipments and build recovery plans for anything at risk.

In production this is woken by Cloud Scheduler. Here you can just run it once:
    python -m backend.worker.main
"""
from __future__ import annotations

from ..core.logging import get_logger
from ..core.store import get_store
from ..domain import planner as planner_mod

log = get_logger("worker")


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
    run_monitoring_once()
