#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8010}"

echo "Starting backend_user server at http://${HOST}:${PORT}"
uv run --frozen uvicorn app.main:app --host "${HOST}" --port "${PORT}"
