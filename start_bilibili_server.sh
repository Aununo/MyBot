#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs
: > logs/bilibili_server.log
source .venv/bin/activate
exec python bilibili_server.py 2>&1 | tee logs/bilibili_server.log
