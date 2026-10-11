"""Weather/news -> signals/{id}: deterministic ids, no duplicate documents."""
from backend.core.store import LocalStore
from backend.domain import ingestion

LOCATION = {"location_id": "IN-JNPA", "name": "Nhava Sheva port", "lat": 18.95, "lon": 72.94}


def test_weather_signal_uses_one_fixed_id_per_location():
    store = LocalStore()
    weather_1 = {"ok": True, "risk": "low", "max_wind_gust_kmh": 10.0}
    weather_2 = {"ok": True, "risk": "high", "max_wind_gust_kmh": 70.0}

    ingestion.ingest_weather_signal(LOCATION, weather_1, store=store)
    ingestion.ingest_weather_signal(LOCATION, weather_2, store=store)

    signals = store.list("signals")
    assert len(signals) == 1  # overwritten, not duplicated
    assert signals[0]["payload"]["risk"] == "high"  # holds the latest reading
    assert signals[0]["signal_id"] == ingestion.weather_signal_id("IN-JNPA")


def test_news_signal_same_article_does_not_duplicate():
    store = LocalStore()
    article = {
        "title": "Terminal operations suspended at Nhava Sheva",
        "url": "https://example.com/article-1",
        "seendate": "20261010T080000Z",
        "domain": "example.com",
    }
    news = {"ok": True, "count": 1, "articles": [article]}

    ingestion.ingest_news_signals(LOCATION, news, store=store)
    ingestion.ingest_news_signals(LOCATION, news, store=store)  # same article again

    signals = store.list("signals")
    assert len(signals) == 1
    assert signals[0]["title"] == article["title"]


def test_news_signal_different_article_creates_second_document():
    store = LocalStore()
    article_a = {"title": "A", "url": "https://example.com/a", "seendate": "20261010T080000Z"}
    article_b = {"title": "B", "url": "https://example.com/b", "seendate": "20261010T090000Z"}
    news = {"ok": True, "count": 2, "articles": [article_a, article_b]}

    ingestion.ingest_news_signals(LOCATION, news, store=store)

    signals = store.list("signals")
    assert len(signals) == 2
    assert {s["title"] for s in signals} == {"A", "B"}


def test_scan_route_signals_writes_signals_for_watched_locations(monkeypatch):
    """End-to-end: scan_route_signals() (backend/worker/main.py) persists signals."""
    from backend.worker import main as worker_main

    store = LocalStore()
    monkeypatch.setattr("backend.worker.main.get_store", lambda: store)
    monkeypatch.setattr(
        "backend.worker.route_monitor.get_store", lambda: store
    )
    monkeypatch.setattr(
        worker_main.weather_adapter,
        "get_weather_risk",
        lambda lat, lon, forecast_days=3: {"ok": True, "risk": "low"},
    )
    monkeypatch.setattr(
        worker_main.news_adapter,
        "search_disruptions",
        lambda name, **kw: {"ok": True, "count": 0, "articles": []},
    )
    # Avoid real sleep() and a live Gemini call between locations in the test.
    monkeypatch.setattr(worker_main.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(worker_main.gemini_mod, "judge_shipment_risk", lambda **kwargs: None)

    worker_main.scan_route_signals(store=store)

    signals = store.list("signals")
    # One weather signal per watched location (WH-MUM, IN-JNPA on the fixtures).
    weather_signals = [s for s in signals if s["source"] == "open-meteo"]
    assert len(weather_signals) == 2
