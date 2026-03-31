#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../scripts/common_env.sh"

kill_frontend_processes() {
    pkill -f "node.*react-scripts" 2>/dev/null || true
    pkill -f "react-scripts.*start" 2>/dev/null || true
    pkill -f "webpack-dev-server" 2>/dev/null || true
    pkill -f "npm.*start" 2>/dev/null || true
    pkill -f "$NANODLNA_FRONTEND_DIR" 2>/dev/null || true
}

echo "Killing any processes using ports $NANODLNA_FRONTEND_PORT and $NANODLNA_BACKEND_PORT..."
lsof -ti:"$NANODLNA_FRONTEND_PORT" | xargs kill -9 2>/dev/null || true
lsof -ti:"$NANODLNA_BACKEND_PORT" | xargs kill -9 2>/dev/null || true

echo "Killing any React or Uvicorn processes..."
kill_frontend_processes
pkill -f "uvicorn" || true

cd "$SCRIPT_DIR"
if [ -f .running_pids ]; then
    read BACKEND_PID FRONTEND_PID < .running_pids

    echo "Stopping backend server (PID: $BACKEND_PID)..."
    kill -9 $BACKEND_PID 2>/dev/null || true

    if [ -n "$FRONTEND_PID" ]; then
        echo "Stopping frontend server (PID: $FRONTEND_PID)..."
        pkill -P "$FRONTEND_PID" 2>/dev/null || true
        kill -9 $FRONTEND_PID 2>/dev/null || true
    fi

    rm -f .running_pids
fi

if pgrep -f "node.*react-scripts" > /dev/null || pgrep -f "uvicorn" > /dev/null; then
    echo "Warning: Some processes may still be running."
    kill_frontend_processes
    pkill -9 -f "uvicorn" || true
    sleep 1
fi

if pgrep -f "node.*react-scripts|webpack-dev-server|npm.*start" > /dev/null || pgrep -f "uvicorn" > /dev/null; then
    echo "Warning: Unable to stop all processes. You may need to manually kill them."
else
    echo "Application stopped."
fi
