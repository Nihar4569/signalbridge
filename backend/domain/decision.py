"""Evidence and decision views assembled from records, without model or network calls."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from . import exposure as exposure_mod


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def route_location_ids(shipment: dict, lanes: dict) -> set[str]:
    lane = lanes.get(shipment.get("lane_id")) or {}
    return {
        value
        for value in (
            shipment.get("destination_location_id"),
            lane.get("origin_location_id"),
            lane.get("destination_location_id"),
            *(point.get("location_id") for point in lane.get("points", [])),
        )
        if value
    }


def resolved_notice_ids(assessment: dict | None, signals: list[dict]) -> set[str]:
    """A cited cancellation cannot suppress a separate attack or an updated source."""
    if not assessment or assessment.get("event_status") != "cancelled":
        return set()
    by_id = {signal["signal_id"]: signal for signal in signals}
    resolved = set()
    for reference in assessment.get("evidence", []):
        signal = by_id.get(reference["signal_id"], {})
        text = (signal.get("payload") or {}).get("notice_text") or signal.get("title") or ""
        if reference["quote"] not in text:
            continue
        if any(word in text.lower() for word in ("attack", "missile", "drone", "seized")):
            continue
        if re.search(
            r"\b(cancelled|canceled|cancels|called off|lifted|reopened|resumed)\b",
            reference["quote"],
            re.IGNORECASE,
        ):
            resolved.add(reference["signal_id"])
    return resolved


def evidence_records(signals: list[dict], locations: list[dict], *, as_of=None) -> list[dict]:
    """Keep source times and original text. A fetch timestamp is not a publication date."""
    now = as_of or utc_now()
    places = {item["location_id"]: item for item in locations}
    records = []
    for signal in signals:
        payload = signal.get("payload") or {}
        weather = signal.get("source") == "open-meteo"
        timestamp = signal.get("fetched_at") if weather else signal.get("published_at")
        try:
            age = now - exposure_mod.parse_ts(timestamp or "")
            current = timedelta(minutes=-5) <= age <= timedelta(hours=3 if weather else 72)
        except (ValueError, TypeError):
            current = False
        text = payload.get("notice_text") or signal.get("title") or ""
        if weather:
            text = (
                f"{text}. Gusts: {payload.get('max_wind_gust_kmh')} km/h. "
                f"Rain: {payload.get('max_precip_mm')} mm. Risk: {payload.get('risk')}."
            )
        location_id = payload.get("location_id")
        url = signal.get("source_url") or ""
        records.append(
            {
                "signal_id": signal["signal_id"],
                "title": signal.get("title") or "Untitled source",
                "text": text[:4000],
                "source": signal.get("source"),
                "source_url": url if urlparse(url).scheme in ("http", "https") else None,
                "published_at": signal.get("published_at"),
                "fetched_at": signal.get("fetched_at"),
                "location_id": location_id,
                "place": places.get(location_id, {}).get("name", location_id),
                "current": current,
                "event_id": payload.get("event_id"),
            }
        )
    return records


def build_decision_brief(store, plan: dict, *, as_of=None) -> dict:
    """Join stored interpretations to source records and the calculated plan."""
    now = as_of or utc_now()
    sku, location_id = plan["sku"], plan["location_id"]
    lanes = {lane["lane_id"]: lane for lane in store.list("lanes")}
    locations = store.list("locations")
    sources = {
        item["signal_id"]: item
        for item in evidence_records(store.list("signals"), locations, as_of=now)
    }
    interpretations, evidence, warnings = [], {}, []
    for shipment in store.list("shipments"):
        if shipment.get("status") not in ("in_transit", "planned"):
            continue
        if shipment.get("destination_location_id") != location_id:
            continue
        if not any(item.get("sku") == sku for item in shipment.get("items", [])):
            continue
        assessment = shipment.get("risk_assessment") or {}
        route_ids = route_location_ids(shipment, lanes)
        cited = assessment.get("evidence") or []
        cited_ids = {item["signal_id"] for item in cited}
        policy_ids = set(assessment.get("policy_evidence_ids") or [])
        for source in sources.values():
            if source["location_id"] in route_ids or source["signal_id"] in cited_ids:
                item = evidence.setdefault(source["signal_id"], {**source, "citations": []})
                for reference in cited:
                    if reference["signal_id"] == source["signal_id"]:
                        if reference["quote"] in source["text"]:
                            item["citations"].append(
                                {
                                    "shipment_id": shipment["shipment_id"],
                                    "quote": reference["quote"],
                                }
                            )
                        else:
                            warnings.append(
                                "A cited source changed since assessment. Reassess before acting."
                            )
                if source["signal_id"] in policy_ids:
                    item["policy_evidence"] = True
        if not assessment:
            warnings.append(
                "Some shipment flags predate evidence-linked assessments. Sources are context only."
            )
        if assessment.get("last_attempt_status") == "unknown":
            warnings.append(
                "The latest AI attempt was unavailable or invalid. The previous risk flag was retained."
            )
        for field in assessment.get("unresolved_fields") or []:
            warnings.append(str(field))
        if any(not sources.get(item["signal_id"], {}).get("current") for item in cited):
            warnings.append("Some cited evidence is stale or unavailable. Reassess before acting.")
        interpretations.append(
            {
                "shipment_id": shipment["shipment_id"],
                "risk_zone": shipment.get("risk_zone", "safe"),
                "status": assessment.get("status", "unverified"),
                "event_status": assessment.get("event_status", "unknown"),
                "reason": assessment.get("reason")
                or shipment.get("risk_reason")
                or "No evidence-linked interpretation has been recorded for this shipment.",
                "source": assessment.get("source", "Stored shipment flag"),
                "assessed_at": assessment.get("assessed_at"),
                "matched_places": [
                    source["place"]
                    for source in sources.values()
                    if source["signal_id"] in cited_ids and source["location_id"] in route_ids
                ],
                "policy_override": assessment.get("policy_override"),
            }
        )
    impact = plan.get("exposure") or {}
    if not interpretations or any(
        item["status"] in ("unverified", "unknown") for item in interpretations
    ):
        warnings.append(
            "Risk coverage is incomplete. A covered order does not establish that every route is safe."
        )
    if not evidence:
        warnings.append("No source evidence is stored for this case.")
    return {
        "as_of": now.isoformat(),
        "sku": sku,
        "location_id": location_id,
        "interpretations": interpretations,
        "evidence": sorted(
            evidence.values(), key=lambda item: (not item["current"], item["signal_id"])
        ),
        "impact": impact,
        "proposal": {
            "status": plan.get("status"),
            "internal_qty": plan.get("internal_used_qty", 0),
            "supplier_qty": plan.get("supplier_qty", 0),
            "recovered_qty": plan.get("recovered_qty", 0),
            "selected_offer_id": plan.get("selected_offer_id"),
            "recovery_cost_minor": (plan.get("margin_check") or {}).get("recovery_cost_minor"),
            "approver": (plan.get("approval") or {}).get("approver_title"),
        },
        "review_notes": list(dict.fromkeys(warnings)),
        "assumptions": [
            "Disrupted arrivals are stored scenario assumptions, not ETAs predicted by Gemini.",
            "Internal availability is on-hand minus reserved stock. Transfer cost/time and donor demand need review.",
            "Amounts describe a proposed recovery. Revenue exposure is not realized profit or delivered stock.",
        ],
    }
