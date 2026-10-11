"""Tests for the global Ask Gemini context (no network: live=False)."""
from backend.ai import global_context as gc
from backend.core.store import LocalStore


def test_context_covers_the_whole_network():
    store = LocalStore()
    context, sources, articles = gc.build_global_context(store, "anything", live=False)
    assert len(context["shipments"]) == 1
    # Nothing is threatened until triage marks a shipment at risk.
    assert context["summary"]["orders_threatened"] == 0
    assert context["customer_orders"] and context["inventory"] and context["supplier_offers"]
    assert "live_weather" not in context and articles == []
    assert all(s["kind"] == "internal" for s in sources)


def test_triage_risk_flows_into_the_context():
    store = LocalStore()
    shipment = store.get("shipments", "shipment_id", "SHP-001")
    store.upsert("shipments", "SHP-001", {**shipment, "risk_zone": "risk", "risk_reason": "Port closed"})

    context, _, _ = gc.build_global_context(store, "anything", live=False)
    assert context["summary"]["shipments_at_risk"] == 1
    assert context["shipments"][0]["why_at_risk"] == "Port closed"
    assert [p["sku"] for p in context["threatened_orders_and_recovery_plans"]] == ["JACKET-BLUE-M"]


def test_news_is_only_fetched_when_asked_about():
    assert gc.wants_news("Any strikes or closures at our ports?")
    assert gc.wants_news("Give me today's briefing")
    assert not gc.wants_news("How much revenue is at risk?")
    assert not gc.wants_news("Is there severe weather on our routes?")


def test_news_targets_follow_the_question():
    assert "Nhava Sheva" in gc.news_targets(LocalStore(), "any strike at nhava sheva?")


def test_news_targets_default_to_disrupted_ports():
    targets = gc.news_targets(LocalStore(), "what is the latest news?")
    assert targets and targets[0] == "Nhava Sheva"
    assert len(targets) <= gc.MAX_NEWS_PLACES
