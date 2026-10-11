"""Approval tier and default approver come from plain rules (no AI)."""
from backend.domain import governance


def test_small_plan_goes_to_the_warehouse_manager():
    approval = governance.route_approval(4_000_000)  # Rs 40,000
    assert approval["tier"] == "local_planner"
    assert approval["approver_title"] == "Warehouse Operations Manager"


def test_medium_plan_goes_to_the_regional_manager():
    approval = governance.route_approval(14_900_000)  # Rs 1,49,000
    assert approval["tier"] == "regional_manager"
    assert approval["approver_title"] == "Regional Supply Chain Manager"


def test_large_plan_goes_to_the_head_of_supply_chain():
    approval = governance.route_approval(225_820_000)  # Rs 22.6 lakh
    assert approval["tier"] == "executive"
    assert approval["approver_title"] == "Head of Supply Chain"
    assert "@" in approval["approver_email"]


def test_tier_boundary_is_inclusive():
    assert governance.route_approval(5_000_000)["tier"] == "local_planner"
    assert governance.route_approval(5_000_001)["tier"] == "regional_manager"
