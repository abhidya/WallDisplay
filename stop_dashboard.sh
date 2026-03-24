#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/scripts/common_env.sh"

echo "Stopping the dashboard..."
echo "Killing any processes using ports $NANODLNA_FRONTEND_PORT and $NANODLNA_BACKEND_PORT..."
lsof -ti:"$NANODLNA_FRONTEND_PORT" | xargs kill -9 2>/dev/null || true
lsof -ti:"$NANODLNA_BACKEND_PORT" | xargs kill -9 2>/dev/null || true

echo "Killing any React, Uvicorn, or Twisted processes..."
pkill -f "react-scripts" 2>/dev/null || true
pkill -f "uvicorn" 2>/dev/null || true
pkill -f "twisted" 2>/dev/null || true
pkill -f "TwistedStreamingServer" 2>/dev/null || true
pkill -f "dashboard_supervisor.sh" 2>/dev/null || true

cd "$NANODLNA_ROOT_DIR/web"
bash ./stop_direct.sh
cd "$NANODLNA_ROOT_DIR"

if pgrep -f "react-scripts" > /dev/null || pgrep -f "uvicorn" > /dev/null || pgrep -f "twisted" > /dev/null || pgrep -f "TwistedStreamingServer" > /dev/null; then
    echo "Warning: Some processes may still be running."
    pkill -9 -f "react-scripts" || true
    pkill -9 -f "uvicorn" || true
    pkill -9 -f "twisted" || true
    pkill -9 -f "TwistedStreamingServer" || true
    sleep 1
fi

if pgrep -f "react-scripts" > /dev/null || pgrep -f "uvicorn" > /dev/null || pgrep -f "twisted" > /dev/null || pgrep -f "TwistedStreamingServer" > /dev/null; then
    echo "Warning: Unable to stop all processes. You may need to manually kill them."
    echo "Try running: ps aux | grep -E 'react-scripts|uvicorn|twisted|TwistedStreamingServer'"
else
    echo "Application stopped."
    echo "Dashboard stopped."
fi
