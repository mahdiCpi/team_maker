#!/usr/bin/env bash
# ==============================================================================
# qa_web_dev.sh — Launch API + web dev servers for manual/browser-driven QA.
#
# `make api-dev` / `make web-dev` pick up whatever `uvicorn`/`npm` resolve to
# on PATH, which can be a different project's venv on a shared dev machine.
# This script pins both to the project's own `.venv` and `web/`, and exports
# a matching TEAM_MAKER_API_KEY for both processes so the Next proxy
# (web/middleware.ts) and the API's fail-closed auth (api/deps.py) agree —
# otherwise "My Teams" always shows "Authentication required".
#
# Usage
# -----
#   scripts/qa_web_dev.sh                 # random key, both servers, logs to /tmp
#   TEAM_MAKER_API_KEY=mykey scripts/qa_web_dev.sh   # use your own key
#
# Ctrl+C stops both servers.
# ==============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT/.venv/Scripts/python.exe"
API_LOG="$ROOT/generated_teams/.qa_api.log"
WEB_LOG="$ROOT/generated_teams/.qa_web.log"

log() { printf '[qa] %s\n' "$*"; }

[ -x "$VENV_PYTHON" ] || { log "FAIL: $VENV_PYTHON not found — run 'pip install -e .' first"; exit 1; }
command -v npm >/dev/null || { log "FAIL: npm not installed"; exit 1; }

export TEAM_MAKER_API_KEY="${TEAM_MAKER_API_KEY:-qa-$(date +%s)-$$}"
log "TEAM_MAKER_API_KEY=$TEAM_MAKER_API_KEY (export this yourself to reuse a fixed key)"

mkdir -p "$(dirname "$API_LOG")"

"$VENV_PYTHON" -m uvicorn api.main:app --reload --port 8000 >"$API_LOG" 2>&1 &
API_PID=$!
npm --prefix "$ROOT/web" run dev >"$WEB_LOG" 2>&1 &
WEB_PID=$!

cleanup() {
    log "stopping servers..."
    kill "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "API   → http://localhost:8000  (log: $API_LOG, pid $API_PID)"
log "web   → http://localhost:3000  (log: $WEB_LOG, pid $WEB_PID)"
log "waiting for both to come up..."

for _ in $(seq 1 30); do
    api_up=false; web_up=false
    curl -sf http://localhost:8000/api/keys/status >/dev/null 2>&1 && api_up=true
    curl -sf http://localhost:3000 >/dev/null 2>&1 && web_up=true
    $api_up && $web_up && { log "both servers ready."; break; }
    sleep 1
done

log "press Ctrl+C to stop."
wait "$API_PID" "$WEB_PID"
