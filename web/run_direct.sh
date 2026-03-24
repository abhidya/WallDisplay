#!/bin/bash

# Exit on error
set -e

# First, make sure any existing instances are stopped
./stop_direct.sh

# Check if ports are available
if lsof -ti:3000 > /dev/null || lsof -ti:8000 > /dev/null; then
    echo "Error: Ports 3000 or 8000 are still in use. Cannot start application."
    echo "Try running ./stop_direct.sh again or manually kill the processes."
    exit 1
fi

# Create necessary directories
mkdir -p data uploads

# Set up Python environment for backend
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python -m venv venv
fi

# Activate virtual environment and install dependencies
source /Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/.venv/bin/activate
pip install -r requirements.txt
#
# Check for import errors before running the server
echo "Checking for import errors..."
PYTHONPATH=/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/.venv/bin/python python -c "import sys; sys.path.insert(0, '.'); import main" 2>/tmp/import_check.log
if [ $? -ne 0 ]; then
    echo "Import error detected. Check the error log:"
    cat /tmp/import_check.log
    echo "Fixing common import issue in streaming_router.py..."

    # Fix known issue with relative imports
    STREAMING_ROUTER="routers/streaming_router.py"
    if [ -f "$STREAMING_ROUTER" ]; then
        # Replace relative import with absolute import
        sed -i'' -e 's/from ..core.streaming_registry/from core.streaming_registry/g' "$STREAMING_ROUTER"
        echo "Fixed import in $STREAMING_ROUTER"
    fi

    # Check again after fix
    PYTHONPATH=/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/.venv/bin/python python -c "import sys; sys.path.insert(0, '.'); import main" 2>/tmp/import_check.log
    if [ $? -ne 0 ]; then
        echo "Import issues persist after attempted fix:"
        cat /tmp/import_check.log
        echo "Please fix the import issues manually before continuing."
        exit 1
    else
        echo "Import issues fixed successfully."
    fi
fi

# Run the backend in the background
echo "Starting backend server..."
PYTHONPATH=/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/.venv/bin/python python run.py &
BACKEND_PID=$!

# Wait for backend to start and verify it's running
echo "Waiting for backend to start..."
MAX_RETRIES=20
RETRY_COUNT=0
while ! curl -s http://localhost:8000/health > /dev/null && [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "Waiting for backend... ($RETRY_COUNT/$MAX_RETRIES)"
    
    # Check if backend process is still running
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

# Set up Node environment for frontend
cd ../frontend
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Run the frontend
echo "Starting frontend server..."
npm start &
FRONTEND_PID=$!

# Save PIDs to file for stopping later
cd ..
echo "$BACKEND_PID $FRONTEND_PID" > .running_pids

echo "Application is running!"
echo "- Frontend: http://localhost:3000"
echo "- Backend API: http://localhost:8000"
echo "- API Documentation: http://localhost:8000/docs"

echo ""
echo "To stop the application, run: ./stop_direct.sh"
echo "Press Ctrl+C to stop the application"

# Wait for user to press Ctrl+C
trap "echo 'Stopping application...'; ./stop_direct.sh; exit 0" INT
wait
