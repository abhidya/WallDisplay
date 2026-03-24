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

ensure_backend_dependencies() {
    cd "$NANODLNA_BACKEND_DIR"

    if [ ! -d "$NANODLNA_VENV_DIR" ]; then
        log "Creating Python virtual environment at $NANODLNA_VENV_DIR"
        python3 -m venv "$NANODLNA_VENV_DIR"
    fi

    if [ -x "$NANODLNA_VENV_DIR/bin/python" ]; then
        NANODLNA_PYTHON_BIN="$NANODLNA_VENV_DIR/bin/python"
    fi

    if [ ! -f .deps_backend.stamp ] || [ requirements.txt -nt .deps_backend.stamp ]; then
        log "Installing backend dependencies"
        "$NANODLNA_PYTHON_BIN" -m pip install -r requirements.txt >> "$NANODLNA_LOG_DIR/backend.stdout.log" 2>> "$NANODLNA_LOG_DIR/backend.stderr.log"
        touch .deps_backend.stamp
    fi
}

ensure_frontend_dependencies() {
    if [ "$NANODLNA_FRONTEND_ENABLED" != "1" ]; then
        return
    fi

    cd "$NANODLNA_FRONTEND_DIR"
    if [ ! -f .deps_frontend.stamp ] || [ package-lock.json -nt .deps_frontend.stamp ] || [ package.json -nt .deps_frontend.stamp ]; then
        log "Installing frontend dependencies"
        "$NANODLNA_NPM_BIN" install >> "$NANODLNA_LOG_DIR/frontend.stdout.log" 2>> "$NANODLNA_LOG_DIR/frontend.stderr.log"
        touch .deps_frontend.stamp
    fi
}

start_children() {
    cd "$NANODLNA_BACKEND_DIR"
    log "Starting backend"
    PYTHONPATH="$NANODLNA_BACKEND_DIR" "$NANODLNA_PYTHON_BIN" run.py --host "$NANODLNA_HOST" --port "$NANODLNA_BACKEND_PORT" >> "$NANODLNA_LOG_DIR/backend.stdout.log" 2>> "$NANODLNA_LOG_DIR/backend.stderr.log" &
    BACKEND_PID=$!

    FRONTEND_PID=""
    if [ "$NANODLNA_FRONTEND_ENABLED" = "1" ]; then
        cd "$NANODLNA_FRONTEND_DIR"
        log "Starting frontend"
        PORT="$NANODLNA_FRONTEND_PORT" BROWSER=none "$NANODLNA_NPM_BIN" start >> "$NANODLNA_LOG_DIR/frontend.stdout.log" 2>> "$NANODLNA_LOG_DIR/frontend.stderr.log" &
        FRONTEND_PID=$!
    fi
}

trap 'log "Received stop signal"; stop_children; exit 0' INT TERM

while true; do
    ensure_backend_dependencies
    ensure_frontend_dependencies
    start_children

    while true; do
        sleep 2

        if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
            log "Backend exited; restarting service set"
            break
        fi

        if [ "$NANODLNA_FRONTEND_ENABLED" = "1" ] && [ -n "$FRONTEND_PID" ] && ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
            log "Frontend exited; restarting service set"
            break
        fi
    done

    stop_children
    sleep "$NANODLNA_SERVICE_RESTART_DELAY"
done
