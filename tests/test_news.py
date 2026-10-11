"""News adapter: GDELT first, Google News RSS when GDELT rate limits (no network)."""
from backend.adapters import news

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Tanker attacked in Strait of Hormuz - Al Jazeera</title><link>https://news.google.com/a</link>
<pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate><source url="https://www.aljazeera.com">Al Jazeera</source></item>
<item><title>Iran says route will be closed - The Guardian</title><link>https://news.google.com/b</link>
<pubDate>Thu, 08 Oct 2026 09:00:00 GMT</pubDate><source url="https://www.theguardian.com">The Guardian</source></item>
</channel></rss>"""


class _Resp:
    def __init__(self, status, content=b"", payload=None):
        self.status_code, self.content, self._payload = status, content, payload
        self.text = content.decode()

    def json(self):
        if self._payload is None:
            raise ValueError
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise news.requests.HTTPError(str(self.status_code))


def _reset(monkeypatch):
    news._cache.clear()
    monkeypatch.setattr(news, "_gdelt_paused_until", 0.0)
    monkeypatch.setattr(news, "_last_gdelt_call", 0.0)
    monkeypatch.setattr(news.time, "sleep", lambda s: None)


def test_falls_back_to_google_news_and_pauses_gdelt(monkeypatch):
    _reset(monkeypatch)
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return _Resp(429, b"Please limit requests") if "gdelt" in url else _Resp(200, RSS)

    monkeypatch.setattr(news.requests, "get", fake_get)
    result = news.search_disruptions("Strait of Hormuz")

    assert result["ok"] and result["source"] == "google-news" and result["gdelt_error"] == "rate_limited"
    first = result["articles"][0]
    assert first["title"] == "Iran says route will be closed"  # newest first, " - Source" stripped
    assert first["seendate"] == "20261008T090000Z" and first["domain"] == "www.theguardian.com"

    news._cache.clear()
    news.search_disruptions("Black Sea")
    assert sum("gdelt" in u for u in calls) == 1  # GDELT paused after the 429


def test_gdelt_used_when_it_answers(monkeypatch):
    _reset(monkeypatch)
    payload = {"articles": [{"title": "Port closed", "url": "https://x.com/1", "seendate": "20261010T080000Z", "domain": "x.com"}]}
    monkeypatch.setattr(news.requests, "get", lambda url, **kw: _Resp(200, b"{}", payload))
    result = news.search_disruptions("Red Sea")
    assert result["source"] == "gdelt" and result["articles"][0]["provider"] == "gdelt"
