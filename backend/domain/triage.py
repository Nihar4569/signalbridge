"""Apply a risk judgment to shipments and write exposures.

The judgment normally comes from Gemini (backend/ai/gemini.py): it reads the
weather and the news together and decides whether a shipment could really
be delayed. This module does not call Gemini. It writes the decision and
does the shortage math.

If no judgment is passed, a keyword match is used so a missing API key
still produces a safe/risk flag. That fallback is not the main triage.

Every call looks at every in-transit shipment, including ones that are
currently safe. A new signal can flip safe -> risk, and a signal that is
gone on the next pass flips risk -> safe.

Until lanes carry waypoints (docs/productiongrade.md §2.6), a shipment
does not record which port it passes. A disruptive signal at an active
port is therefore treated as touching every in-transit shipment. A signal
at a warehouse only touches shipments headed there.

Exposure rows answer a narrower question than the shipment flag: the
shipment is "risk" when a signal matches, but the exposure stays "safe"
unless that delay actually creates a shortage against an open order.
The shortage uses the shipment's stored assumed_arrival_at only after a
signal matches — a pre-seeded delay_state by itself does not.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..core import config
from . import decision as decision_mod
from . import exposure as exposure_mod
from . import planner as planner_mod

_ACTIVE = ("in_transit", "planned")

# A confirmed, severe disruption on a shipment's route always flags it at risk,
# even if Gemini judged it safe. Mild words (congestion, delayed) are excluded.
_SEVERE_KEYWORDS = (
    "attack", "attacked", "blockade", "blocked", "closed", "closure",
    "suspended", "strike", "missile", "drone", "seized", "shutdown",
)
_SEVERE_WITHIN_DAYS = 3


def exposure_id(sku: str, location_id: str) -> str:
    """One row per SKU + location. Recomputing overwrites it."""
    return f"EXP-{sku}__{location_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_disruptive(signal: dict) -> bool:
    """A stored signal is only a disruption when the reading itself says so.

    Weather: only "high" (storm / heavy rain / strong wind). "low" and
    "medium" stay safe. News: a structured event_type such as
    port_suspension, or a headline that contains a disruption keyword.
    """
    payload = signal.get("payload") or {}
    if signal.get("source") == "open-meteo":
        return payload.get("risk") == "high"
    if payload.get("event_type"):
        return True
    title = (signal.get("title") or "").lower()
    return any(word in title for word in config.DISRUPTION_KEYWORDS)


def match_signal_to_shipment(
    signal: dict,
    shipment: dict,
    location: dict,
    dest_location: dict | None = None,
) -> bool:
    """True when this signal is a disruption at a place this shipment touches.

    A port storm counts only for shipments in that same country. A hurricane
    at Manzanillo must not mark a Mumbai shipment at risk.
    """
    if shipment.get("status") not in _ACTIVE:
        return False
    if not location or not _is_disruptive(signal):
        return False
    if location.get("location_id") == shipment.get("destination_location_id"):
        return True
    if location.get("type") != "port" or not location.get("active", True):
        return False
    if not dest_location:
        return False
    return bool(location.get("country")) and location.get("country") == dest_location.get("country")


def _reason(signal: dict, location: dict) -> str:
    payload = signal.get("payload") or {}
    kind = payload.get("event_type") or payload.get("risk") or signal.get("source")
    return f"{kind}@{location['location_id']}"


def _matching_reasons(
    shipment: dict,
    signals: list[dict],
    locations: dict[str, dict],
    lanes: dict,
) -> list[str]:
    """Deterministic fallback used only when Gemini is silent.

    Flag a shipment only when a disruptive signal sits on a place this
    shipment's own route actually touches — never country-wide, so a Gulf
    disruption never marks an unrelated domestic road move.
    """
    route = _route_location_ids(shipment, lanes)
    reasons: list[str] = []
    for signal in signals:
        loc_id = (signal.get("payload") or {}).get("location_id")
        if not loc_id or loc_id not in route:
            continue
        location = locations.get(loc_id)
        dest = locations.get(shipment.get("destination_location_id"))
        if location and match_signal_to_shipment(signal, shipment, location, dest):
            reasons.append(_reason(signal, location))
    return reasons


def _severe_locations(signals: list[dict], *, as_of=None, excluded_ids=None) -> dict[str, str]:
    """Places with a confirmed severe disruption right now: {location_id: reason}.

    Severe = recent news whose headline names an attack / blockade / closure /
    strike, or a high-risk (gale) weather reading. This is the deterministic
    floor the LLM is not allowed to override.
    """
    now = as_of or decision_mod.utc_now()
    cutoff = (now - timedelta(days=_SEVERE_WITHIN_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    out: dict[str, str] = {}
    for signal in signals:
        if signal.get("signal_id") in (excluded_ids or set()):
            continue
        payload = signal.get("payload") or {}
        loc_id = payload.get("location_id")
        if not loc_id:
            continue
        if signal.get("source") == "open-meteo":
            try:
                age = now - exposure_mod.parse_ts(signal.get("fetched_at") or "")
                fresh = timedelta(minutes=-5) <= age <= timedelta(hours=3)
            except (ValueError, TypeError):
                fresh = False
            if fresh and payload.get("risk") == "high":
                out.setdefault(loc_id, "severe weather (gale) on the route")
        elif (signal.get("published_at") or "") >= cutoff:
            title = (signal.get("title") or "")
            if any(word in title.lower() for word in _SEVERE_KEYWORDS):
                out[loc_id] = title[:200]
    return out


def _route_location_ids(shipment: dict, lanes: dict) -> set[str]:
    """Every place a shipment passes: its lane's waypoints plus its destination."""
    lane = lanes.get(shipment.get("lane_id")) or {}
    ids = {p.get("location_id") for p in lane.get("points", []) if p.get("location_id")}
    ids.add(shipment.get("destination_location_id"))
    return ids


