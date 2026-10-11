"""Tests for the global Ask Gemini context (no network: live=False)."""
from backend.ai import global_context as gc
from backend.core.store import LocalStore

store = LocalStore()


def test_context_covers_the_whole_network():
    context, sources, articles = gc.build_global_context(store, "anything", live=False)
    assert len(context["shipments"]) == 4
    assert context["summary"]["orders_threatened"] == 2
    skus = {p["sku"] for p in context["threatened_orders_and_recovery_plans"]}
    assert skus == {"JACKET-BLUE-M", "VACCINE-10ML"}
    assert context["customer_orders"] and context["inventory"] and context["supplier_offers"]
    assert "live_weather" not in context and articles == []
    assert all(s["kind"] == "internal" for s in sources)


def test_news_is_only_fetched_when_asked_about():
    assert gc.wants_news("Any strikes or closures at our ports?")
    assert gc.wants_news("Give me today's briefing")
    assert not gc.wants_news("How much revenue is at risk?")
    assert not gc.wants_news("Is there severe weather on our routes?")


def test_news_targets_follow_the_question():
    assert gc.news_targets(store, "news about the Suez Canal")[0] == "Suez Canal"
    assert "Nhava Sheva" in gc.news_targets(store, "any strike at nhava sheva?")


def test_news_targets_default_to_disrupted_ports():
    targets = gc.news_targets(store, "what is the latest news?")
    assert targets and targets[0] == "Nhava Sheva"
    assert len(targets) <= gc.MAX_NEWS_PLACES
