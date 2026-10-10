"""Tiny Gemini helper — same REST call style as script/api_test.py.

One job: turn a recovery plan into a short, friendly explanation for a manager.
If there is no API key, or the call fails for any reason, we quietly fall back to
the plan's own built-in narrative. The app must never break because of the AI.
"""
from __future__ import annotations

import requests

from ..core import config

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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
