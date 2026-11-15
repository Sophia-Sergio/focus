#!/bin/bash
# Daily runner: logs to scripts/download/logs/, prevents overlapping runs.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
LOCK=logs/.lock
mkdir "$LOCK" 2>/dev/null || { echo "already running" >> logs/sync.log; exit 0; }
trap 'rmdir "$LOCK"' EXIT
/usr/bin/env python3 sync_itservicios.py "$@" >> logs/sync.log 2>&1
