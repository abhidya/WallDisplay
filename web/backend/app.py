#!/usr/bin/env python3

"""
This module serves as an entry point for the application.
It imports the FastAPI app from the main module and can be run directly.
"""

import sys
import os

# Add the current directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))
sys.path.insert(0, backend_dir)
sys.path.insert(0, project_root)

# Import the FastAPI app from the main module
from web.backend.main import app

# This allows the file to be run directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
