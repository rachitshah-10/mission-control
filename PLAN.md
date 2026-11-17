# Mission Control: Implementation Plan

## 1. Problem Statement
Meridian Launch Services is 90 minutes from launch. Console engineers submit free-text anomaly reports along with station telemetry (`wind_knots`, `temp_c`, `fuel_pct`). The Flight Director does not have time to sift through raw notes and needs a reliable console that:
- Deterministically enforces hard launch safety limits in code (never delegated to an LLM).
- Uses an AI pipeline to classify the report, run concurrent safety/quality checks, and iteratively draft + review a concise Flight Director briefing.
- Tracks token usage, code-calculated cost, and a step-by-step trace for every report.
- Guarantees that only a human Flight Director can approve a pending briefing.

## 2. Core Rules & Pipeline Design

### 2.1 Report Inputs & Validation
Every submitted report requires:
- `name`: non-empty string (engineer name)
- `station`: non-empty string (console/station ID)
- `wind_knots`: finite number (`>= 0`)
- `temp_c`: finite number
- `fuel_pct`: finite number (`0` to `100`)
- `note`: non-empty free-text anomaly description

Invalid or missing inputs are rejected with HTTP `422` / `400` and a clear, structured error message.

### 2.2 Deterministic Launch Limits (Plain Code)
Evaluated strictly in Python without any model call:
- `wind_knots <= 25`
- `temp_c >= 4`
- `98 <= fuel_pct <= 100`

Any reading outside its limit records a specific violation string and sets `verdict = "no_go"`. If all readings are within limits, `verdict = "go"`.

### 2.3 Brief-By Time (Plain Code)
- Severity mapping: `high -> 5` minutes, `medium -> 15` minutes, `low -> 30` minutes.
- Rule override: any launch limit violation forces effective severity to `high` (`5` minutes), regardless of what the sorting model suggests.

### 2.4 Model Pipeline (Behind One Swappable Interface)
All LLM calls flow through a single `ModelClient` protocol (`OpenAIClient` in production, `FakeModelClient` in offline tests):
1. **Structured Sorting:** Requests `subsystem` (`propulsion`, `telemetry`, `avionics`, `ground_systems`, `payload`, `weather`, `unknown`) and `severity` (`high`, `medium`, `low`) via a strict schema. Code validates the payload; invalid or unparseable values fall back safely (`subsystem="unknown"`, `severity="medium"` — or `"high"` if a limit violation exists).
2. **Three Concurrent Checks (`asyncio.gather`):**
   - `hidden_instructions`: detects prompt-injection attempts inside `note`.
   - `missing_details`: flags critical missing context needed for decision-making.
   - `panic_tone`: detects panicked/alarmist tone.
   If `hidden_instructions` is flagged, the report is marked `needs_review = True` / flagged in the UI, and the note can **never** modify `verdict` (which remains code-computed).
3. **Draft & Review Loop (Max 3 Rounds):**
   - Round `1..3`: Drafter model call writes a concise Flight Director briefing; Evaluator model call reviews it (`approved: bool`, `feedback: str`).
   - Evaluator feedback is passed into the next draft iteration. The loop terminates early on evaluator approval or after round 3.
4. **Human-Only Approval:**
   - Reports enter `approval_status = "pending"`. Only an explicit human Flight Director action (`POST /api/reports/{id}/approve`) transitions `approval_status` to `"approved"`. No automated pipeline step can approve a briefing.

### 2.5 Cost & Traceability
- Every model step records: `step_name`, `round_number`, `status`, `input_tokens`, `output_tokens`, `total_tokens`, `cost_usd` (computed in Python from token counts and configured per-1M-token rates), and `detail_json`.
- Report `total_cost_usd` equals the sum of step costs calculated in code.

## 3. SQLite Database Schema

Two primary tables managed inside atomic SQLite transactions (`with conn:`):

