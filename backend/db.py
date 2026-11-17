from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("mission_control.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    station TEXT NOT NULL,
    wind_knots REAL NOT NULL,
    temp_c REAL NOT NULL,
    fuel_pct REAL NOT NULL,
    note TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('go', 'no_go')),
    violations_json TEXT NOT NULL,
    subsystem TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
    brief_by_minutes INTEGER NOT NULL CHECK (brief_by_minutes IN (5, 15, 30)),
    hidden_instructions_flagged INTEGER NOT NULL DEFAULT 0
        CHECK (hidden_instructions_flagged IN (0, 1)),
    missing_details_flagged INTEGER NOT NULL DEFAULT 0 CHECK (missing_details_flagged IN (0, 1)),
    panic_tone_flagged INTEGER NOT NULL DEFAULT 0 CHECK (panic_tone_flagged IN (0, 1)),
    review_required INTEGER NOT NULL DEFAULT 0 CHECK (review_required IN (0, 1)),
    briefing_text TEXT NOT NULL,
    draft_rounds INTEGER NOT NULL CHECK (draft_rounds >= 1),
    approval_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved')),
    approved_by TEXT,
    approved_at TEXT,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    output_summary TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    return Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))


@contextmanager
def get_connection(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    path = resolve_db_path(db_path)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_step(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "report_id": row["report_id"],
        "step_order": row["step_order"],
        "step_name": row["step_name"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "total_tokens": row["input_tokens"] + row["output_tokens"],
        "cost_usd": row["cost_usd"],
        "output_summary": row["output_summary"],
        "detail": json.loads(row["detail_json"]),
        "created_at": row["created_at"],
    }


def _row_to_report(row: sqlite3.Row, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "station": row["station"],
        "wind_knots": row["wind_knots"],
        "temp_c": row["temp_c"],
        "fuel_pct": row["fuel_pct"],
        "note": row["note"],
        "verdict": row["verdict"],
        "violations": json.loads(row["violations_json"]),
        "subsystem": row["subsystem"],
        "severity": row["severity"],
        "brief_by_minutes": row["brief_by_minutes"],
        "hidden_instructions_flagged": bool(row["hidden_instructions_flagged"]),
        "missing_details_flagged": bool(row["missing_details_flagged"]),
        "panic_tone_flagged": bool(row["panic_tone_flagged"]),
        "review_required": bool(row["review_required"]),
        "briefing_text": row["briefing_text"],
        "draft_rounds": row["draft_rounds"],
        "approval_status": row["approval_status"],
        "approved_by": row["approved_by"],
        "approved_at": row["approved_at"],
        "total_tokens": row["total_tokens"],
        "total_cost_usd": row["total_cost_usd"],
        "created_at": row["created_at"],
        "steps": steps,
    }


def save_report_with_steps(
    db_path: str | Path | None,
    report_data: dict[str, Any],
    steps: list[dict[str, Any]],
) -> int:
    created_at = report_data.get("created_at") or _utc_now_iso()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO reports (
                name, station, wind_knots, temp_c, fuel_pct, note,
                verdict, violations_json, subsystem, severity, brief_by_minutes,
                hidden_instructions_flagged, missing_details_flagged,
                panic_tone_flagged, review_required,
                briefing_text, draft_rounds, approval_status,
                approved_by, approved_at, total_tokens, total_cost_usd, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_data["name"],
                report_data["station"],
                report_data["wind_knots"],
                report_data["temp_c"],
                report_data["fuel_pct"],
                report_data["note"],
                report_data["verdict"],
                json.dumps(report_data.get("violations", [])),
                report_data["subsystem"],
                report_data["severity"],
                report_data["brief_by_minutes"],
                int(bool(report_data.get("hidden_instructions_flagged", False))),
                int(bool(report_data.get("missing_details_flagged", False))),
                int(bool(report_data.get("panic_tone_flagged", False))),
                int(bool(report_data.get("review_required", False))),
                report_data["briefing_text"],
                report_data.get("draft_rounds", 1),
                report_data.get("approval_status", "pending"),
                report_data.get("approved_by"),
                report_data.get("approved_at"),
                report_data.get("total_tokens", 0),
                report_data.get("total_cost_usd", 0.0),
                created_at,
            ),
        )
        report_id = int(cursor.lastrowid)

        for idx, step in enumerate(steps, start=1):
            conn.execute(
                """
                INSERT INTO pipeline_steps (
                    report_id, step_order, step_name,
                    input_tokens, output_tokens, cost_usd,
                    output_summary, detail_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    step.get("step_order", idx),
                    step["step_name"],
                    step.get("input_tokens", 0),
                    step.get("output_tokens", 0),
                    step.get("cost_usd", 0.0),
                    step.get("output_summary", ""),
                    json.dumps(step.get("detail", {})),
                    step.get("created_at") or _utc_now_iso(),
                ),
            )
    return report_id


def get_report(db_path: str | Path | None, report_id: int) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if row is None:
            return None
        step_rows = conn.execute(
            "SELECT * FROM pipeline_steps WHERE report_id = ? ORDER BY step_order ASC, id ASC",
            (report_id,),
        ).fetchall()
    return _row_to_report(row, [_row_to_step(s) for s in step_rows])


def list_reports(db_path: str | Path | None) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        report_rows = conn.execute(
            "SELECT * FROM reports ORDER BY id DESC"
        ).fetchall()
        step_rows = conn.execute(
            "SELECT * FROM pipeline_steps ORDER BY report_id DESC, step_order ASC, id ASC"
        ).fetchall()

    steps_by_report: dict[int, list[dict[str, Any]]] = {}
    for step_row in step_rows:
        step = _row_to_step(step_row)
        steps_by_report.setdefault(step["report_id"], []).append(step)

    return [_row_to_report(r, steps_by_report.get(r["id"], [])) for r in report_rows]


def approve_report(
    db_path: str | Path | None,
    report_id: int,
    approved_by: str,
) -> tuple[str, dict[str, Any] | None]:
    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT approval_status FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if existing is None:
            return "not_found", None
        if existing["approval_status"] == "approved":
            return "already_approved", None

        conn.execute(
            """
            UPDATE reports
            SET approval_status = 'approved', approved_by = ?, approved_at = ?
            WHERE id = ? AND approval_status = 'pending'
            """,
            (approved_by, _utc_now_iso(), report_id),
        )
    return "ok", get_report(db_path, report_id)
