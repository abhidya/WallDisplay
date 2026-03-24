#!/bin/bash

# Exit on error
set -e

# Store the root directory path
ROOT_DIR="$(pwd)"

# First, make sure any existing instances are stopped
"$ROOT_DIR/stop_dashboard.sh"

# Default configuration file
CONFIG_FILE="my_device_config.json"

# Parse command line arguments
if [ ! -z "$1" ]; then
  CONFIG_FILE="$1"
fi

# Check if the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Config file $CONFIG_FILE not found!"
  exit 1
fi

# Get absolute path of config file
CONFIG_PATH=$(realpath "$CONFIG_FILE")

# Check if ports are available
if lsof -ti:3000 > /dev/null || lsof -ti:8000 > /dev/null; then
    echo "Error: Ports 3000 or 8000 are still in use. Cannot start dashboard."
    echo "Try running ./stop_dashboard.sh again or manually kill the processes."
    exit 1
fi

# Clean up any lingering Twisted processes
echo "Cleaning up any lingering Twisted processes..."
pkill -f "twisted" 2>/dev/null || true
pkill -f "TwistedStreamingServer" 2>/dev/null || true

# Clean up the database
echo "Cleaning up the database..."
python clean_videos.py

# Add videos from the configuration to the database
echo "Adding videos from configuration to the database..."
python add_config_videos.py

# Reset the dashboard log file to ensure fresh logs
echo "Resetting dashboard log file..."
echo "--- Dashboard started at $(date) ---" > dashboard_run.log

# Start the dashboard
echo "Starting the dashboard..."
cd web && ./run_direct.sh &
DASHBOARD_PID=$!

# Return to the root directory
cd "$ROOT_DIR"

# Wait for the dashboard to start
echo "Waiting for dashboard to start..."
MAX_RETRIES=15  # Reduced from 30 to avoid long waits
RETRY_COUNT=0
while ! curl -s http://localhost:8000/health > /dev/null && [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "Waiting for backend... ($RETRY_COUNT/$MAX_RETRIES)"
    
    # Check if backend process is still running
    if ! ps -p $DASHBOARD_PID > /dev/null; then
        echo ""
        echo "Backend process has terminated. Check for errors in the logs:"
        echo "tail -n 50 dashboard_run.log"
        # Use full path to stop_dashboard.sh
        if [ -f "$ROOT_DIR/stop_dashboard.sh" ]; then
            "$ROOT_DIR/stop_dashboard.sh"
        else
            echo "Warning: stop_dashboard.sh not found. Attempting manual cleanup..."
            # Kill processes on specific ports
            lsof -ti:3000 | xargs kill -9 2>/dev/null || true
            lsof -ti:8000 | xargs kill -9 2>/dev/null || true
            # Kill specific processes by name
            pkill -f "react-scripts" 2>/dev/null || true
            pkill -f "uvicorn" 2>/dev/null || true
            pkill -f "twisted" 2>/dev/null || true
            pkill -f "TwistedStreamingServer" 2>/dev/null || true
        fi
        exit 1
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Error: Dashboard failed to start within the expected time."
    echo "Diagnostic information:"
    echo "1. Checking if Python processes are running:"
    ps aux | grep -E "python|twisted|TwistedStreamingServer"
    echo ""
    echo "2. Checking if ports are in use:"
    lsof -i :8000
    lsof -i :3000
    echo ""
    echo "3. Last few lines of logs:"
    tail -n 20 dashboard_run.log 2>/dev/null || echo "No log file found"
    echo ""
    echo "Please check logs for detailed error information."
    # Use full path to stop_dashboard.sh
    if [ -f "$ROOT_DIR/stop_dashboard.sh" ]; then
        "$ROOT_DIR/stop_dashboard.sh"
    else
        echo "Warning: stop_dashboard.sh not found. Attempting manual cleanup..."
        # Kill processes on specific ports
        lsof -ti:3000 | xargs kill -9 2>/dev/null || true
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        # Kill specific processes by name
        pkill -f "react-scripts" 2>/dev/null || true
        pkill -f "uvicorn" 2>/dev/null || true
        pkill -f "twisted" 2>/dev/null || true
        pkill -f "TwistedStreamingServer" 2>/dev/null || true
    fi
    exit 1
fi

echo "Dashboard is running."

# Load the configuration file
echo "Loading configuration file: $CONFIG_PATH"
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/devices/load-config?config_file=$CONFIG_PATH")
echo $RESPONSE

echo "Dashboard is running with devices loaded from configuration file."
echo "- Frontend: http://localhost:3000"
echo "- Backend API: http://localhost:8000"
echo "- API Documentation: http://localhost:8000/docs"

echo ""
echo "To stop the dashboard, press Ctrl+C"

# Wait for user to press Ctrl+C
trap "echo 'Stopping dashboard...'; '$ROOT_DIR/stop_dashboard.sh'; exit 0" INT
wait $DASHBOARD_PID