1. **`reports`**
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
   - `name` (`TEXT NOT NULL`)
   - `station` (`TEXT NOT NULL`)
   - `wind_knots` (`REAL NOT NULL`)
   - `temp_c` (`REAL NOT NULL`)
   - `fuel_pct` (`REAL NOT NULL`)
   - `note` (`TEXT NOT NULL`)
   - `verdict` (`TEXT NOT NULL CHECK (verdict IN ('go', 'no_go'))`)
   - `violations_json` (`TEXT NOT NULL`)
   - `subsystem` (`TEXT NOT NULL`)
   - `severity` (`TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low'))`)
   - `brief_by_minutes` (`INTEGER NOT NULL CHECK (brief_by_minutes IN (5, 15, 30))`)
   - `hidden_instructions_flagged` (`INTEGER NOT NULL DEFAULT 0`)
   - `missing_details_flagged` (`INTEGER NOT NULL DEFAULT 0`)
   - `panic_tone_flagged` (`INTEGER NOT NULL DEFAULT 0`)
   - `review_required` (`INTEGER NOT NULL DEFAULT 0`)
   - `briefing_text` (`TEXT NOT NULL`)
   - `draft_rounds` (`INTEGER NOT NULL`)
   - `approval_status` (`TEXT NOT NULL DEFAULT 'pending' CHECK (approval_status IN ('pending', 'approved'))`)
   - `approved_by` (`TEXT`)
   - `approved_at` (`TEXT`)
   - `total_tokens` (`INTEGER NOT NULL DEFAULT 0`)
   - `total_cost_usd` (`REAL NOT NULL DEFAULT 0.0`)
   - `created_at` (`TEXT NOT NULL`)

2. **`pipeline_steps`**
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
   - `report_id` (`INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE`)
   - `step_order` (`INTEGER NOT NULL`)
   - `step_name` (`TEXT NOT NULL`)
   - `input_tokens` (`INTEGER NOT NULL DEFAULT 0`)
   - `output_tokens` (`INTEGER NOT NULL DEFAULT 0`)
   - `cost_usd` (`REAL NOT NULL DEFAULT 0.0`)
   - `output_summary` (`TEXT NOT NULL`)
   - `detail_json` (`TEXT NOT NULL`)
   - `created_at` (`TEXT NOT NULL`)

## 4. Planned Feature Branches & Test-First Strategy

On every branch below, failing pytest tests will be committed **first**, observed failing, and then satisfied by the implementation:

1. **`feature/schema-and-filing`**
   - DB connection/schema, atomic transaction helpers, report validation, and `POST /api/reports` + `GET /api/reports` persistence.
   - *Planned tests:* valid filing, validation rejections (blank name/station/note, out-of-range fuel/negative wind), persistence across app/DB restart, transaction rollback test.
2. **`feature/deterministic-rules-and-cost`**
   - Plain-code launch limit evaluator, brief-by time calculator, and token-to-USD cost calculator.
   - *Planned tests:* exact boundary tests (`wind_knots` at `25` vs `25.01`, `temp_c` at `4` vs `3.99`, `fuel_pct` at `98`, `100`, `97.99`, `100.01`), multi-violation formatting, brief-by mapping with and without violations, cost math accuracy.
3. **`feature/ai-pipeline-and-safety`**
   - `ModelClient` interface, `OpenAIClient` (`gpt-6-astra`), `FakeModelClient`, structured sorting with fallback, 3 concurrent checks, 3-round draft/review loop, and human-only approval endpoint.
   - *Planned tests:* invalid sorting JSON/enum fallback, concurrent timing/execution of 3 checks, prompt-injection note flagged + routed to review + verdict unchanged, draft/review feedback propagation stopping at max 3 rounds, human-only approval enforcement, offline full-suite pass with no API key.
4. **`feature/frontend-console`**
   - React + Vite + TypeScript UI for filing reports (with field validation messages) and the Flight Director console (verdicts, briefings, human approval button, total cost, and per-step trace cards with token counts).
   - *Planned tests:* frontend build/typecheck verification and end-to-end API/UI integration checks.
5. **`feature/single-command-runner-and-docs`**
   - Single command to start backend + built/served frontend (`./start.sh` or `npm`/`make`/Python runner) and single command to run all tests, plus full `README.md` walkthrough.

## 5. Risks & Mitigations

1. **Prompt Injection in Engineer Notes**
   - *Risk:* A malicious or malformed note instructs the model to force `verdict = "go"` or reveal `.env` secrets.
   - *Mitigation:* Launch limits and `verdict` are computed solely in Python before/independently of any model output; the `hidden_instructions` check flags suspicious notes for human review; `.env` is never passed into prompts.
2. **Malformed or Out-of-Schema Model Outputs**
   - *Risk:* The model returns unexpected subsystem/severity values or invalid JSON under load.
   - *Mitigation:* Use structured schema outputs and strictly validate in Python with deterministic safe fallbacks (`unknown` subsystem, `medium` or violation-forced `high` severity).
3. **API Latency, Rate Limits, or Offline Grading**
   - *Risk:* Grading/CI environments have no OpenAI API key or network access, and sequential checks would add unnecessary latency.
   - *Mitigation:* Run the 3 note checks concurrently with `asyncio.gather`, and route every model call through `ModelClient` so tests run 100% deterministically offline using `FakeModelClient`.
