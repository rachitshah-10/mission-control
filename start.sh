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

if [ ! -f "frontend/dist/index.html" ]; then
  (cd frontend && npm run build)
fi

echo "Starting Mission Control at http://127.0.0.1:8000"
exec .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
