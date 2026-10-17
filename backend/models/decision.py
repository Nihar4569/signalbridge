"""Strict model output. IDs, evidence quotes and coverage are validated separately."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    signal_id: str = Field(min_length=1, max_length=160)
    quote: str = Field(min_length=1, max_length=1200)


class ShipmentInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    shipment_id: str = Field(min_length=1, max_length=160)
    status: Literal["affected", "unaffected", "unknown"]
    event_status: Literal["active", "planned", "cancelled", "none", "uncertain"]
    reason: str = Field(min_length=1, max_length=800)
    evidence: list[EvidenceReference] = Field(max_length=8)
    unresolved_fields: list[str] = Field(max_length=8)


class InterpretationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    shipments: list[ShipmentInterpretation] = Field(max_length=100)


def gemini_response_schema() -> dict:
    """Send the portable schema subset; enforce lengths and extra fields in Python.

    Some configured models reject Pydantic's string/collection constraints with
    an unhelpful HTTP 400. The backend still applies the full strict models.
    """
    ignored = {"minLength", "maxLength", "maxItems", "title", "additionalProperties"}

    def portable(value):
        if isinstance(value, list):
            return [portable(item) for item in value]
        if isinstance(value, dict):
            return {key: portable(item) for key, item in value.items() if key not in ignored}
        return value

    return portable(InterpretationBatch.model_json_schema())
