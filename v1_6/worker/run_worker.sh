#!/bin/sh
# Starts the warm policy worker. Extra args are passed through (--socket, --pidfile, --die-after, --hang-after).
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
PY="${NYM0GATE_PY:-python3}"
mkdir -p "$ROOT/run"
export PYTHONDONTWRITEBYTECODE=1
exec "$PY" "$HERE/fallback_worker.py" "$@" >> "$ROOT/run/worker.log" 2>&1
