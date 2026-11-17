# Tool Choices — Mission Control

This document explains the stack selected for **Mission Control: Go/No-Go Launch Console**, including the specific reason for each choice, one rejected alternative, and one Meridian Launch Services customer concern with mitigation.

---

## 1. Back End: Python + FastAPI
- **Specific Reason:** FastAPI provides native `async`/`await` support for running the three note checks concurrently (`asyncio.gather`), Pydantic v2 validation for rejecting malformed engineer reports with clear field-level messages, and clean dependency injection for swapping between the live OpenAI client and the offline fake client during tests.
- **Rejected Alternative:** **Flask** — rejected because it lacks built-in async concurrency and schema validation out of the box, requiring extra extensions to achieve the same validation and concurrent model-call behavior.
- **Customer Concern:** *Blocking or unhandled exceptions during a 90-minute launch countdown could stall report intake.*
  - **Mitigation:** Keep deterministic launch-limit evaluation independent of model latency, enforce strict request validation at the API boundary, and wrap database writes in atomic transactions with explicit error responses.

---

## 2. Front End: React + Vite + TypeScript
- **Specific Reason:** React with TypeScript and Vite lets us build a responsive two-part console (Engineer Report Form + Flight Director Briefing/Trace View) with compile-time type safety for API payloads, clear inline validation feedback, and individual step trace cards showing tokens and costs—while compiling to static assets that FastAPI can serve from a single startup command.
- **Rejected Alternative:** **Server-rendered Jinja2 templates** — rejected because managing dynamic multi-step trace cards, live approval state updates, and client-side form validation feedback is clunkier and harder to maintain cleanly than componentized React + TypeScript.
- **Customer Concern:** *UI drift or misread telemetry during high-stress countdown operations could cause a Flight Director to overlook a `no_go` violation or approve prematurely.*
  - **Mitigation:** Use high-contrast `GO` / `NO-GO` badges, highlight limit violations and `review_required` flags prominently, disable automatic approval, and require an explicit Flight Director confirmation action.

---

## 3. Database: SQLite (`sqlite3`)
- **Specific Reason:** SQLite is built into Python's standard library, requires zero external daemon or container setup, supports `CHECK` constraints and foreign keys for data integrity, and persists reports and step traces to a single local file across application restarts.
- **Rejected Alternative:** **PostgreSQL** — rejected because requiring a separate database server adds operational friction for single-command local startup and offline test runs without offering meaningful advantages for a single-console launch tool.
- **Customer Concern:** *Concurrent engineer submissions could trigger database lock errors or leave partial report/trace state after a crash.*
  - **Mitigation:** Configure SQLite with WAL mode and busy timeouts, enforce `FOREIGN KEY` and `CHECK` constraints, and save each report along with its pipeline trace steps inside a single atomic `with conn:` transaction.

---

## 4. Model: OpenAI (`gpt-6-astra`)
- **Specific Reason:** OpenAI's API supports structured JSON schema responses for reliable subsystem/severity sorting, fast concurrent calls for the three parallel note checks, and clear token-usage metadata (`prompt_tokens`, `completion_tokens`) needed to compute exact per-step and per-report costs in code—all behind a single `ModelClient` interface so offline tests run with `FakeModelClient`.
- **Rejected Alternative:** **Local Ollama model (e.g., Llama 3 8B)** — rejected because smaller local models vary widely in hardware requirements, struggle more often with strict schema adherence and nuanced prompt-injection detection, and cannot be assumed to be pre-installed in every environment.
- **Customer Concern:** *Model hallucinations, prompt-injection attacks in engineer notes, or unpredictable API costs during launch operations.*
  - **Mitigation:** Keep all launch limit checks, `verdict` assignment, brief-by times, and cost calculations strictly in Python code; validate structured outputs with safe fallbacks; run a dedicated `hidden_instructions` check that flags suspicious notes for human review; and cap the draft/review loop at 3 rounds.
