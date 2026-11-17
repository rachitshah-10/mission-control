from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.db import (
    approve_report,
    get_report,
    init_db,
    list_reports,
    resolve_db_path,
    save_report_with_steps,
)
from backend.model_client import ModelClient, get_model_client
from backend.pipeline import run_report_pipeline
from backend.schemas import ApprovalRequest, ReportCreate, ReportOut

load_dotenv()

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app(
    db_path: str | Path | None = None,
    model_client: ModelClient | None = None,
    static_dir: str | Path | None = None,
) -> FastAPI:
    resolved_db = resolve_db_path(db_path)
    active_model = model_client or get_model_client()
    resolved_static = Path(static_dir) if static_dir is not None else DEFAULT_STATIC_DIR

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
    async def file_report(payload: ReportCreate) -> dict:
        record, steps = await run_report_pipeline(payload, active_model)
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

    @app.post("/api/reports/{report_id}/approve", response_model=ReportOut)
    def approve_pending_report(report_id: int, body: ApprovalRequest) -> dict:
        outcome, updated = approve_report(resolved_db, report_id, body.approved_by)
        if outcome == "not_found":
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        if outcome == "already_approved":
            raise HTTPException(status_code=409, detail=f"Report {report_id} is already approved")
        if updated is None:
            raise HTTPException(status_code=500, detail="Failed to load approved report")
        return updated

    index_file = resolved_static / "index.html"
    if index_file.is_file():
        assets_dir = resolved_static / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/", include_in_schema=False)
        def serve_index() -> FileResponse:
            return FileResponse(index_file)

    return app


app = create_app()
