import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import get_connection, init_db, save_report_with_steps
from backend.main import create_app


def _valid_payload(**overrides):
    payload = {
        "name": "Elena Vance",
        "station": "PROP-02",
        "wind_knots": 14.5,
        "temp_c": 18.0,
        "fuel_pct": 99.2,
        "note": "Primary LOX bleed valve cycled 120ms slower than nominal.",
    }
    payload.update(overrides)
    return payload


def _valid_report_record(**overrides):
    record = {
        "name": "Elena Vance",
        "station": "PROP-02",
        "wind_knots": 14.5,
        "temp_c": 18.0,
        "fuel_pct": 99.2,
        "note": "Primary LOX bleed valve cycled 120ms slower than nominal.",
        "verdict": "go",
        "violations": [],
        "subsystem": "propulsion",
        "severity": "medium",
        "brief_by_minutes": 15,
        "hidden_instructions_flagged": False,
        "missing_details_flagged": False,
        "panic_tone_flagged": False,
        "review_required": False,
        "briefing_text": "Pending pipeline output.",
        "draft_rounds": 1,
        "approval_status": "pending",
        "total_tokens": 0,
        "total_cost_usd": 0.0,
    }
    record.update(overrides)
    return record


def test_schema_enforces_check_constraints(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    with get_connection(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO reports (
                    name, station, wind_knots, temp_c, fuel_pct, note,
                    verdict, violations_json, subsystem, severity, brief_by_minutes,
                    briefing_text, draft_rounds, approval_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Alex",
                    "GNC-1",
                    10.0,
                    15.0,
                    99.0,
                    "Sensor blip",
                    "maybe",
                    "[]",
                    "avionics",
                    "low",
                    30,
                    "Brief",
                    1,
                    "pending",
                    "2026-11-17T12:00:00Z",
                ),
            )


def test_save_report_with_steps_rolls_back_on_step_failure(tmp_path: Path):
    db_path = tmp_path / "rollback.db"
    init_db(db_path)

    bad_steps = [
        {
            "step_order": 1,
            "step_name": None,  # violates NOT NULL constraint on step_name
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.001,
            "output_summary": "broken",
            "detail": {},
        }
    ]

    with pytest.raises(sqlite3.IntegrityError):
        save_report_with_steps(db_path, _valid_report_record(), bad_steps)

    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    assert count == 0


def test_file_report_succeeds_and_persists_across_restart(tmp_path: Path):
    db_path = tmp_path / "persist.db"

    app_first = create_app(db_path=db_path)
    with TestClient(app_first) as client:
        resp = client.post("/api/reports", json=_valid_payload())
        assert resp.status_code == 201
        created = resp.json()
        assert created["id"] >= 1
        assert created["name"] == "Elena Vance"
        assert created["station"] == "PROP-02"
        assert created["wind_knots"] == 14.5
        assert created["temp_c"] == 18.0
        assert created["fuel_pct"] == 99.2
        assert created["approval_status"] == "pending"
        assert created["created_at"]

    # Simulate a fresh application restart pointing at the same SQLite file
    app_restarted = create_app(db_path=db_path)
    with TestClient(app_restarted) as client:
        list_resp = client.get("/api/reports")
        assert list_resp.status_code == 200
        reports = list_resp.json()
        assert len(reports) == 1
        assert reports[0]["id"] == created["id"]
        assert reports[0]["note"] == _valid_payload()["note"]

        detail_resp = client.get(f"/api/reports/{created['id']}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["station"] == "PROP-02"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "   "),
        ("station", ""),
        ("note", "  \n "),
        ("wind_knots", -1.0),
        ("fuel_pct", 101.5),
        ("fuel_pct", -0.1),
    ],
)
def test_invalid_report_input_returns_clear_validation_error(tmp_path: Path, field: str, value):
    db_path = tmp_path / "validation.db"
    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        resp = client.post("/api/reports", json=_valid_payload(**{field: value}))
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body
        assert body["detail"]
        assert field in str(body["detail"])


def test_get_missing_report_returns_404(tmp_path: Path):
    db_path = tmp_path / "missing.db"
    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        resp = client.get("/api/reports/9999")
        assert resp.status_code == 404
