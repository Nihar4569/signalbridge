"""Save weather and news readings to the `signals` collection.

Ids are deterministic, so running the scan again overwrites instead of
duplicating:
  - weather: one document per place, always holding the latest reading
             (SIG-WEATHER-{location_id})
  - news:    one document per article URL (SIG-NEWS-{hash of url})
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def weather_signal_id(location_id: str) -> str:
    return f"SIG-WEATHER-{location_id}"


def news_signal_id(url: str) -> str:
    return "SIG-NEWS-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _gdelt_time(seendate: str | None) -> str | None:
    """GDELT '20261010T080000Z' -> '2026-10-10T08:00:00Z'."""
    try:
        return datetime.strptime(seendate or "", "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def ingest_weather_signal(location: dict, weather: dict, *, store) -> dict | None:
    """Store the latest weather reading for a place. Skips failed readings."""
    if not weather.get("ok"):
        return None
    now = _now_iso()
    risk = weather.get("risk")
    doc = {
        "signal_id": weather_signal_id(location["location_id"]),
        "source": "open-meteo",
        "source_url": None,
        "title": f"Weather risk at {location.get('name', location['location_id'])}: {risk}",
        "raw_hash": None,
        "fetched_at": now,
        "published_at": now,
        "status": "processed",
        "ttl_at": None,
        "payload": {
            "location_id": location["location_id"],
            "risk": risk,
            "max_wind_gust_kmh": weather.get("max_wind_gust_kmh"),
            "max_precip_mm": weather.get("max_precip_mm"),
            "worst_weather_code": weather.get("worst_weather_code"),
            "error": weather.get("error"),
        },
    }
    store.upsert("signals", doc["signal_id"], doc)
    return doc


def ingest_news_signals(location: dict, news: dict, *, store) -> list[dict]:
    """Store each article once. The same URL seen again overwrites its document."""
    saved: list[dict] = []
    for article in news.get("articles") or []:
        url = article.get("url")
        if not url:
            continue
        doc = {
            "signal_id": news_signal_id(url),
            "source": "gdelt",
            "source_url": url,
            "title": (article.get("title") or "")[:300],
            "raw_hash": hashlib.sha1(url.encode("utf-8")).hexdigest(),
            "fetched_at": _now_iso(),
            "published_at": _gdelt_time(article.get("seendate")),
            "status": "new",
            "ttl_at": None,
            "payload": {
                "location_id": location["location_id"],
                "domain": article.get("domain"),
                "country": article.get("sourcecountry"),
            },
        }
        store.upsert("signals", doc["signal_id"], doc)
        saved.append(doc)
    return saved
