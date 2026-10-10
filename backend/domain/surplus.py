"""Predictive surplus.

When we buy replacement stock AND the original delayed shipment eventually
arrives, we may end up with extra units. Flag that overstock early so it can be
marked down or returned instead of sitting unsold.
"""
from __future__ import annotations


def forecast_surplus(
    *,
    late_shipment_units: int,
    recovery_qty: int,
    original_still_arriving: bool,
) -> dict:
    """Estimate future overstock caused by a late shipment arriving after recovery."""
    if not original_still_arriving or recovery_qty <= 0:
        return {"expected_surplus_qty": 0, "suggested_action": None}

    expected = min(late_shipment_units, recovery_qty)
    return {
        "expected_surplus_qty": expected,
        "suggested_action": "markdown" if expected > 0 else None,
    }
