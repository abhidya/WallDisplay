#!/usr/bin/env python3
# encoding: UTF-8

import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(log_level="INFO", log_file="app.log"):
    """
    Centralized logging configuration to prevent duplicate logs
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatters
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(console_formatter)
    
    # Error console handler with highlighting (always show errors regardless of level)
    error_console_handler = logging.StreamHandler()
    error_console_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        '\033[91m%(asctime)s - %(name)s - %(levelname)s - %(message)s\033[0m',  # Red color for errors
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_console_handler.setFormatter(error_formatter)
    
    # Resolve and create log directory when needed.
    log_file_path = os.path.abspath(log_file)
    log_dir = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    file_handler = None
    try:
        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(file_formatter)
    except OSError as exc:
        console_handler.handle(
            logging.LogRecord(
                name=__name__,
                level=logging.WARNING,
                pathname=__file__,
                lineno=0,
                msg=f"File logging disabled (cannot open {log_file_path}): {exc}",
                args=(),
                exc_info=None,
            )
        )
    
    # Configure root logger only once
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove all existing handlers to prevent duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add our handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_console_handler)
    if file_handler:
        root_logger.addHandler(file_handler)
    
    # Create a separate error log file
    error_log_path = os.path.join(log_dir or ".", "errors.log")
    try:
        error_file_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10  # Keep more error logs
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_file_handler)
    except OSError as exc:
        console_handler.handle(
            logging.LogRecord(
                name=__name__,
                level=logging.WARNING,
                pathname=__file__,
                lineno=0,
                msg=f"Error-file logging disabled (cannot open {error_log_path}): {exc}",
                args=(),
                exc_info=None,
            )
        )
    
    # Prevent propagation to avoid duplicate logs
    logging.getLogger("uvicorn").propagate = False
    logging.getLogger("uvicorn.access").propagate = False
    
    # Set specific log levels for different components
    component_levels = {
        # Backend components
        "core.twisted_streaming": numeric_level,  # Main streaming service
        "core.streaming_service": numeric_level,
        "core.transcreen_projector": numeric_level,
        "core.dlna_server": numeric_level,
        "core.device_manager": numeric_level,
        "core.streaming_registry": numeric_level,
        "routers": numeric_level,
        
        # Database (DDB)
        "database": numeric_level,
        "sqlalchemy.engine": logging.WARNING,  # Only show warnings and errors
        
        # Frontend-related (API calls)
        "uvicorn.access": logging.WARNING,  # Reduce noise from HTTP requests
        "uvicorn.error": numeric_level,
        
        # Twisted/DLNA specific
        "twisted": logging.WARNING,  # Reduce Twisted verbosity
        
        # Third-party libraries
        "urllib3": logging.WARNING,
        "asyncio": logging.WARNING,
    }
    
    for logger_name, level in component_levels.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        
    return root_logger

def get_logger(name):
    """
    Get a logger instance that won't create duplicate logs
    """
    logger = logging.getLogger(name)
    # Don't add handlers to child loggers - they'll use the root logger's handlers
    logger.propagate = True
    return logger

# Recommended log levels for different use cases:
# 
# DEBUG: Full visibility into all operations (very verbose)
#   - Use when debugging specific issues
#   - Shows all SQL queries, HTTP requests, file operations
#
# INFO: Standard operational information
#   - Device connections/disconnections
#   - Streaming start/stop events
#   - Configuration changes
#   - Recommended for run_dashboard.sh
#
# WARNING: Potentially harmful situations
#   - Port conflicts
#   - Resource limitations
#   - Non-critical errors that were recovered
#
# ERROR: Error events that might still allow the app to continue
#   - Failed device connections
#   - File not found errors
#   - Network errors
#
# CRITICAL: Very serious errors that might cause the app to abort
#   - Database corruption
#   - Unable to bind to required ports
#   - Critical configuration missing
