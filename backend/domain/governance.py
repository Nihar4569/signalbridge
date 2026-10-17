"""Governance: who approves a plan of this value? Plain rules, no AI."""
from __future__ import annotations

from ..core import config


def route_approval(total_minor: int) -> dict:
    """Pick the approval tier and its default approver for a recovery cost (paise)."""
    for tier_name, ceiling in config.GOVERNANCE_TIERS:
        if ceiling is None or total_minor <= ceiling:
            return _approval(tier_name, ceiling)
    # Should never happen because the last tier has ceiling=None.
    return _approval("executive", None)


def _approval(tier: str, ceiling: int | None) -> dict:
    approver = config.APPROVERS[tier]
    return {
        "tier": tier,
        "threshold_minor": ceiling,
        "required_role": "executive" if tier == "executive" else "manager",
        "approver_title": approver["title"],
        "approver_email": approver["email"],
    }
