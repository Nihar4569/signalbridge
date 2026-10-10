"""Gemini calls.

Two jobs, both optional so a missing key never crashes the scan:

  - judge_shipment_risk: read the weather and news together with the
    shipments and decide whether each shipment might actually be delayed.
    This is the triage step. It is a judgment, not a keyword overlap.
  - explain_plan: turn an already-calculated recovery plan into a short
    paragraph for the manager. It does not choose the supplier or the numbers.
"""
from __future__ import annotations

import json

import requests

from ..core import config
from ..core.logging import get_logger

log = get_logger("gemini")

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def judge_shipment_risk(
    *,
    shipments: list[dict],
    signals: list[dict],
    locations: list[dict],
    products: list[dict],
) -> list[dict] | None:
    """Ask Gemini which in-transit shipments these signals could delay.

    Returns a list of {shipment_id, risk, reason}, or None when Gemini did
    not answer (no key, HTTP error, or unreadable JSON). The caller must
    not invent a risk decision in that case.
    """
    active = [s for s in shipments if s.get("status") in ("in_transit", "planned")]
    if not active or not config.GOOGLE_API_KEY:
        return None

    by_id = {loc["location_id"]: loc for loc in locations}
    names = {p["sku"]: p.get("name") for p in products}
    brief = {
        "shipments": [_shipment_brief(s, by_id, names) for s in active],
        "weather": [_weather_brief(s, by_id) for s in signals if s.get("source") == "open-meteo"],
        "news": [_news_brief(s, by_id) for s in signals if s.get("source") != "open-meteo"][:20],
        "places": [
            {"location_id": loc["location_id"], "name": loc.get("name"), "type": loc.get("type")}
            for loc in locations
        ],
    }
    prompt = (
        "You are the triage analyst for a retailer's inbound shipments.\n"
        "You receive live weather readings and news articles, plus the shipments "
        "currently on the water. Decide, for each shipment, whether there is a "
        "real possibility that this weather or news will delay it.\n"
        "Reason about the situation. A place name appearing in a headline is not "
        "enough, and a 'low' weather reading is not a delay. A storm, flood, "
        "strike, closure, congestion, or similar event can be a risk when it "
        "could affect the destination, a port the shipment uses, or the sea "
        "route named by its lane.\n"
        "Do not calculate quantities, money, or a recovery plan.\n"
        "Reply with JSON only, one object per shipment you were given, using "
        "only those shipment_id values:\n"
        '{"shipments":[{"shipment_id":"...","risk":true,"reason":"one sentence"}]}\n\n'
        f"{json.dumps(brief, default=str)}"
    )
    text = _generate(prompt, json_mode=True)
    if text is None:
        return None
    return _parse_judgments(text, {s["shipment_id"] for s in active})


def explain_plan(plan: dict) -> dict:
    """Return {'text': str, 'source': 'gemini'|'fallback'} for a plan."""
    narrative = plan.get("narrative", "No plan was produced.")

    if not config.GOOGLE_API_KEY:
        return {"text": narrative, "source": "fallback"}

    try:
        response = requests.post(
            _ENDPOINT.format(model=config.GEMINI_MODEL),
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": config.GOOGLE_API_KEY,
            },
            json={"contents": [{"parts": [{"text": _build_prompt(plan)}]}]},
            timeout=20,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return {"text": text.strip(), "source": "gemini"}
    except Exception as exc:  # network / quota / unexpected shape — stay safe
        return {"text": narrative, "source": f"fallback ({type(exc).__name__})"}


def _build_prompt(plan: dict) -> str:
    exposure = plan.get("exposure", {})
    margin = plan.get("margin_check", {})
    approval = plan.get("approval", {})
    return (
        "You are a calm supply-chain assistant. In 3-4 short sentences, explain "
        "this recovery plan to a busy retail manager in plain English. "
        "Do NOT invent numbers; use only what is given below.\n\n"
        f"Product: {plan.get('sku')} at {plan.get('location_id')}\n"
        f"Shortage: {exposure.get('shortage_qty')} units by {exposure.get('deadline')}\n"
        f"Used from our own stores: {plan.get('internal_used_qty')} units\n"
        f"Supplier chosen: {plan.get('selected_offer_id')}\n"
        f"Recovery cost (paise): {margin.get('recovery_cost_minor')}\n"
        f"Revenue protected (paise): {margin.get('protected_revenue_minor')}\n"
        f"Verdict: {margin.get('verdict')}\n"
        f"Needs approval from: {approval.get('tier')}\n"
    )


def _shipment_brief(shipment: dict, locations: dict, product_names: dict) -> dict:
    dest_id = shipment.get("destination_location_id")
    dest = locations.get(dest_id) or {}
    return {
        "shipment_id": shipment.get("shipment_id"),
        "lane_id": shipment.get("lane_id"),
        "destination": dest.get("name") or dest_id,
        "destination_type": dest.get("type"),
        "expected_arrival_at": shipment.get("expected_arrival_at"),
        "items": [
            {
                "sku": item.get("sku"),
                "name": product_names.get(item.get("sku")),
                "quantity": item.get("quantity"),
            }
            for item in shipment.get("items") or []
        ],
    }


def _weather_brief(signal: dict, locations: dict) -> dict:
    payload = signal.get("payload") or {}
    loc = locations.get(payload.get("location_id")) or {}
    return {
        "place": loc.get("name") or payload.get("location_id"),
        "place_type": loc.get("type"),
        "risk": payload.get("risk"),
        "max_wind_gust_kmh": payload.get("max_wind_gust_kmh"),
        "max_precip_mm": payload.get("max_precip_mm"),
    }


def _news_brief(signal: dict, locations: dict) -> dict:
    payload = signal.get("payload") or {}
    loc = locations.get(payload.get("location_id")) or {}
    return {
        "place_searched": loc.get("name") or payload.get("location_id"),
        "title": signal.get("title"),
        "url": signal.get("source_url"),
    }


def _generate(prompt: str, *, json_mode: bool) -> str | None:
    body: dict = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        body["generationConfig"] = {"temperature": 0, "responseMimeType": "application/json"}
    try:
        response = requests.post(
            _ENDPOINT.format(model=config.GEMINI_MODEL),
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": config.GOOGLE_API_KEY,
            },
            json=body,
            timeout=60,
        )
    except requests.RequestException as exc:
        log.warning("Gemini request failed: %s", type(exc).__name__)
        return None
    if response.status_code >= 400:
        log.warning("Gemini HTTP %s: %s", response.status_code, response.text[:180])
        return None
    try:
        parts = response.json()["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError, ValueError):
        log.warning("Gemini response had no candidate text")
        return None
    texts = [p.get("text", "").strip() for p in parts if isinstance(p, dict) and p.get("text")]
    if not texts:
        log.warning("Gemini response had no text part")
        return None
    return "\n".join(texts)


def _parse_judgments(text: str, allowed_ids: set[str]) -> list[dict] | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    rows = data.get("shipments") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    judgments = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        shipment_id = row.get("shipment_id")
        if shipment_id not in allowed_ids:
            continue
        judgments.append(
            {
                "shipment_id": shipment_id,
                "risk": row.get("risk") is True,
                "reason": row.get("reason") or "",
            }
        )
    return judgments
