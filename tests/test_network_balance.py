"""Nearby own-warehouse ranking. Distance is attached; default order stays richest-first."""
from backend.domain.network_balance import find_internal_surplus

LOCATIONS = [
    {"location_id": "WH-MUM", "type": "dc", "lat": 19.08, "lon": 72.88, "active": True},
    {"location_id": "NEAR", "type": "dark_store", "lat": 19.10, "lon": 72.90, "active": True},
    {"location_id": "FAR", "type": "dc", "lat": 28.61, "lon": 77.21, "active": True},
]
BALANCES = [
    {"sku": "JACKET-BLUE-M", "location_id": "NEAR", "on_hand_qty": 5, "reserved_qty": 0},
    {"sku": "JACKET-BLUE-M", "location_id": "FAR", "on_hand_qty": 40, "reserved_qty": 0},
]


def test_default_order_is_richest_first_and_includes_distance():
    options = find_internal_surplus(
        sku="JACKET-BLUE-M",
        exclude_location_id="WH-MUM",
        stock_balances=BALANCES,
        locations=LOCATIONS,
        origin_location_id="WH-MUM",
    )
    assert [o["location_id"] for o in options] == ["FAR", "NEAR"]
    assert options[0]["distance_km"] > options[1]["distance_km"]


def test_distance_sort_puts_the_nearer_warehouse_first():
    options = find_internal_surplus(
        sku="JACKET-BLUE-M",
        exclude_location_id="WH-MUM",
        stock_balances=BALANCES,
        locations=LOCATIONS,
        origin_location_id="WH-MUM",
        sort_by="distance",
    )
    assert [o["location_id"] for o in options] == ["NEAR", "FAR"]
