from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

MAX_WIND_KNOTS = 25.0
MIN_TEMP_C = 4.0
MIN_FUEL_PCT = 98.0
MAX_FUEL_PCT = 100.0

BRIEF_BY_MINUTES: dict[Literal["high", "medium", "low"], Literal[5, 15, 30]] = {
    "high": 5,
    "medium": 15,
    "low": 30,
}

INPUT_COST_PER_1M_USD = 2.50
OUTPUT_COST_PER_1M_USD = 10.00


@dataclass(frozen=True)
class LimitEvaluation:
    verdict: Literal["go", "no_go"]
    violations: list[str]


def evaluate_launch_limits(
    wind_knots: float,
    temp_c: float,
    fuel_pct: float,
) -> LimitEvaluation:
    violations: list[str] = []

    if wind_knots > MAX_WIND_KNOTS:
        violations.append(
            f"wind_knots ({wind_knots}) exceeds maximum limit of {MAX_WIND_KNOTS} knots"
        )
    if temp_c < MIN_TEMP_C:
        violations.append(
            f"temp_c ({temp_c}) is below minimum limit of {MIN_TEMP_C} C"
        )
    if fuel_pct < MIN_FUEL_PCT or fuel_pct > MAX_FUEL_PCT:
        violations.append(
            f"fuel_pct ({fuel_pct}) is outside allowed range {MIN_FUEL_PCT}-{MAX_FUEL_PCT}%"
        )

    verdict: Literal["go", "no_go"] = "no_go" if violations else "go"
    return LimitEvaluation(verdict=verdict, violations=violations)


def compute_brief_by_minutes(
    severity: str,
    has_violations: bool,
) -> tuple[Literal["high", "medium", "low"], Literal[5, 15, 30]]:
    if has_violations:
        return "high", BRIEF_BY_MINUTES["high"]

    normalized = severity.strip().lower() if isinstance(severity, str) else ""
    if normalized in BRIEF_BY_MINUTES:
        valid_severity: Literal["high", "medium", "low"] = normalized  # type: ignore[assignment]
        return valid_severity, BRIEF_BY_MINUTES[valid_severity]

    return "medium", BRIEF_BY_MINUTES["medium"]


def calculate_step_cost_usd(
    input_tokens: int,
    output_tokens: int,
    input_rate_per_1m: float = INPUT_COST_PER_1M_USD,
    output_rate_per_1m: float = OUTPUT_COST_PER_1M_USD,
) -> float:
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts cannot be negative")
    cost = (
        (input_tokens / 1_000_000) * input_rate_per_1m
        + (output_tokens / 1_000_000) * output_rate_per_1m
    )
    return round(cost, 8)


def calculate_total_cost_usd(steps: Sequence[Mapping[str, Any]]) -> float:
    total = sum(float(step.get("cost_usd", 0.0)) for step in steps)
    return round(total, 8)
