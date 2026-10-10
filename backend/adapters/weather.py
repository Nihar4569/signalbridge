"""Weather adapter — live forecast from Open-Meteo (free, no API key).

We ask for a few hours of forecast at a location's coordinates and turn it into
a single simple risk level: low / medium / high. If the call fails, we return
risk "unknown" instead of crashing.

Docs: https://open-meteo.com/en/docs   (see docs/external_api.md)
"""
from __future__ import annotations

import requests

from ..core import config


def _risk_level(max_precip_mm: float, max_gust_kmh: float, worst_code: int) -> str:
    if (
        max_gust_kmh >= config.WEATHER_WIND_GUST_HIGH_KMH
        or max_precip_mm >= config.WEATHER_PRECIP_HIGH_MM
        or worst_code in config.WEATHER_STORM_CODES
    ):
        return "high"
    if max_gust_kmh >= config.WEATHER_WIND_GUST_MED_KMH or max_precip_mm >= config.WEATHER_PRECIP_MED_MM:
        return "medium"
    return "low"


def get_weather_risk(lat: float, lon: float, forecast_days: int = 3) -> dict:
    """Return a weather-risk summary for one point (filtered by lat/lon + time)."""
    try:
        response = requests.get(
            config.OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation,wind_speed_10m,wind_gusts_10m,weather_code",
                "forecast_days": forecast_days,
                "timezone": "UTC",
            },
            headers={"User-Agent": config.HTTP_USER_AGENT},
            timeout=config.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        hourly = response.json().get("hourly", {})

        precip = [x for x in hourly.get("precipitation", []) if x is not None]
        gusts = [x for x in hourly.get("wind_gusts_10m", []) if x is not None]
        codes = [x for x in hourly.get("weather_code", []) if x is not None]

        max_precip = max(precip) if precip else 0.0
        max_gust = max(gusts) if gusts else 0.0
        worst_code = max(codes) if codes else 0

        return {
            "ok": True,
            "source": "open-meteo",
            "max_precip_mm": round(max_precip, 1),
            "max_wind_gust_kmh": round(max_gust, 1),
            "worst_weather_code": worst_code,
            "risk": _risk_level(max_precip, max_gust, worst_code),
        }
    except Exception as exc:  # network / bad response — never crash the caller
        return {"ok": False, "source": "open-meteo", "risk": "unknown", "error": type(exc).__name__}