def _zone_for_shipment(
    shipment: dict,
    signals: list[dict],
    locations: dict,
    judgments: list[dict] | None,
    lanes: dict,
    severe: dict[str, str],
    as_of=None,
) -> tuple[str, str | None]:
    """Gemini's judgment wins when the worker passed one — except a confirmed
    severe disruption on the route always flags "risk" (safety net), so the
    decision never silently flips just because the LLM wavered.

    judgments is None only when Gemini did not run. Then the keyword match
    is a fallback so a missing API key does not leave every shipment stale.
    """
    item = None
    if judgments is not None:
        for candidate in judgments:
            if candidate.get("shipment_id") != shipment.get("shipment_id"):
                continue
            item = candidate
            if item.get("risk") is True:
                reason = (item.get("reason") or "gemini").strip()
                return "risk", reason[:240] or "gemini"
            break  # Gemini said safe — fall through to the deterministic net
    else:
        reasons = _matching_reasons(shipment, signals, locations, lanes)
        if reasons:
            return "risk", reasons[0]

    # A cited cancellation only removes that notice from the floor. Other
    # independent severe evidence on the route continues to apply.
    if item and item.get("event_status") == "cancelled":
        resolved_ids = decision_mod.resolved_notice_ids(item, signals)
        severe = _severe_locations(signals, as_of=as_of, excluded_ids=resolved_ids)
    for loc_id in _route_location_ids(shipment, lanes):
        if loc_id in severe:
            place = (locations.get(loc_id) or {}).get("name", loc_id)
            return "risk", f"Confirmed disruption on route — {place}: {severe[loc_id]}"[:240]
    if judgments is not None and (item is None or type(item.get("risk")) is not bool):
        return shipment.get("risk_zone", "safe"), shipment.get("risk_reason")
    return "safe", None


def _apply_shipment_risk(
    store: Any,
    shipments: list[dict],
    signals: list[dict],
    locations: dict,
    lanes: dict,
    severe: dict[str, str],
    judgments: list[dict] | None = None,
    as_of=None,
) -> list[dict]:
    """Write risk_zone on every in-transit shipment. Returns the copies we saved."""
    updated: list[dict] = []
    for shipment in shipments:
        if shipment.get("status") not in _ACTIVE:
            continue
        new_zone, new_reason = _zone_for_shipment(
            shipment, signals, locations, judgments, lanes, severe, as_of=as_of
        )
        assessment = next((item for item in judgments or [] if item.get("shipment_id") == shipment["shipment_id"]), None)
        if assessment and "status" in assessment:
            assessment = {**assessment, "last_attempt_status": assessment["status"]}
            if assessment.get("risk") is False and new_zone == "risk":
                assessment["policy_override"] = new_reason
                assessment["policy_evidence_ids"] = [
                    signal["signal_id"] for signal in signals
                    if (signal.get("payload") or {}).get("location_id")
                    in _route_location_ids(shipment, lanes)
                    and _severe_locations(
                        [signal], as_of=as_of,
                        excluded_ids=decision_mod.resolved_notice_ids(assessment, signals),
                    )
                ]
        # "assumed_delayed" was seeded demo data. Drop it so a stored
        # shipment cannot keep pretending a delay after this pass.
        seeded_delay = shipment.get("delay_state") == "assumed_delayed"
        unchanged = (
            shipment.get("risk_zone") == new_zone
            and shipment.get("risk_reason") == new_reason
            and not seeded_delay
            and (assessment is None or "status" not in assessment or shipment.get("risk_assessment") == assessment)
        )
        if unchanged:
            updated.append(shipment)
            continue
        saved = dict(shipment)
        saved["risk_zone"] = new_zone
        saved["risk_reason"] = new_reason
        if assessment and "status" in assessment:
            saved["risk_assessment"] = assessment
        if seeded_delay:
            saved["delay_state"] = None
        store.upsert("shipments", saved["shipment_id"], saved)
        updated.append(saved)
    return updated


