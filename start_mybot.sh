#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs
: > logs/mybot.log
source .venv/bin/activate
export OPENCLAW_AGENT_ID="${OPENCLAW_AGENT_ID:-main}"
exec python bot.py 2>&1 | tee logs/mybot.log
