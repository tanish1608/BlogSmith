#!/usr/bin/env bash
# Run BlogSmith locally: FastAPI backend (:8000) + Vite dashboard (:5173).
# Both hit your real Firebase project (Firestore + Auth) — no emulator needed.
#
#   ./dev.sh
#   → backend:   http://localhost:8000   (API + Swagger at /docs)
#   → dashboard: http://localhost:5173   (proxies API calls to :8000)
#
# Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "No .venv found. Create it first:  python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend deps…"
  (cd frontend && npm install)
fi

echo "Starting backend on :8000 …"
uvicorn blogsmith.api.main:app --reload --port 8000 &
BACK=$!

echo "Starting dashboard on :5173 …"
(cd frontend && npm run dev) &
FRONT=$!

cleanup() {
  echo
  echo "Stopping…"
  kill "$BACK" "$FRONT" 2>/dev/null || true
}
trap cleanup INT TERM

# Wait for both; Ctrl-C triggers cleanup. (Portable to macOS bash 3.2.)
wait
