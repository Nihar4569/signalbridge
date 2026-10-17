"""Disposable demonstration snapshots. Never read or reset the operational store."""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from ...ai import gemini
from ...core import config
from ...core.store import SnapshotStore
from ...domain import decision, exposure, planner, triage

router = APIRouter(prefix="/decision-demo", tags=["decision walkthrough"])


class RunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["reference", "gemini"] = "reference"


@lru_cache(maxsize=1)
def _fixture() -> dict:
    return json.loads((config.ROOT / "fixtures/decision_demo/cases.json").read_text())


@router.get("/cases")
def cases() -> dict:
    data = _fixture()
    return {
        "assessment_at": data["assessment_at"],
        "synthetic": True,
        "gemini_configured": bool(config.GEMINI_API_KEYS),
        "cases": [
            {key: case[key] for key in ("case_id", "title", "description")}
            for case in data["cases"]
        ],
    }


@router.post("/cases/{case_id}/run")
def run_case(case_id: str, body: RunBody) -> dict:
    data = _fixture()
    case = next((item for item in data["cases"] if item["case_id"] == case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail="Unknown walkthrough case.")
    store = SnapshotStore({**data["collections"], "signals": [case["signal"]]})
    clock = exposure.parse_ts(data["assessment_at"])
    started = time.monotonic()
    if body.mode == "gemini":
        rows = gemini.judge_shipment_risk(
            shipments=store.list("shipments"),
            signals=store.list("signals"),
            locations=store.list("locations"),
            products=store.list("products"),
            lanes=store.list("lanes"),
            as_of=clock,
        )
    else:
        lanes = {lane["lane_id"]: lane for lane in store.list("lanes")}
        rows = gemini._parse_judgments(
            json.dumps(case["reference"]),
            {shipment["shipment_id"] for shipment in store.list("shipments")},
            evidence=decision.evidence_records(
                store.list("signals"), store.list("locations"), as_of=clock
            ),
            shipment_locations={
                shipment["shipment_id"]: decision.route_location_ids(shipment, lanes)
                for shipment in store.list("shipments")
            },
        )
        if rows is None:
            raise HTTPException(status_code=500, detail="The reference fixture failed validation.")
        for row in rows:
            row.update(
                source="Reference interpretation (no model call)", assessed_at=data["assessment_at"]
            )
    if rows is None:
        triage.mark_assessment_unavailable(store, as_of=clock)
        state = "unavailable"
    else:
        triage.run_triage(store, judgments=rows, as_of=clock)
        state = "review" if any(row["status"] == "unknown" for row in rows) else "complete"
    plan = planner.build_plan(store, sku=data["sku"], location_id=data["location_id"], as_of=clock)
    brief = decision.build_decision_brief(store, plan, as_of=clock)
    return {
        "case_id": case_id,
        "mode": body.mode,
        "assessment_state": state,
        "synthetic": True,
        "executed_at": decision.utc_now().isoformat(),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "scenario_clock": data["assessment_at"],
        "brief": brief,
        "plan": plan,
        "shipments": [
            {
                "shipment_id": shipment["shipment_id"],
                "risk_zone": shipment.get("risk_zone"),
                "assessment": shipment.get("risk_assessment"),
            }
            for shipment in store.list("shipments")
        ],
    }
