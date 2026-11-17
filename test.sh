#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm ci)
fi

OPENAI_API_KEY="" USE_FAKE_MODEL=1 .venv/bin/pytest -v
.venv/bin/ruff check .
(cd frontend && npm test && npm run typecheck)
