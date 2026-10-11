"""Read helpers that turn stored records into what the dashboard and Gemini show.

Real data (Firestore) only stores facts: triage writes `risk_zone` /
`risk_reason` on shipments, and the scan writes weather + news `signals`.
These helpers derive the display view from those facts in one place.
"""
from __future__ import annotations


def shipment_health(shipment: dict) -> str:
    """on_time | at_risk | delayed. Triage (risk_zone) is the source of truth."""
    if shipment.get("delay_state") == "confirmed_delayed":
        return "delayed"
    if shipment.get("risk_zone") == "risk":
        return "at_risk"
    return "on_time"


def lane_points(lane: dict | None, locations: dict) -> list[dict]:
    """Ordered points to draw: origin location, the lane's waypoints, destination.

    Each point is {name, lat, lon, kind}. Waypoints without a kind are "sea".
    """
    if not lane:
        return []
    points: list[dict] = []

    def add(name, lat, lon, kind):
        if lat is None or lon is None:
            return
        if points and (points[-1]["lat"], points[-1]["lon"]) == (lat, lon):
            return
        points.append({"name": name, "lat": lat, "lon": lon, "kind": kind})

    origin = locations.get(lane.get("origin_location_id")) or {}
    add(origin.get("name"), origin.get("lat"), origin.get("lon"), origin.get("type") or "origin")
    for p in lane.get("points") or []:
        add(p.get("name"), p.get("lat"), p.get("lon"), p.get("kind") or "sea")
    dest = locations.get(lane.get("destination_location_id")) or {}
    add(dest.get("name"), dest.get("lat"), dest.get("lon"), "destination")
    return points


def _near(a: dict, lat: float, lon: float) -> bool:
    # ~110 km box: a storm cell reaches well beyond the exact sample point.
    return abs(a["lat"] - lat) <= 1.0 and abs(a["lon"] - lon) <= 1.0


def active_alerts(store) -> list[dict]:
    """Stored alerts plus every disruptive signal (high-risk weather, any news)."""
    locations = {loc["location_id"]: loc for loc in store.list("locations")}
    lanes = store.list("lanes")
    alerts = list(store.list("alerts"))

    for signal in store.list("signals"):
        payload = signal.get("payload") or {}
        is_weather = signal.get("source") == "open-meteo"
        if is_weather and payload.get("risk") != "high":
            continue
        loc = locations.get(payload.get("location_id")) or {}
        if loc.get("lat") is None:
            continue
        lane_id = next(
            (
                lane["lane_id"]
                for lane in lanes
                if any(_near(p, loc["lat"], loc["lon"]) for p in lane_points(lane, locations))
            ),
            None,
        )
        if is_weather:
            detail = (
                f"Gusts up to {payload.get('max_wind_gust_kmh')} km/h, "
                f"rain up to {payload.get('max_precip_mm')} mm"
            )
        else:
            detail = signal.get("source_url") or ""
        alerts.append({
            "alert_id": signal.get("signal_id"),
            "type": "weather" if is_weather else "disruption",
            "severity": "high",
            "lat": loc["lat"],
            "lon": loc["lon"],
            "title": signal.get("title"),
            "detail": detail,
            "lane_id": lane_id,
            "fetched_at": signal.get("fetched_at"),
        })
    return alerts
