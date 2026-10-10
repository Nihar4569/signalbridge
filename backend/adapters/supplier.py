"""Owned supplier simulator.

This stands in for a real supplier's reservation API. It returns a confirmed
hold so the rest of the system can treat it like a real booking. Because we own
it, it is safe to call in a demo — no real money or goods move.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone


class SupplierSimulator:
    def hold(self, *, offer_id: str, qty: int) -> dict:
        """Confirm a stock hold and return a receipt."""
        now = datetime.now(timezone.utc)
        return {
            "supplier_ref": f"RES-{uuid.uuid4().hex[:6].upper()}",
            "held_qty": qty,
            "offer_id": offer_id,
            "expires_at": (now + timedelta(hours=24)).isoformat(),
            "verified_at": now.isoformat(),
        }
