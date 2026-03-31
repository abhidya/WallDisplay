#!/bin/bash

COMMON_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$COMMON_ENV_DIR/.." && pwd)"

if [ -f "$ROOT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env"
    set +a
fi

export NANODLNA_ROOT_DIR="${NANODLNA_ROOT_DIR:-$ROOT_DIR}"
export NANODLNA_HOST="${NANODLNA_HOST:-0.0.0.0}"
export NANODLNA_BACKEND_PORT="${NANODLNA_BACKEND_PORT:-8000}"
export NANODLNA_FRONTEND_PORT="${NANODLNA_FRONTEND_PORT:-3000}"
export NANODLNA_FRONTEND_ENABLED="${NANODLNA_FRONTEND_ENABLED:-1}"
export NANODLNA_SERVICE_LABEL="${NANODLNA_SERVICE_LABEL:-com.nanodlna.dashboard}"
export NANODLNA_GIT_BRANCH="${NANODLNA_GIT_BRANCH:-main}"
export NANODLNA_GIT_REMOTE="${NANODLNA_GIT_REMOTE:-origin}"
export NANODLNA_GIT_AUTO_UPDATE="${NANODLNA_GIT_AUTO_UPDATE:-0}"
export NANODLNA_SERVICE_RESTART_DELAY="${NANODLNA_SERVICE_RESTART_DELAY:-5}"
export NANODLNA_INSTALL_PLAYWRIGHT="${NANODLNA_INSTALL_PLAYWRIGHT:-1}"
export NANODLNA_BACKEND_START_TIMEOUT="${NANODLNA_BACKEND_START_TIMEOUT:-120}"
export NANODLNA_DASHBOARD_START_TIMEOUT="${NANODLNA_DASHBOARD_START_TIMEOUT:-180}"
export NANODLNA_PORT_RELEASE_TIMEOUT="${NANODLNA_PORT_RELEASE_TIMEOUT:-10}"

if [ -z "${NANODLNA_VENV_DIR:-}" ]; then
    if [ -d "$NANODLNA_ROOT_DIR/.venv" ]; then
        NANODLNA_VENV_DIR="$NANODLNA_ROOT_DIR/.venv"
    else
        NANODLNA_VENV_DIR="$NANODLNA_ROOT_DIR/web/backend/venv"
    fi
fi
export NANODLNA_VENV_DIR

if [ -z "${NANODLNA_PYTHON_BIN:-}" ]; then
    if [ -x "$NANODLNA_VENV_DIR/bin/python" ]; then
        NANODLNA_PYTHON_BIN="$NANODLNA_VENV_DIR/bin/python"
    else
        NANODLNA_PYTHON_BIN="${PYTHON:-python3}"
    fi
fi
export NANODLNA_PYTHON_BIN

export NANODLNA_NPM_BIN="${NANODLNA_NPM_BIN:-npm}"
export NANODLNA_LOG_DIR="${NANODLNA_LOG_DIR:-$NANODLNA_ROOT_DIR/logs}"
export NANODLNA_BACKEND_DIR="$NANODLNA_ROOT_DIR/web/backend"
export NANODLNA_FRONTEND_DIR="$NANODLNA_ROOT_DIR/web/frontend"
export NANODLNA_DB_PATH="${NANODLNA_DB_PATH:-$NANODLNA_BACKEND_DIR/nanodlna.db}"

if [ -n "${NANODLNA_CONFIG_FILE:-}" ] && [[ "$NANODLNA_CONFIG_FILE" != /* ]]; then
    export NANODLNA_CONFIG_FILE="$NANODLNA_ROOT_DIR/$NANODLNA_CONFIG_FILE"
fi

nanodlna_listener_pid_for_port() {
    local port="$1"
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1
}

nanodlna_wait_for_port_release() {
    local port="$1"
    local label="$2"
    local timeout="${3:-$NANODLNA_PORT_RELEASE_TIMEOUT}"
    local listener_pid=""
    local attempt=0

    while [ "$attempt" -lt "$timeout" ]; do
        listener_pid="$(nanodlna_listener_pid_for_port "$port")"
        if [ -z "$listener_pid" ]; then
            return 0
        fi

        attempt=$((attempt + 1))
        echo "Waiting for ${label} port ${port} to clear... (${attempt}/${timeout})"
        sleep 1
    done

    listener_pid="$(nanodlna_listener_pid_for_port "$port")"
    if [ -n "$listener_pid" ]; then
        echo "Port ${port} is still held by PID ${listener_pid}."
        return 1
    fi

    return 0
}