def _on_hand(stock_balances: list[dict], sku: str, location_id: str) -> int:
    for balance in stock_balances:
        if balance.get("sku") == sku and balance.get("location_id") == location_id:
            return int(balance.get("on_hand_qty") or 0)
    return 0


def _affected_lines(order_lines: list[dict], sku: str, location_id: str, deadline) -> list[str]:
    ids: list[str] = []
    for line in order_lines:
        if line.get("sku") != sku or line.get("location_id") != location_id:
            continue
        if line.get("status") != "open":
            continue
        if exposure_mod.parse_ts(line["due_at"]) <= deadline:
            ids.append(line["line_id"])
    return ids


def mark_assessment_unavailable(store: Any, *, as_of=None) -> None:
    """Retain risk flags and evidence, while exposing a failed latest attempt."""
    attempted_at = (as_of or decision_mod.utc_now()).isoformat()
    for shipment in store.list("shipments"):
        if shipment.get("status") not in _ACTIVE:
            continue
        previous = shipment.get("risk_assessment") or {
            "status": "unknown", "event_status": "uncertain", "evidence": [],
            "reason": "No validated AI interpretation is available. The stored risk flag is unchanged.",
            "source": "Assessment unavailable",
        }
        store.upsert("shipments", shipment["shipment_id"], {
            **shipment,
            "risk_assessment": {**previous, "last_attempt_status": "unknown", "last_attempt_at": attempted_at},
        })


def run_triage(store: Any, judgments: list[dict] | None = None, *, as_of=None) -> list[dict]:
    """Set shipment risk, then write one exposure per pair.

    Pass `judgments` from Gemini (one row per shipment: risk true/false and
    a reason). Omit it only for the keyword fallback. Returns the exposure
    documents written this pass.
    """
    locations = {loc["location_id"]: loc for loc in store.list("locations")}
    lanes = {lane["lane_id"]: lane for lane in store.list("lanes")}
    signals = store.list("signals")
    severe = _severe_locations(signals, as_of=as_of)
    _apply_shipment_risk(
        store, store.list("shipments"), signals, locations, lanes, severe,
        judgments=judgments, as_of=as_of,
    )
    # Re-read so a shipment we just saved is the one exposure math sees.
    shipments = store.list("shipments")

    order_lines = store.list("order_lines")
    stock_balances = store.list("stock_balances")
    products = {p["sku"]: p for p in store.list("products")}
    now = as_of.isoformat() if as_of else _now_iso()

    pairs: dict[tuple[str, str], list[dict]] = {}
    for shipment in shipments:
        if shipment.get("status") not in _ACTIVE:
            continue
        dest = shipment.get("destination_location_id")
        for item in shipment.get("items") or []:
            pairs.setdefault((item["sku"], dest), []).append(shipment)

    written: list[dict] = []
    for (sku, location_id), group in pairs.items():
        deadline = planner_mod._earliest_deadline(order_lines, sku, location_id)
        if deadline is None:
            continue
        at_risk = any(s.get("risk_zone") == "risk" for s in group)
        # Signal match decides the scenario. delay_state alone does not.
        scenario = "disrupted" if at_risk else "baseline"
        picture = exposure_mod.assess_exposure(
            sku=sku,
            location_id=location_id,
            deadline=deadline,
            on_hand_qty=_on_hand(stock_balances, sku, location_id),
            shipments=shipments,
            order_lines=order_lines,
            scenario=scenario,
        )
        shortage = int(picture["shortage_qty"])
        exposure_risk = "risk" if at_risk and shortage > 0 else "safe"
        risky = next((s for s in group if s.get("risk_zone") == "risk"), None)
        chosen = risky or group[0]
        price = int((products.get(sku) or {}).get("unit_price_minor") or 0)
        doc = {
            "exposure_id": exposure_id(sku, location_id),
            "event_id": None,
            "shipment_id": chosen.get("shipment_id"),
            "sku": sku,
            "location_id": location_id,
            "deadline_at": picture["deadline"],
            "supply_by_deadline": picture["supply_by_deadline"],
            "demand_by_deadline": picture["demand_by_deadline"],
            "shortage_qty": shortage,
            "affected_order_line_ids": _affected_lines(order_lines, sku, location_id, deadline),
            "revenue_at_risk_minor": shortage * price,
            "penalty_at_risk_minor": 0,
            "severity": "high" if exposure_risk == "risk" else None,
            "risk_zone": exposure_risk,
            "triage_decision": "actionable" if exposure_risk == "risk" else "ignored",
            "computed_at": now,
        }
        store.upsert("exposures", doc["exposure_id"], doc)
        written.append(doc)
    return written
