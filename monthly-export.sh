#!/bin/bash
# Runs the Polar Flow export for last month, but only once per calendar month.
# Intended to be triggered on every boot via @reboot cron; it is a no-op if the
# export has already succeeded this month.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
MARKER_FILE="$HOME/.polar-monthly-export-last-run"
CURRENT_MONTH=$(date +%Y-%m)
LAST_MONTH=$(date -d "last month" +%Y-%m)
LOG_FILE="$REPO_DIR/cron.log"

# Log to file and stdout so manual runs show output in the terminal too
log() { echo "$(date): $*" | tee -a "$LOG_FILE"; }
log_err() { echo "$(date): ERROR: $*" | tee -a "$LOG_FILE" >&2; }

trap 'log_err "script failed at line $LINENO"' ERR

# Skip if already ran successfully this month
if [[ -f "$MARKER_FILE" ]] && [[ "$(cat "$MARKER_FILE")" == "$CURRENT_MONTH" ]]; then
    log "already ran for $CURRENT_MONTH, skipping."
    exit 0
fi

cd "$REPO_DIR"

# Bring containers up (safe to call if already running)
log "bringing containers up..."
docker compose up -d 2>&1 | tee -a "$LOG_FILE"

# Wait for the Selenium container to pass its health check
log "waiting for Selenium to be healthy (up to 120s)..."
timeout 120 bash -c \
    'until docker inspect --format="{{.State.Health.Status}}" "$(docker compose ps -q selenium 2>/dev/null)" 2>/dev/null | grep -q healthy; do sleep 5; done' \
    2>&1 | tee -a "$LOG_FILE"

# Determine start month from the most recently downloaded TCX file.
# This is more reliable than completed_months.txt: if the last file is from
# 2026-04, we re-check from April onwards to catch any missed exercises.
START_MONTH=$(docker exec export sh -c \
    'ls /data/*.tcx 2>/dev/null | sort | tail -1 | xargs -r basename | cut -c1-7' \
    2>/dev/null || true)

if [[ -z "$START_MONTH" || ! "$START_MONTH" =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
    START_MONTH="$LAST_MONTH"
    log "no existing TCX files found, starting from $START_MONTH"
else
    log "most recent TCX file is from $START_MONTH, starting from there"
fi

# Clear completed_months.txt for START_MONTH and later so those months are
# fully re-scraped and any missing downloads are picked up.
docker exec export sh -c \
    "[ -f /data/completed_months.txt ] && \
     awk -v s='$START_MONTH' '\$0 < s' /data/completed_months.txt > /tmp/_cm && \
     mv /tmp/_cm /data/completed_months.txt || true" \
    2>&1 | tee -a "$LOG_FILE"

# Run the export from START_MONTH through the current month so partial
# current-month downloads are also caught.
log "running export from $START_MONTH to $CURRENT_MONTH..."
docker exec export python3 polar-export.py \
    --start "$START_MONTH" \
    --end "$CURRENT_MONTH" 2>&1 | tee -a "$LOG_FILE"

# Record success so subsequent boots this month are skipped
echo "$CURRENT_MONTH" > "$MARKER_FILE"
log "export completed."
