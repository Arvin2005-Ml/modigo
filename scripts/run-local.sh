#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"
mode="${1:-production}"
if [[ "$mode" != "production" && "$mode" != "dev" ]]; then
  printf 'Usage: %s [production|dev]\n' "$0" >&2
  exit 2
fi
if [[ ! -x .venv/bin/python || ! -f apps/web/node_modules/next/dist/bin/next ]]; then
  printf 'Install the locked Python and Node dependencies first; see README.md.\n' >&2
  exit 1
fi

export DATA_BACKEND=mongo API_WORKERS=1 JOB_RUNNER_MODE=in_process
export APP_ORIGIN="${APP_ORIGIN:-http://127.0.0.1:3000}"
export LLM_PROVIDER="${LLM_PROVIDER:-demo}"
export PYTHONPATH="$project_root/apps/api${PYTHONPATH:+:$PYTHONPATH}"

if [[ "$mode" == "production" ]]; then
  npm --prefix apps/web run build
fi

api_pid=''
web_pid=''
cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$web_pid" ]]; then kill "$web_pid" 2>/dev/null || true; fi
  if [[ -n "$api_pid" ]]; then kill "$api_pid" 2>/dev/null || true; fi
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

.venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log &
api_pid=$!
(
  cd apps/web
  if [[ "$mode" == "production" ]]; then
    exec node node_modules/next/dist/bin/next start --hostname 127.0.0.1
  else
    exec node node_modules/next/dist/bin/next dev --hostname 127.0.0.1
  fi
) &
web_pid=$!
printf 'Starting Funilo at http://127.0.0.1:3000 (%s). Ctrl+C stops both processes.\n' "$mode"
printf 'MongoDB persistence uses the public endpoint configured in the server .env.\n'
wait -n "$api_pid" "$web_pid"
