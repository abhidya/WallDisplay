#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../scripts/common_env.sh"

mkdir -p "$NANODLNA_LOG_DIR"
SUPERVISOR_LOG="$NANODLNA_LOG_DIR/service-supervisor.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$SUPERVISOR_LOG"
}

BACKEND_PID=""
FRONTEND_PID=""

stop_children() {
    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
}

trap 'log "Received stop signal"; stop_children; exit 0' INT TERM

while true; do
    log "Starting dashboard through run_dashboard.sh"
    set +e
    "$NANODLNA_ROOT_DIR/run_dashboard.sh" >> "$NANODLNA_LOG_DIR/launchd-dashboard.out.log" 2>> "$NANODLNA_LOG_DIR/launchd-dashboard.err.log"
    exit_code=$?
    set -e
    log "run_dashboard.sh exited with code $exit_code; restarting after delay"
    "$NANODLNA_ROOT_DIR/stop_dashboard.sh" >> "$NANODLNA_LOG_DIR/launchd-dashboard.out.log" 2>> "$NANODLNA_LOG_DIR/launchd-dashboard.err.log" || true
    sleep "$NANODLNA_SERVICE_RESTART_DELAY"
done
