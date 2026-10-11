"""Read helpers that turn stored records into what the dashboard and Gemini show.

Real data (Firestore) only stores facts: triage writes `risk_zone` /
`risk_reason` on shipments, and the scan writes weather + news `signals`.
These helpers derive the display view from those facts in one place.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..core import config

NEWS_ALERT_DAYS = 3


def is_disruptive(signal: dict) -> bool:
    """High-risk weather, or recent news whose headline names a disruption."""
    payload = signal.get("payload") or {}
    if signal.get("source") == "open-meteo":
        return payload.get("risk") == "high"
    since = (datetime.now(timezone.utc) - timedelta(days=NEWS_ALERT_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    if (signal.get("published_at") or "") < since:
        return False
    title = (signal.get("title") or "").lower()
    return bool(payload.get("event_type")) or any(word in title for word in config.DISRUPTION_KEYWORDS)

def shipment_health(shipment: dict) -> str:
    """on_time | at_risk | delayed. Triage (risk_zone) is the source of truth."""
    if shipment.get("delay_state") == "confirmed_delayed":
        return "delayed"
    if shipment.get("risk_zone") == "risk":
        return "at_risk"
    return "on_time"


def shipment_progress(shipment: dict) -> float:
    """How far along its lane a shipment is (0-1), from departure and ETA dates."""
    try:
        start = datetime.fromisoformat(shipment["departed_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(shipment["expected_arrival_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        return float(shipment.get("progress", 0.5))
    done = (datetime.now(timezone.utc) - start) / (end - start)
    return round(min(max(done, 0.02), 0.98), 3)


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
    """Stored alerts, high-risk weather, and one news alert per place (latest headline)."""
    locations = {loc["location_id"]: loc for loc in store.list("locations")}
    lanes = store.list("lanes")
    alerts = list(store.list("alerts"))

    weather, news_by_place = [], {}
    for signal in store.list("signals"):
        if not is_disruptive(signal):
            continue
        if signal.get("source") == "open-meteo":
            weather.append(signal)
        else:
            news_by_place.setdefault((signal.get("payload") or {}).get("location_id"), []).append(signal)

    latest_news = []
    for items in news_by_place.values():
        items.sort(key=lambda s: s.get("published_at") or "", reverse=True)
        latest_news.append((items[0], len(items)))

    for signal, count in [(s, 1) for s in weather] + latest_news:
        payload = signal.get("payload") or {}
        is_weather = signal.get("source") == "open-meteo"
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
            title = signal.get("title")
            detail = (
                f"Gusts up to {payload.get('max_wind_gust_kmh')} km/h, "
                f"rain up to {payload.get('max_precip_mm')} mm"
            )
        else:
            title = f"{loc.get('name')}: {signal.get('title')}"
            detail = f"{count} disruption report(s) in the last {NEWS_ALERT_DAYS} days"
        alerts.append({
            "alert_id": signal.get("signal_id"),
            "type": "weather" if is_weather else "disruption",
            "severity": "high",
            "lat": loc["lat"],
            "lon": loc["lon"],
            "title": title,
            "detail": detail,
            "source_url": signal.get("source_url"),
            "lane_id": lane_id,
            "fetched_at": signal.get("fetched_at"),
        })
    return alerts
