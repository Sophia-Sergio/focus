#!/bin/bash
# Daily runner: logs to scripts/download/logs/, prevents overlapping runs.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
LOCK=logs/.lock
mkdir "$LOCK" 2>/dev/null || { echo "already running" >> logs/sync.log; exit 0; }
trap 'rmdir "$LOCK"' EXIT
/usr/bin/env python3 sync_itservicios.py "$@" >> logs/sync.log 2>&1
SYNC_RC=$?
# Upload everything (idempotent: only new/changed files go) to Google Drive, same folder tree.
/usr/bin/env python3 upload_pdfs_to_drive.py >> logs/sync.log 2>&1
UP_RC=$?
exit $(( SYNC_RC || UP_RC ))
