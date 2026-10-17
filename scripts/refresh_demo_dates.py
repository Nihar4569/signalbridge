"""Keep the demo scenario current: shift every stored date forward together.

The dataset was authored on a fixed day, so a week later shipments look overdue
and orders look past-due. This shifts ALL dates by the same number of days, so
every carefully designed relationship (which offer is feasible, which arrives
too late, which order falls short) is preserved exactly — the whole scenario
just moves forward in time.

Idempotent: if the data is already current it shifts by 0 and changes nothing.

    python -m scripts.refresh_demo_dates            # writes to DATA_BACKEND
    python -m scripts.refresh_demo_dates --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.core import config
from backend.core.store import get_store
from backend.models import doc_id_for

# Date fields we shift, per collection.
DATE_FIELDS = {
    "shipments": ["departed_at", "expected_arrival_at", "assumed_arrival_at",
                  "confirmed_arrival_at", "updated_at"],
    "order_lines": ["due_at"],
    "supplier_offers": ["delivery_latest", "expires_at"],
    "stock_balances": ["updated_at"],
}
# events store their dates inside a nested "when" object.
EVENT_WHEN = ["occurred_at", "effective_from", "effective_until", "recorded_at"]

# Keep the soonest arrival at least this far in the future, so nothing looks overdue.
LEAD_DAYS = 1


def _parse(ts: str | None) -> datetime | None:
    if not isinstance(ts, str) or not re.match(r"^\d{4}-\d{2}-\d{2}", ts):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _shift(ts: str | None, days: int) -> str | None:
    dt = _parse(ts)
    if dt is None:
        return ts
    moved = dt + timedelta(days=days)
    return moved.isoformat().replace("+00:00", "Z")


def compute_shift(shipments: list[dict]) -> int:
    """Days to add so the soonest in-transit arrival is LEAD_DAYS in the future."""
    arrivals = [
        _parse(s.get("expected_arrival_at"))
        for s in shipments
        if s.get("status") in ("in_transit", "planned")
    ]
    arrivals = [a for a in arrivals if a]
    if not arrivals:
        return 0
    target = datetime.now(timezone.utc) + timedelta(days=LEAD_DAYS)
    gap = (target - min(arrivals)).days
    return max(0, gap)


def shift_doc(collection: str, doc: dict, days: int) -> dict:
    out = dict(doc)
    for field in DATE_FIELDS.get(collection, []):
        if field in out:
            out[field] = _shift(out[field], days)
    if collection == "events" and isinstance(out.get("when"), dict):
        when = dict(out["when"])
        for field in EVENT_WHEN:
            if field in when:
                when[field] = _shift(when[field], days)
        out["when"] = when
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Shift demo dates so the scenario stays current")
    ap.add_argument("--dry-run", action="store_true", help="show the shift, write nothing")
    ap.add_argument("--days", type=int, help="force a specific shift instead of auto")
    args = ap.parse_args(argv)

    store = get_store()
    days = args.days if args.days is not None else compute_shift(store.list("shipments"))
    print(f"backend: {store.backend_name} · shift: +{days} day(s)")
    if days == 0 and args.days is None:
        print("Data is already current — nothing to do.")
        return 0

    collections = list(DATE_FIELDS) + ["events"]
    for collection in collections:
        docs = store.list(collection)
        if not docs:
            continue
        changed = 0
        for doc in docs:
            moved = shift_doc(collection, doc, days)
            if moved != doc:
                changed += 1
                if not args.dry_run:
                    store.upsert(collection, doc_id_for(collection, doc), moved)
        print(f"  {collection:16} {changed:3}/{len(docs)} documents shifted")

        # Keep the local fixtures snapshot in step with the store.
        path = Path(config.FIXTURES_DIR) / f"{collection}.json"
        if not args.dry_run and path.exists():
            local = json.loads(path.read_text(encoding="utf-8"))
            shifted = [shift_doc(collection, d, days) for d in local]
            path.write_text(json.dumps(shifted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.dry_run:
        print("\nDry run — nothing written.")
    else:
        print("\nDone. Re-run a scan so triage recomputes against the new dates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
