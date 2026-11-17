from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.rules import (
    INPUT_COST_PER_1M_USD,
    OUTPUT_COST_PER_1M_USD,
    calculate_step_cost_usd,
    calculate_total_cost_usd,
    compute_brief_by_minutes,
    evaluate_launch_limits,
)


@pytest.mark.parametrize(
    ("wind_knots", "temp_c", "fuel_pct"),
    [
        (25.0, 4.0, 98.0),
        (25.0, 4.0, 100.0),
        (0.0, 20.0, 99.0),
    ],
)
def test_launch_limits_go_on_exact_boundaries_and_nominal(
    wind_knots: float, temp_c: float, fuel_pct: float
):
    result = evaluate_launch_limits(wind_knots=wind_knots, temp_c=temp_c, fuel_pct=fuel_pct)
    assert result.verdict == "go"
    assert result.violations == []


@pytest.mark.parametrize(
    ("wind_knots", "temp_c", "fuel_pct", "expected_token"),
    [
        (25.01, 4.0, 98.0, "wind_knots"),
        (25.0, 3.99, 98.0, "temp_c"),
        (25.0, 4.0, 97.99, "fuel_pct"),
        (25.0, 4.0, 100.01, "fuel_pct"),
    ],
)
def test_launch_limits_no_go_just_past_each_boundary(
    wind_knots: float, temp_c: float, fuel_pct: float, expected_token: str
):
    result = evaluate_launch_limits(wind_knots=wind_knots, temp_c=temp_c, fuel_pct=fuel_pct)
    assert result.verdict == "no_go"
    assert len(result.violations) == 1
    assert expected_token in result.violations[0]


def test_launch_limits_reports_multiple_violations():
    result = evaluate_launch_limits(wind_knots=30.0, temp_c=2.0, fuel_pct=96.5)
    assert result.verdict == "no_go"
    assert len(result.violations) == 3
    joined = " ".join(result.violations)
    assert "wind_knots" in joined
    assert "temp_c" in joined
    assert "fuel_pct" in joined


@pytest.mark.parametrize(
    ("severity", "has_violations", "expected_severity", "expected_minutes"),
    [
        ("high", False, "high", 5),
        ("medium", False, "medium", 15),
        ("low", False, "low", 30),
        ("low", True, "high", 5),
        ("medium", True, "high", 5),
        ("high", True, "high", 5),
        ("invalid", False, "medium", 15),
        ("invalid", True, "high", 5),
    ],
)
def test_brief_by_minutes_mapping_and_violation_override(
    severity: str,
    has_violations: bool,
    expected_severity: str,
    expected_minutes: int,
):
    eff_severity, minutes = compute_brief_by_minutes(severity, has_violations=has_violations)
    assert eff_severity == expected_severity
    assert minutes == expected_minutes


def test_cost_calculation_in_code():
    step_cost = calculate_step_cost_usd(
        input_tokens=1000,
        output_tokens=500,
        input_rate_per_1m=2.0,
        output_rate_per_1m=8.0,
    )
    assert step_cost == pytest.approx(0.006, abs=1e-9)

    default_cost = calculate_step_cost_usd(input_tokens=1_000_000, output_tokens=1_000_000)
    assert default_cost == pytest.approx(
        INPUT_COST_PER_1M_USD + OUTPUT_COST_PER_1M_USD, abs=1e-9
    )

    assert calculate_step_cost_usd(0, 0) == 0.0

    with pytest.raises(ValueError):
        calculate_step_cost_usd(-1, 10)


def test_total_cost_sums_steps():
    steps = [
        {"cost_usd": 0.0012},
        {"cost_usd": 0.0028},
        {"cost_usd": 0.0005},
    ]
    assert calculate_total_cost_usd(steps) == pytest.approx(0.0045, abs=1e-9)


def test_filing_endpoint_applies_launch_limits_and_brief_by_time(tmp_path: Path):
    app = create_app(db_path=tmp_path / "limits.db")
    with TestClient(app) as client:
        boundary_go = client.post(
            "/api/reports",
            json={
                "name": "Samira Patel",
                "station": "PAD-A",
                "wind_knots": 25.0,
                "temp_c": 4.0,
                "fuel_pct": 98.0,
                "note": "Minor telemetry jitter on channel B.",
            },
        )
        assert boundary_go.status_code == 201
        go_data = boundary_go.json()
        assert go_data["verdict"] == "go"
        assert go_data["violations"] == []

        violating = client.post(
            "/api/reports",
            json={
                "name": "Samira Patel",
                "station": "PAD-A",
                "wind_knots": 25.1,
                "temp_c": 3.5,
                "fuel_pct": 97.5,
                "note": "Crosswind gust and low LOX level.",
            },
        )
        assert violating.status_code == 201
        no_go_data = violating.json()
        assert no_go_data["verdict"] == "no_go"
        assert len(no_go_data["violations"]) == 3
        assert no_go_data["severity"] == "high"
        assert no_go_data["brief_by_minutes"] == 5
        assert any(step["step_name"] == "launch_limits" for step in no_go_data["steps"])
