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
    pkill -P $$ -f "ngrok http" 2>/dev/null || true
    pkill -f "ngrok http $NANODLNA_FRONTEND_PORT" 2>/dev/null || true
    wait 2>/dev/null || true
}

trap 'log "Received stop signal"; stop_children; exit 0' INT TERM

while true; do
    log "Starting dashboard through run_dashboard.sh"
    
    NGROK_CMD=""
    if command -v ngrok >/dev/null 2>&1; then
        NGROK_CMD="ngrok"
    elif [ -x "$NANODLNA_VENV_DIR/bin/ngrok" ]; then
        NGROK_CMD="$NANODLNA_VENV_DIR/bin/ngrok"
    fi

    if [ -n "$NGROK_CMD" ]; then
        log "Starting Ngrok tunnel for secure external access using $NGROK_CMD..."
        
        # Ensure ngrok binary is fully downloaded by pyngrok if using the venv wrapper
        if [ "$NGROK_CMD" = "$NANODLNA_VENV_DIR/bin/ngrok" ]; then
            "$NANODLNA_PYTHON_BIN" -c "from pyngrok import ngrok; ngrok.install_ngrok()" >/dev/null 2>&1 || true
        fi
        
        pkill -P $$ -f "ngrok http" 2>/dev/null || true
        pkill -f "ngrok http $NANODLNA_FRONTEND_PORT" 2>/dev/null || true
        "$NGROK_CMD" http "$NANODLNA_FRONTEND_PORT" > /dev/null &
        NGROK_PID=$!
        
        # Wait for Ngrok to spin up
        sleep 4
        NGROK_URL=$("$NANODLNA_PYTHON_BIN" -c "
try:
    import urllib.request, json
    data = json.loads(urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels').read().decode())
    print([t['public_url'] for t in data.get('tunnels', []) if t['public_url'].startswith('https')][0])
except Exception:
    print('')
" 2>/dev/null)
        log "Secure Public URL (for Projector): $NGROK_URL"
    fi

    set +e
    "$NANODLNA_ROOT_DIR/run_dashboard.sh" >> "$NANODLNA_LOG_DIR/launchd-dashboard.out.log" 2>> "$NANODLNA_LOG_DIR/launchd-dashboard.err.log"
    exit_code=$?
    set -e
    log "run_dashboard.sh exited with code $exit_code; restarting after delay"
    "$NANODLNA_ROOT_DIR/stop_dashboard.sh" >> "$NANODLNA_LOG_DIR/launchd-dashboard.out.log" 2>> "$NANODLNA_LOG_DIR/launchd-dashboard.err.log" || true
    sleep "$NANODLNA_SERVICE_RESTART_DELAY"
done
