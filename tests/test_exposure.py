"""Tests for the core shortage math. These need no cloud and no API key."""
from backend.domain import exposure as exposure_mod

DEADLINE = "2026-10-16T12:00:00Z"

SHIPMENTS = [
    {
        "destination_location_id": "WH-MUM",
        "status": "in_transit",
        "items": [{"sku": "JACKET-BLUE-M", "quantity": 500}],
        "expected_arrival_at": "2026-10-12T12:00:00Z",
        "assumed_arrival_at": "2026-10-19T12:00:00Z",
        "delay_state": "assumed_delayed",
    }
]

ORDER_LINES = [
    {
        "sku": "JACKET-BLUE-M",
        "location_id": "WH-MUM",
        "quantity": 200,
        "due_at": DEADLINE,
        "status": "open",
    }
]


def test_baseline_has_no_shortage():
    result = exposure_mod.assess_exposure(
        sku="JACKET-BLUE-M",
        location_id="WH-MUM",
        deadline=DEADLINE,
        on_hand_qty=120,
        shipments=SHIPMENTS,
        order_lines=ORDER_LINES,
        scenario="baseline",
    )
    assert result["supply_by_deadline"] == 620
    assert result["shortage_qty"] == 0
    assert result["is_actionable"] is False


def test_disruption_creates_80_unit_shortage():
    result = exposure_mod.assess_exposure(
        sku="JACKET-BLUE-M",
        location_id="WH-MUM",
        deadline=DEADLINE,
        on_hand_qty=120,
        shipments=SHIPMENTS,
        order_lines=ORDER_LINES,
        scenario="disrupted",
    )
    # The 500 units now arrive after the deadline, so only on-hand 120 count.
    assert result["supply_by_deadline"] == 120
    assert result["demand_by_deadline"] == 200
    assert result["shortage_qty"] == 80
    assert result["is_actionable"] is True


def test_seeded_delay_state_alone_is_not_a_disruption():
    assert exposure_mod.is_disrupted(SHIPMENTS, "JACKET-BLUE-M", "WH-MUM") is False
    marked = [dict(SHIPMENTS[0], risk_zone="risk")]
    assert exposure_mod.is_disrupted(marked, "JACKET-BLUE-M", "WH-MUM") is True


def test_closed_orders_are_ignored():
    lines = [dict(ORDER_LINES[0], status="closed")]
    result = exposure_mod.assess_exposure(
        sku="JACKET-BLUE-M",
        location_id="WH-MUM",
        deadline=DEADLINE,
        on_hand_qty=0,
        shipments=[],
        order_lines=lines,
        scenario="disrupted",
    )
    assert result["demand_by_deadline"] == 0
    assert result["shortage_qty"] == 0
