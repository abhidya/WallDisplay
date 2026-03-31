#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/scripts/common_env.sh"

"$NANODLNA_ROOT_DIR/stop_dashboard.sh"

CONFIG_FILE="${1:-${NANODLNA_CONFIG_FILE:-$NANODLNA_ROOT_DIR/my_device_config.json}}"
if [[ "$CONFIG_FILE" != /* ]]; then
    CONFIG_FILE="$NANODLNA_ROOT_DIR/$CONFIG_FILE"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config file $CONFIG_FILE not found!"
    exit 1
fi

CONFIG_PATH="$(cd "$(dirname "$CONFIG_FILE")" && pwd)/$(basename "$CONFIG_FILE")"

if [ "$NANODLNA_FRONTEND_ENABLED" = "1" ] && ! nanodlna_wait_for_port_release "$NANODLNA_FRONTEND_PORT" "frontend"; then
    echo "Error: Frontend port $NANODLNA_FRONTEND_PORT is still in use. Cannot start dashboard."
    echo "Try running ./stop_dashboard.sh again or manually kill the processes."
    exit 1
fi

if ! nanodlna_wait_for_port_release "$NANODLNA_BACKEND_PORT" "backend"; then
    echo "Error: Backend port $NANODLNA_BACKEND_PORT is still in use. Cannot start dashboard."
    echo "Try running ./stop_dashboard.sh again or manually kill the processes."
    exit 1
fi

if { [ "$NANODLNA_FRONTEND_ENABLED" = "1" ] && [ -n "$(nanodlna_listener_pid_for_port "$NANODLNA_FRONTEND_PORT")" ]; } || [ -n "$(nanodlna_listener_pid_for_port "$NANODLNA_BACKEND_PORT")" ]; then
    echo "Error: Required ports are still in use. Cannot start dashboard."
    echo "Try running ./stop_dashboard.sh again or manually kill the processes."
    exit 1
fi

echo "Cleaning up any lingering Twisted processes..."
pkill -f "twisted" 2>/dev/null || true
pkill -f "TwistedStreamingServer" 2>/dev/null || true

echo "Cleaning up the database..."
"$NANODLNA_PYTHON_BIN" "$NANODLNA_ROOT_DIR/clean_videos.py" "$NANODLNA_DB_PATH"

echo "Adding videos from configuration to the database..."
"$NANODLNA_PYTHON_BIN" "$NANODLNA_ROOT_DIR/add_config_videos.py" "$CONFIG_PATH" "$NANODLNA_DB_PATH"

mkdir -p "$NANODLNA_LOG_DIR"
echo "Resetting dashboard log file..."
echo "--- Dashboard started at $(date) ---" > "$NANODLNA_LOG_DIR/dashboard_run.log"

echo "Starting the dashboard..."
cd "$NANODLNA_ROOT_DIR/web"
bash ./run_direct.sh &
DASHBOARD_PID=$!
cd "$NANODLNA_ROOT_DIR"

echo "Waiting for dashboard to start..."
MAX_RETRIES="$NANODLNA_DASHBOARD_START_TIMEOUT"
RETRY_COUNT=0
RUNNING_PIDS_FILE="$NANODLNA_ROOT_DIR/web/.running_pids"
BACKEND_PID=""
BACKEND_PORT_OWNER=""
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if ! ps -p $DASHBOARD_PID > /dev/null; then
        echo ""
        echo "Backend process has terminated. Check $NANODLNA_LOG_DIR/dashboard_run.log"
        "$NANODLNA_ROOT_DIR/stop_dashboard.sh" || true
        exit 1
    fi

    if [ -f "$RUNNING_PIDS_FILE" ]; then
        read -r BACKEND_PID _ < "$RUNNING_PIDS_FILE"
        BACKEND_PORT_OWNER="$(nanodlna_listener_pid_for_port "$NANODLNA_BACKEND_PORT")"

        if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null && [ "$BACKEND_PORT_OWNER" = "$BACKEND_PID" ] && curl -fsS "http://localhost:${NANODLNA_BACKEND_PORT}/health" > /dev/null 2>&1; then
            break
        fi
    fi

    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for backend... ($RETRY_COUNT/$MAX_RETRIES)"
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Error: Dashboard failed to start within the expected time."
    echo "Diagnostic information:"
    ps aux | grep -E "python|twisted|TwistedStreamingServer"
    lsof -i :"$NANODLNA_BACKEND_PORT" || true
    if [ "$NANODLNA_FRONTEND_ENABLED" = "1" ]; then
        lsof -i :"$NANODLNA_FRONTEND_PORT" || true
    fi
    tail -n 20 "$NANODLNA_LOG_DIR/dashboard_run.log" 2>/dev/null || echo "No log file found"
    "$NANODLNA_ROOT_DIR/stop_dashboard.sh" || true
    exit 1
fi

echo "Dashboard is running."
echo "Loading configuration file: $CONFIG_PATH"
RESPONSE=$(curl -s -X POST "http://localhost:${NANODLNA_BACKEND_PORT}/api/devices/load-config?config_file=$CONFIG_PATH")
echo "$RESPONSE"

echo "Dashboard is running with devices loaded from configuration file."
if [ "$NANODLNA_FRONTEND_ENABLED" = "1" ]; then
    echo "- Frontend: http://localhost:${NANODLNA_FRONTEND_PORT}"
fi
echo "- Backend API: http://localhost:${NANODLNA_BACKEND_PORT}"
echo "- API Documentation: http://localhost:${NANODLNA_BACKEND_PORT}/docs"

echo ""
echo "To stop the dashboard, press Ctrl+C"

trap "echo 'Stopping dashboard...'; '$NANODLNA_ROOT_DIR/stop_dashboard.sh'; exit 0" INT
wait $DASHBOARD_PID
