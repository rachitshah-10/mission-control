from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from backend.db import get_report, init_db, list_reports, resolve_db_path, save_report_with_steps
from backend.rules import (
    calculate_total_cost_usd,
    compute_brief_by_minutes,
    evaluate_launch_limits,
)
from backend.schemas import ReportCreate, ReportOut

load_dotenv()


def create_app(db_path: str | Path | None = None) -> FastAPI:
    resolved_db = resolve_db_path(db_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db(resolved_db)
        yield

    app = FastAPI(title="Mission Control", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
    def file_report(payload: ReportCreate) -> dict:
        limits = evaluate_launch_limits(
            wind_knots=payload.wind_knots,
            temp_c=payload.temp_c,
            fuel_pct=payload.fuel_pct,
        )
        effective_severity, brief_by_minutes = compute_brief_by_minutes(
            "medium",
            has_violations=bool(limits.violations),
        )
        steps = [
            {
                "step_order": 1,
                "step_name": "launch_limits",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "output_summary": (
                    f"verdict={limits.verdict}, violations={len(limits.violations)}"
                ),
                "detail": {
                    "verdict": limits.verdict,
                    "violations": limits.violations,
                    "brief_by_minutes": brief_by_minutes,
                },
            }
        ]
        record = {
            "name": payload.name,
            "station": payload.station,
            "wind_knots": payload.wind_knots,
            "temp_c": payload.temp_c,
            "fuel_pct": payload.fuel_pct,
            "note": payload.note,
            "verdict": limits.verdict,
            "violations": limits.violations,
            "subsystem": "unknown",
            "severity": effective_severity,
            "brief_by_minutes": brief_by_minutes,
            "hidden_instructions_flagged": False,
            "missing_details_flagged": False,
            "panic_tone_flagged": False,
            "review_required": False,
            "briefing_text": payload.note,
            "draft_rounds": 1,
            "approval_status": "pending",
            "total_tokens": 0,
            "total_cost_usd": calculate_total_cost_usd(steps),
        }
        report_id = save_report_with_steps(resolved_db, record, steps)
        saved = get_report(resolved_db, report_id)
        if saved is None:
            raise HTTPException(status_code=500, detail="Failed to load saved report")
        return saved

    @app.get("/api/reports", response_model=list[ReportOut])
    def get_all_reports() -> list[dict]:
        return list_reports(resolved_db)

    @app.get("/api/reports/{report_id}", response_model=ReportOut)
    def get_single_report(report_id: int) -> dict:
        report = get_report(resolved_db, report_id)
        if report is None:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        return report

    return app


app = create_app()
