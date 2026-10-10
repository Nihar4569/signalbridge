"""Live signals = real weather + news for a location (Open-Meteo + GDELT)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...adapters import news as news_adapter
from ...adapters import weather as weather_adapter
from ..deps import store_dep

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/{location_id}")
def get_signals(location_id: str, store=Depends(store_dep)) -> dict:
    """Return the live weather risk and recent disruption news for a location."""
    location = store.get("locations", "location_id", location_id)
    if not location:
        return {"error": f"unknown location: {location_id}"}

    if location.get("lat") is not None:
        weather = weather_adapter.get_weather_risk(location["lat"], location["lon"])
    else:
        weather = {"ok": False, "risk": "unknown", "error": "no coordinates"}

    news = news_adapter.search_disruptions(location.get("name", location_id))

    return {
        "location_id": location_id,
        "name": location.get("name"),
        "weather": weather,
        "news": news,
    }
