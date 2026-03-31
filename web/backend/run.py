#!/usr/bin/env python3

import uvicorn
import argparse
import logging
import sys
import os

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _resolve_backend_log_file() -> str:
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(backend_dir, "..", ".."))
    log_dir = os.environ.get("NANODLNA_LOG_DIR") or os.path.join(root_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "dashboard_run.log")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the nano-dlna Dashboard API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Use centralized logging configuration
    try:
        from logging_config import setup_logging
        log_level = "DEBUG" if args.debug else "INFO"
        setup_logging(log_level=log_level, log_file=_resolve_backend_log_file())
    except ImportError:
        # Fallback to basic config if logging_config not available
        log_level = logging.DEBUG if args.debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    
    # Run the server
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )
