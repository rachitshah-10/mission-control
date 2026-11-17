from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from openai import AsyncOpenAI


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int
    output_tokens: int


class ModelClient(Protocol):
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any] | None = None,
    ) -> ModelResponse: ...


class OpenAIModelClient:
    def __init__(self, api_key: str, model: str = "gpt-6-astra") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": response_schema,
            }

        completion = await self._client.chat.completions.create(**kwargs)
        content = completion.choices[0].message.content or ""
        usage = completion.usage
        input_tokens = int(usage.prompt_tokens) if usage and usage.prompt_tokens else 0
        output_tokens = int(usage.completion_tokens) if usage and usage.completion_tokens else 0
        return ModelResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class FakeModelClient:
    """Deterministic offline model implementation used in tests and local fake mode."""

    _INJECTION_PATTERNS = (
        "ignore all",
        "ignore previous",
        "ignore your instructions",
        "override verdict",
        "set verdict",
        "system prompt",
        "print the contents of .env",
        "disregard",
    )

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        sys_lower = system_prompt.lower()
        in_tok = max(20, len(user_prompt.split()) * 2)

        if "sort" in sys_lower:
            payload = self._fake_sort(user_prompt)
            text = json.dumps(payload)
            return ModelResponse(content=text, input_tokens=in_tok, output_tokens=18)

        if "hidden_instructions" in sys_lower:
            lower = user_prompt.lower()
            flagged = any(pat in lower for pat in self._INJECTION_PATTERNS)
            reason = (
                "Detected directive attempting to alter system behavior or verdict."
                if flagged
                else "No hidden instructions detected."
            )
            return ModelResponse(
                content=json.dumps({"flagged": flagged, "reason": reason}),
                input_tokens=in_tok,
                output_tokens=20,
            )

        if "missing_details" in sys_lower:
            note_text = self._extract_note(user_prompt)
            flagged = len(note_text.strip()) < 20
            reason = (
                "Note is too brief and lacks diagnostic context."
                if flagged
                else "Sufficient operational context provided."
            )
            return ModelResponse(
                content=json.dumps({"flagged": flagged, "reason": reason}),
                input_tokens=in_tok,
                output_tokens=18,
            )

        if "panic_tone" in sys_lower:
            note_text = self._extract_note(user_prompt)
            flagged = bool(
                re.search(r"!!+", note_text)
                or any(w in note_text.lower() for w in ("panic", "abort now", "emergency!!!"))
            )
            reason = (
                "Urgent or panicked phrasing detected."
                if flagged
                else "Tone is calm and procedural."
            )
            return ModelResponse(
                content=json.dumps({"flagged": flagged, "reason": reason}),
                input_tokens=in_tok,
                output_tokens=18,
            )

        if "draft" in sys_lower:
            briefing = self._fake_draft(user_prompt)
            return ModelResponse(
                content=briefing,
                input_tokens=in_tok,
                output_tokens=max(35, len(briefing.split()) * 2),
            )

        if "review" in sys_lower:
            return ModelResponse(
                content=json.dumps(
                    {"approved": True, "feedback": "Briefing is concise, factual, and complete."}
                ),
                input_tokens=in_tok,
                output_tokens=20,
            )

        return ModelResponse(content="{}", input_tokens=in_tok, output_tokens=5)

    @staticmethod
    def _extract_note(prompt: str) -> str:
        marker = "Note:"
        if marker in prompt:
            return prompt.split(marker, 1)[1].strip()
        return prompt

    @staticmethod
    def _fake_sort(prompt: str) -> dict[str, str]:
        lower = prompt.lower()
        subsystem = "unknown"
        if any(k in lower for k in ("valve", "lox", "fuel", "helium", "prop")):
            subsystem = "propulsion"
        elif any(k in lower for k in ("telemetry", "downlink", "packet", "s-band", "link")):
            subsystem = "telemetry"
        elif any(k in lower for k in ("imu", "avionics", "bus", "voltage", "gimbal")):
            subsystem = "avionics"
        elif any(k in lower for k in ("wind", "temp", "weather")):
            subsystem = "weather"
        elif any(k in lower for k in ("payload", "fairing")):
            subsystem = "payload"
        elif any(k in lower for k in ("pad", "ground")):
            subsystem = "ground_systems"

        severity = "low"
        if any(k in lower for k in ("drop", "dip", "drift", "fluctuat", "slow", "overshoot")):
            severity = "medium"
        if any(k in lower for k in ("abort", "fire", "rupture", "critical", "loss of")):
            severity = "high"
        return {"subsystem": subsystem, "severity": severity}

    @staticmethod
    def _fake_draft(prompt: str) -> str:
        fields: dict[str, str] = {}
        for line in prompt.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                fields[key.strip().lower()] = val.strip()

        station = fields.get("station", "UNKNOWN")
        verdict = fields.get("verdict", "go").upper()
        subsystem = fields.get("subsystem", "unknown")
        brief_by = fields.get("brief_by_minutes", "15")
        note = fields.get("note", "No summary provided.")
        flags = fields.get("safety_flags", "none")

        return (
            f"[{verdict} | {subsystem.upper()} | Brief within {brief_by}m] "
            f"Station {station}: {note} Flags: {flags}. "
            f"Flight Director review required before release."
        )


def get_model_client() -> ModelClient:
    use_fake = os.getenv("USE_FAKE_MODEL", "0").strip() == "1"
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if use_fake or not api_key:
        return FakeModelClient()
    model = os.getenv("OPENAI_MODEL", "gpt-6-astra").strip() or "gpt-6-astra"
    return OpenAIModelClient(api_key=api_key, model=model)
