"""Display helpers over real (Firestore-shaped) records."""
from backend.core.store import LocalStore
from backend.domain import network

LOCATIONS = {
    "MX-ZLO": {"location_id": "MX-ZLO", "name": "Manzanillo port", "type": "port", "lat": 19.05, "lon": -104.3},
    "WH-ZLO": {"location_id": "WH-ZLO", "name": "Manzanillo DC", "type": "dc", "lat": 19.1, "lon": -104.34},
    "EP-1": {"location_id": "EP-1", "name": "Eastern Pacific", "type": "sea_waypoint", "lat": 18.5, "lon": -104.9},
}
LANE = {
    "lane_id": "LANE-EPAC-ZLO",
    "origin_location_id": "MX-ZLO",
    "destination_location_id": "WH-ZLO",
    "points": [{"name": "Hurricane position", "lat": 19.1, "lon": -105.2}],
}


def test_health_comes_from_triage():
    assert network.shipment_health({"risk_zone": "risk"}) == "at_risk"
    assert network.shipment_health({"risk_zone": "safe"}) == "on_time"
    assert network.shipment_health({}) == "on_time"
    assert network.shipment_health({"delay_state": "confirmed_delayed"}) == "delayed"


def test_lane_points_run_origin_waypoints_destination():
    points = network.lane_points(LANE, LOCATIONS)
    assert [p["kind"] for p in points] == ["port", "sea", "destination"]
    assert points[0]["name"] == "Manzanillo port"
    assert network.lane_points(None, LOCATIONS) == []


def test_only_high_weather_signals_become_alerts():
    store = LocalStore()
    for loc in LOCATIONS.values():
        store.upsert("locations", loc["location_id"], loc)
    store.upsert("lanes", LANE["lane_id"], LANE)
    store.upsert("signals", "SIG-WEATHER-EP-1", {
        "signal_id": "SIG-WEATHER-EP-1", "source": "open-meteo", "title": "Weather risk at Eastern Pacific: high",
        "payload": {"location_id": "EP-1", "risk": "high", "max_wind_gust_kmh": 192.2, "max_precip_mm": 24.2},
    })
    store.upsert("signals", "SIG-WEATHER-WH-ZLO", {
        "signal_id": "SIG-WEATHER-WH-ZLO", "source": "open-meteo", "title": "Weather risk at Manzanillo DC: low",
        "payload": {"location_id": "WH-ZLO", "risk": "low"},
    })

    alerts = network.active_alerts(store)
    assert [a["alert_id"] for a in alerts] == ["SIG-WEATHER-EP-1"]
    assert alerts[0]["type"] == "weather"
    assert alerts[0]["lane_id"] == "LANE-EPAC-ZLO"
