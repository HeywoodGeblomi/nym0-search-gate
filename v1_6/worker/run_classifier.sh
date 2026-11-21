#!/bin/sh
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
PY="${NYM0CLGATE_PY:-python3}"
mkdir -p "$ROOT/run"
export PYTHONDONTWRITEBYTECODE=1
exec "$PY" "$HERE/classifier_worker.py" "$@" >> "$ROOT/run/classifier.log" 2>&1
