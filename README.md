# Mission Control: Go/No-Go Launch Console

Full-stack launch anomaly triage console for Meridian Launch Services (90 minutes before launch). Console engineers submit telemetry and free-text anomaly reports, a deterministic + AI pipeline classifies and prepares briefings, and the Flight Director reviews traces, costs, and approves pending briefings.

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- An OpenAI API key configured in `.env` (optional for offline testing or fake-model demo mode)

Create `.env` from `.env.example` before running against the live model:

```bash
cp .env.example .env
```

Set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL=gpt-6-astra`). To run the full UI offline without an API key, set `USE_FAKE_MODEL=1`.

## Start the App

```bash
./start.sh
```

This builds the React frontend (if needed) and starts the FastAPI server at `http://127.0.0.1:8000`, serving both the UI and the `/api` endpoints.

## Run the Tests

```bash
./test.sh
```

This runs the entire offline backend test suite (`pytest` with `USE_FAKE_MODEL=1` and no API key), `ruff check .`, the frontend `vitest` component tests, and TypeScript `tsc --noEmit`.

## Architecture & Core Rules

- **Report Intake & Persistence (`backend/db.py`, `backend/schemas.py`, `backend/main.py`):**
  Validates `name`, `station`, `wind_knots`, `temp_c`, `fuel_pct`, and `note`, rejecting invalid input with clear `422` errors. Reports and pipeline trace steps are stored together in SQLite inside a single atomic transaction so data persists across restarts.
- **Launch Limits & Brief-By Time (`backend/rules.py`):**
  Evaluated strictly in Python code without a model:
  - `wind_knots <= 25`
  - `temp_c >= 4`
  - `98 <= fuel_pct <= 100`
  Any violation sets `verdict = "no_go"` and forces `severity = "high"` (`5` min brief-by). Otherwise `high` = `5` min, `medium` = `15` min, `low` = `30` min.
- **Model Interface & Pipeline (`backend/model_client.py`, `backend/pipeline.py`):**
  All model calls go through the `ModelClient` protocol (`OpenAIModelClient` for `gpt-6-astra`, `FakeModelClient` for offline tests):
  1. **Structured Sorting:** Classifies subsystem and severity with schema enforcement and safe code fallbacks on invalid responses.
  2. **Three Concurrent Checks (`asyncio.gather`):** Checks `hidden_instructions`, `missing_details`, and `panic_tone` in parallel. Notes containing hidden instructions are flagged (`review_required = true`) and never alter the launch verdict.
  3. **Draft & Review Loop:** Drafts a Flight Director briefing and evaluates it for up to 3 rounds, passing evaluator feedback into each subsequent draft.
  4. **Human-Only Approval:** Briefings start `pending` and can only be approved via `POST /api/reports/{id}/approve` with `actor_type = "human"`.
- **Trace & Cost (`backend/rules.py`, `frontend/src/App.tsx`):**
  Each pipeline step records `input_tokens`, `output_tokens`, `total_tokens`, and `cost_usd` calculated in code, rendered as one trace card per step in the Flight Director console.

## Additional Documentation

- [PLAN.md](PLAN.md) — design plan, SQLite schema, branch breakdown, and risk mitigations.
- [TOOL_CHOICES.md](TOOL_CHOICES.md) — rationale, rejected alternatives, and customer concerns for FastAPI, React/Vite, SQLite, and OpenAI `gpt-6-astra`.
