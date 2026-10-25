#!/bin/bash
# Runs ONE slot (morning|evening) at most once per local day. Used by both the
# launchd agents (primary; runs a missed job the moment the Mac wakes) and the
# optional hourly cron guard. An atomic mkdir lock guarantees the two can never
# double-run the same slot.
set -euo pipefail

PROJECT_DIR="/Users/yashabutt/mabcos-pipeline"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_FILE="$PROJECT_DIR/cron.log"
slot="${1:-morning}"

mkdir -p "$PROJECT_DIR/output"
today=$(date +%F)
now=$(date +"%Y-%m-%d %H:%M:%S %Z")
marker="$PROJECT_DIR/output/.last_run_$slot"
lock="$PROJECT_DIR/output/.lock_$slot"

# Clear a stale lock left by a crashed/slept run (older than 30 minutes).
if [ -d "$lock" ] && [ -n "$(find "$lock" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
  rmdir "$lock" 2>/dev/null || true
fi

# Atomic lock: only one runner (cron or launchd) proceeds.
if ! mkdir "$lock" 2>/dev/null; then
  echo "$now $slot already running, skipping" >> "$LOG_FILE"
  exit 0
fi
trap 'rmdir "$lock" 2>/dev/null || true' EXIT

last=""
[ -f "$marker" ] && last=$(tr -d ' \t\r\n' < "$marker")
if [ "$last" = "$today" ]; then
  exit 0
fi

cd "$PROJECT_DIR"
if MABCOS_SLOT="$slot" "$VENV_PYTHON" pipeline.py \
   && MABCOS_SLOT="$slot" "$VENV_PYTHON" notify.py; then
  echo "$today" > "$marker"
  echo "$now ran $slot" >> "$LOG_FILE"
else
  echo "$now failed $slot, will retry on next wake/tick" >> "$LOG_FILE"
  exit 1
fi
