"""News adapter: live disruption headlines for a place (free, no API key).

search_disruptions(place) asks for articles that mention the place AND a
disruption keyword (strike, storm, attack, ...) from the last few days.

Two free sources, same query, same result shape:
  1. GDELT DOC 2.0         - primary. Allows ~1 request per 5 seconds.
  2. Google News RSS search - fallback, used while GDELT is rate limiting us
                              or timing out (GDELT is paused for 5 minutes).

Every result says which provider answered ("gdelt" or "google-news").
Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/  (see docs/external_api.md)
"""
from __future__ import annotations

import threading
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

from ..core import config
from ..core.store import get_store

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
GDELT_GAP_SECONDS = 5.2
GDELT_PAUSE_SECONDS = 300
CACHE_SECONDS = 600
MAX_RSS_BYTES = 2_000_000

_lock = threading.Lock()
_last_gdelt_call = 0.0
_gdelt_paused_until = 0.0
_cache: dict[tuple, tuple[float, dict]] = {}


def search_disruptions(
    location_name: str,
    *,
    timespan: str | None = None,
    max_records: int | None = None,
    timeout: float | None = None,
) -> dict:
    """Recent disruption news mentioning a place, newest first."""
    timespan = timespan or config.NEWS_TIMESPAN
    max_records = max_records or config.NEWS_MAX_RECORDS
    timeout = timeout or config.HTTP_TIMEOUT
    keywords = " OR ".join(config.DISRUPTION_KEYWORDS)
    query = f'"{location_name}" ({keywords})'

    key = (query, timespan, max_records)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]

    result = _search_gdelt(query, timespan, max_records, timeout)
    if not result["ok"]:
        fallback = _search_google_news(query, timespan, max_records, timeout)
        fallback["gdelt_error"] = result.get("error")
        result = fallback if fallback["ok"] else result
    if result["ok"]:
        _cache[key] = (time.time(), result)
    return result


def _search_gdelt(query: str, timespan: str, max_records: int, timeout: float) -> dict:
    global _last_gdelt_call, _gdelt_paused_until
    with _lock:
        if time.time() < _gdelt_paused_until:
            return _news_error("gdelt", query, "paused", "GDELT rate-limited us recently.")
        wait = GDELT_GAP_SECONDS - (time.time() - _last_gdelt_call)
        if wait > 0:
            time.sleep(wait)
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
                timeout=timeout,
            )
        except requests.RequestException as exc:
            _gdelt_paused_until = time.time() + GDELT_PAUSE_SECONDS
            return _news_error("gdelt", query, type(exc).__name__, "Could not reach GDELT.")
        finally:
            _last_gdelt_call = time.time()

        if response.status_code == 429:
            _gdelt_paused_until = time.time() + GDELT_PAUSE_SECONDS
            return _news_error("gdelt", query, "rate_limited", "GDELT allows about 1 request every 5 seconds.")

    # GDELT sometimes answers 200 with a plain-text message instead of JSON.
    try:
        data = response.json()
    except ValueError:
        return _news_error("gdelt", query, "no_json", response.text.strip()[:140])

    articles = [
        {
            "title": a.get("title"),
            "url": a.get("url"),
            "seendate": a.get("seendate"),
            "domain": a.get("domain"),
            "sourcecountry": a.get("sourcecountry"),
            "provider": "gdelt",
        }
        for a in data.get("articles", []) or []
    ]
    return {"ok": True, "source": "gdelt", "query": query, "count": len(articles), "articles": articles}


def _search_google_news(query: str, timespan: str, max_records: int, timeout: float) -> dict:
    """Google News RSS search: supports "phrases", OR, and when:3d."""
    try:
        response = requests.get(
            GOOGLE_NEWS_RSS,
            params={"q": f"{query} when:{timespan}", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            headers={"User-Agent": config.HTTP_USER_AGENT},
            timeout=timeout,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content[:MAX_RSS_BYTES])
    except (requests.RequestException, ET.ParseError) as exc:
        return _news_error("google-news", query, type(exc).__name__, "Could not reach Google News.")

    articles = []
    for item in root.findall("./channel/item"):
        source = item.find("source")
        source_name = (source.text if source is not None else "") or ""
        title = item.findtext("title") or ""
        if source_name and title.endswith(" - " + source_name):
            title = title[: -len(" - " + source_name)]
        articles.append({
            "title": title,
            "url": item.findtext("link"),
            "seendate": _rss_time(item.findtext("pubDate")),
            "domain": urlparse(source.get("url", "")).netloc if source is not None else None,
            "source_name": source_name,
            "sourcecountry": None,
            "provider": "google-news",
        })
    articles.sort(key=lambda a: a["seendate"] or "", reverse=True)
    articles = articles[:max_records]
    return {"ok": True, "source": "google-news", "query": query, "count": len(articles), "articles": articles}


def _rss_time(value: str | None) -> str | None:
    """RSS 'Wed, 08 Oct 2026 07:00:00 GMT' -> GDELT style '20261008T070000Z'."""
    try:
        return parsedate_to_datetime(value).strftime("%Y%m%dT%H%M%SZ")
    except (TypeError, ValueError):
        return None


def _news_error(source: str, query: str, error: str, note: str) -> dict:
    return {
        "ok": False,
        "source": source,
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
