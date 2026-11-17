from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app


def test_serves_built_frontend_index_and_api_routes(tmp_path: Path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><title>Mission Control</title>"
        "<body><div id='root'></div></body></html>",
        encoding="utf-8",
    )

    app = create_app(db_path=tmp_path / "spa.db", static_dir=dist_dir)
    with TestClient(app) as client:
        root_resp = client.get("/")
        assert root_resp.status_code == 200
        assert "Mission Control" in root_resp.text

        health_resp = client.get("/api/health")
        assert health_resp.status_code == 200
        assert health_resp.json() == {"status": "ok"}
