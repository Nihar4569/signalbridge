"""Margin check: is this rescue worth more than it costs?

Stops us spending ₹100 to protect ₹60. All money is integer minor units (paise).
"""
from __future__ import annotations


def assess_margin(
    *,
    shortage_qty: int,
    unit_price_minor: int,
    recovery_cost_minor: int,
    penalty_at_risk_minor: int = 0,
) -> dict:
    """Weigh the cost of recovery against the revenue + penalty it protects."""
    protected_revenue_minor = shortage_qty * unit_price_minor
    net_benefit_minor = protected_revenue_minor + penalty_at_risk_minor - recovery_cost_minor
    return {
        "recovery_cost_minor": recovery_cost_minor,
        "protected_revenue_minor": protected_revenue_minor,
        "penalty_avoided_minor": penalty_at_risk_minor,
        "net_benefit_minor": net_benefit_minor,
        "verdict": "worth_it" if net_benefit_minor > 0 else "not_worth_it",
    }
