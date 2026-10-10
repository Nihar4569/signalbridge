"""Governance: who is allowed to approve a plan of this value?"""
from __future__ import annotations

from ..core import config


def route_approval(total_minor: int) -> dict:
    """Pick the approval tier for a recovery cost (integer minor units)."""
    for tier_name, ceiling in config.GOVERNANCE_TIERS:
        if ceiling is None or total_minor <= ceiling:
            return {
                "tier": tier_name,
                "threshold_minor": ceiling,
                "required_role": "executive" if tier_name == "executive" else "manager",
            }
    # Should never happen because the last tier has ceiling=None.
    return {"tier": "executive", "threshold_minor": None, "required_role": "executive"}
