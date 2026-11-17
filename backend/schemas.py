from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ReportCreate(BaseModel):
    name: str
    station: str
    wind_knots: float
    temp_c: float
    fuel_pct: float
    note: str

    @field_validator("name", "station", "note")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("wind_knots", "temp_c", "fuel_pct")
    @classmethod
    def must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value

    @field_validator("wind_knots")
    @classmethod
    def wind_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("wind_knots cannot be negative")
        return value

    @field_validator("fuel_pct")
    @classmethod
    def fuel_percentage_bounds(cls, value: float) -> float:
        if value < 0 or value > 100:
            raise ValueError("fuel_pct must be between 0 and 100")
        return value


class PipelineStepOut(BaseModel):
    id: int
    report_id: int
    step_order: int
    step_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    output_summary: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ReportOut(BaseModel):
    id: int
    name: str
    station: str
    wind_knots: float
    temp_c: float
    fuel_pct: float
    note: str
    verdict: Literal["go", "no_go"]
    violations: list[str]
    subsystem: str
    severity: Literal["high", "medium", "low"]
    brief_by_minutes: Literal[5, 15, 30]
    hidden_instructions_flagged: bool
    missing_details_flagged: bool
    panic_tone_flagged: bool
    review_required: bool
    briefing_text: str
    draft_rounds: int
    approval_status: Literal["pending", "approved"]
    approved_by: str | None = None
    approved_at: str | None = None
    total_tokens: int
    total_cost_usd: float
    created_at: str
    steps: list[PipelineStepOut] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    approved_by: str
    actor_type: Literal["human"] = "human"

    @field_validator("approved_by")
    @classmethod
    def approver_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("approved_by must not be blank")
        return stripped
