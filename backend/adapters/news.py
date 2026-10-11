"""News adapter — live disruption search from GDELT DOC 2.0 (free, no API key).

Two jobs:
  1. search_disruptions(...) — live news search, filtered by a location phrase +
     disruption keywords (strike, closure, storm, ...). This is the real API.
  2. fetch_events(...) — reads the pre-seeded demo events from fixtures. Used by
     the deterministic demo so it never depends on today's news.

Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/  (see docs/external_api.md)
"""
from __future__ import annotations

import requests

from ..core import config
from ..core.store import get_store


def search_disruptions(
    location_name: str,
    *,
    timespan: str | None = None,
    max_records: int | None = None,
    timeout: float | None = None,
) -> dict:
    """Search recent news for disruptions mentioning a location.

    The query filters to articles that mention the location phrase AND at least
    one disruption keyword, newest first.
    """
    timespan = timespan or config.NEWS_TIMESPAN
    max_records = max_records or config.NEWS_MAX_RECORDS
    keywords = " OR ".join(config.DISRUPTION_KEYWORDS)
    query = f'"{location_name}" ({keywords})'

    try:
        response = requests.get(
            config.GDELT_URL,
            params={
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": max_records,
                "timespan": timespan,
                "sort": "datedesc",
            },
            headers={"User-Agent": config.HTTP_USER_AGENT},
            timeout=timeout or config.HTTP_TIMEOUT,
        )

        # GDELT asks for ~1 request per 5 seconds; it returns 429 if you go faster.
        if response.status_code == 429:
            return _news_error(query, "rate_limited", "GDELT allows about 1 request every 5 seconds.")

        # GDELT sometimes returns HTTP 200 with a plain-text message (not JSON),
        # e.g. "The specified phrase is too short." Handle that cleanly.
        try:
            data = response.json()
        except ValueError:
            return _news_error(query, "no_json", response.text.strip()[:140])

        articles = data.get("articles", []) or []
        return {
            "ok": True,
            "source": "gdelt",
            "query": query,
            "count": len(articles),
            "articles": [
                {
                    "title": a.get("title"),
                    "url": a.get("url"),
                    "seendate": a.get("seendate"),
                    "domain": a.get("domain"),
                    "sourcecountry": a.get("sourcecountry"),
                }
                for a in articles
            ],
        }
    except Exception as exc:  # network / timeout — stay safe
        return _news_error(query, type(exc).__name__, "Could not reach GDELT.")


def _news_error(query: str, error: str, note: str) -> dict:
    return {
        "ok": False,
        "source": "gdelt",
        "query": query,
        "count": 0,
        "articles": [],
        "error": error,
        "note": note,
    }


def fetch_events(location_ids: list[str] | None = None) -> list[dict]:
    """Return the pre-seeded demo events from fixtures (deterministic demo)."""
    events = get_store().list("events")
    if location_ids is None:
        return events
    wanted = set(location_ids)
    return [e for e in events if (e.get("where") or {}).get("location_id") in wanted]
