#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../scripts/common_env.sh"

cd "$SCRIPT_DIR"
bash ./stop_direct.sh

if { [ "$NANODLNA_FRONTEND_ENABLED" = "1" ] && lsof -ti:"$NANODLNA_FRONTEND_PORT" > /dev/null; } || lsof -ti:"$NANODLNA_BACKEND_PORT" > /dev/null; then
    echo "Error: Required ports are still in use. Cannot start application."
    echo "Try running ./stop_direct.sh again or manually kill the processes."
    exit 1
fi

mkdir -p "$NANODLNA_ROOT_DIR/web/data" "$NANODLNA_ROOT_DIR/web/uploads" "$NANODLNA_LOG_DIR"

cd "$NANODLNA_BACKEND_DIR"
if [ ! -d "$NANODLNA_VENV_DIR" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$NANODLNA_VENV_DIR"
fi

if [ -x "$NANODLNA_VENV_DIR/bin/python" ]; then
    NANODLNA_PYTHON_BIN="$NANODLNA_VENV_DIR/bin/python"
fi

if [ ! -f .deps_backend.stamp ] || [ requirements.txt -nt .deps_backend.stamp ]; then
    "$NANODLNA_PYTHON_BIN" -m pip install -r requirements.txt
    touch .deps_backend.stamp
fi

echo "Checking for import errors..."
PYTHONPATH="$NANODLNA_BACKEND_DIR" "$NANODLNA_PYTHON_BIN" -c "import sys; sys.path.insert(0, '.'); import main" 2>/tmp/import_check.log

echo "Starting backend server..."
PYTHONPATH="$NANODLNA_BACKEND_DIR" "$NANODLNA_PYTHON_BIN" run.py --host "$NANODLNA_HOST" --port "$NANODLNA_BACKEND_PORT" >> "$NANODLNA_LOG_DIR/backend.stdout.log" 2>> "$NANODLNA_LOG_DIR/backend.stderr.log" &
BACKEND_PID=$!

echo "Waiting for backend to start..."
MAX_RETRIES=20
RETRY_COUNT=0
while ! curl -s "http://localhost:${NANODLNA_BACKEND_PORT}/health" > /dev/null && [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for backend... ($RETRY_COUNT/$MAX_RETRIES)"

    if ! ps -p $BACKEND_PID > /dev/null; then
        echo "Backend process ($BACKEND_PID) has terminated. Check logs for errors."
        exit 1
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Error: Backend failed to start within the expected time."
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo "Backend is running."
FRONTEND_PID=""

if [ "$NANODLNA_FRONTEND_ENABLED" = "1" ]; then
    cd "$NANODLNA_FRONTEND_DIR"
    if [ ! -f .deps_frontend.stamp ] || [ package-lock.json -nt .deps_frontend.stamp ] || [ package.json -nt .deps_frontend.stamp ]; then
        echo "Installing frontend dependencies..."
        "$NANODLNA_NPM_BIN" install
        touch .deps_frontend.stamp
    fi

    echo "Starting frontend server..."
    PORT="$NANODLNA_FRONTEND_PORT" BROWSER=none "$NANODLNA_NPM_BIN" start >> "$NANODLNA_LOG_DIR/frontend.stdout.log" 2>> "$NANODLNA_LOG_DIR/frontend.stderr.log" &
    FRONTEND_PID=$!
fi

cd "$SCRIPT_DIR"
echo "$BACKEND_PID $FRONTEND_PID" > .running_pids

echo "Application is running!"
if [ "$NANODLNA_FRONTEND_ENABLED" = "1" ]; then
    echo "- Frontend: http://localhost:${NANODLNA_FRONTEND_PORT}"
fi
echo "- Backend API: http://localhost:${NANODLNA_BACKEND_PORT}"
echo "- API Documentation: http://localhost:${NANODLNA_BACKEND_PORT}/docs"

echo ""
echo "To stop the application, run: ./stop_direct.sh"
echo "Press Ctrl+C to stop the application"

trap "echo 'Stopping application...'; bash ./stop_direct.sh; exit 0" INT
wait
