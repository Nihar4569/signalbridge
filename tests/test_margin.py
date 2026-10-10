"""Tests for the margin check."""
from backend.domain import margin as margin_mod


def test_recovery_is_worth_it_when_benefit_positive():
    result = margin_mod.assess_margin(
        shortage_qty=80,
        unit_price_minor=249900,
        recovery_cost_minor=11300000,
        penalty_at_risk_minor=5000000,
    )
    assert result["protected_revenue_minor"] == 80 * 249900
    assert result["verdict"] == "worth_it"
    assert result["net_benefit_minor"] > 0


def test_recovery_not_worth_it_when_too_expensive():
    result = margin_mod.assess_margin(
        shortage_qty=1,
        unit_price_minor=100,
        recovery_cost_minor=1_000_000,
    )
    assert result["verdict"] == "not_worth_it"
    assert result["net_benefit_minor"] < 0
