import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.model_client import DEFAULT_BASE_URL, OpenAIModelClient, get_model_client


class _FakeResponsesEndpoint:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text='{"subsystem": "propulsion", "severity": "medium"}',
            usage=SimpleNamespace(input_tokens=42, output_tokens=12),
        )


class _FakeAsyncOpenAI:
    def __init__(self) -> None:
        self.responses = _FakeResponsesEndpoint()


class _FailingModelClient:
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any] | None = None,
    ):
        raise RuntimeError("Upstream Foundry error 401")


def test_openai_model_client_uses_responses_api_and_schema():
    fake_sdk = _FakeAsyncOpenAI()
    client = OpenAIModelClient(
        api_key="test-key",
        model="gpt-6-astra",
        base_url=DEFAULT_BASE_URL,
        client=fake_sdk,
    )

    schema = {
        "name": "sort_schema",
        "strict": True,
        "schema": {"type": "object", "properties": {}, "additionalProperties": False},
    }
    resp = asyncio.run(
        client.complete(
            system_prompt="Sort report",
            user_prompt="Valve blip",
            response_schema=schema,
        )
    )

    assert resp.content == '{"subsystem": "propulsion", "severity": "medium"}'
    assert resp.input_tokens == 42
    assert resp.output_tokens == 12
    assert len(fake_sdk.responses.calls) == 1
    sent = fake_sdk.responses.calls[0]
    assert sent["model"] == "gpt-6-astra"
    assert sent["instructions"] == "Sort report"
    assert sent["input"] == "Valve blip"
    assert sent["text"]["format"]["type"] == "json_schema"
    assert sent["text"]["format"]["name"] == "sort_schema"


def test_get_model_client_configures_foundry_base_url(monkeypatch):
    monkeypatch.setenv("USE_FAKE_MODEL", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "test-foundry-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    client = get_model_client()
    assert isinstance(client, OpenAIModelClient)
    assert client.base_url == DEFAULT_BASE_URL


def test_post_report_returns_json_502_when_model_fails(tmp_path: Path):
    app = create_app(db_path=tmp_path / "err.db", model_client=_FailingModelClient())
    with TestClient(app) as client:
        resp = client.post(
            "/api/reports",
            json={
                "name": "Rachit",
                "station": "PROP-02",
                "wind_knots": 23,
                "temp_c": 6,
                "fuel_pct": 99,
                "note": "Valve test",
            },
        )
    assert resp.status_code == 502
    assert resp.headers["content-type"].startswith("application/json")
    assert "Upstream Foundry error 401" in resp.json()["detail"]
