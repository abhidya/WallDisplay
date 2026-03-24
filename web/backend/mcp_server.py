#!/usr/bin/env python3

import asyncio
import logging
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiofiles
from dataclasses import dataclass
from collections import deque
import re

# MCP imports - Fix for FastMCP 2.0
from fastmcp import FastMCP
from mcp.types import Tool, TextContent

# FastAPI integration
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

# Import logging config from the project
try:
    from logging_config import get_logger
except ImportError:
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger(__name__)

@dataclass
class LogEntry:
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    filename: str
    line_number: int
    extra_data: Dict[str, Any] = None

class LogStreamManager:
    """Manages log streaming and aggregation from multiple sources"""
    
    def __init__(self):
        self.log_buffer = deque(maxlen=10000)  # Keep last 10k entries
        self.active_streams = {}
        self.log_files = {
            'dashboard': '/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/web/backend/dashboard_run.log',
            'errors': '/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/web/backend/errors.log',
            'root_dashboard': '/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/dashboard_run.log',
            'root_errors': '/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/errors.log'
        }
        self.frontend_logs = deque(maxlen=1000)
        self.db_logs = deque(maxlen=1000)
        
    async def tail_log_file(self, file_path: str, lines: int = 100) -> List[str]:
        """Tail a log file and return the last N lines"""
        try:
            if not os.path.exists(file_path):
                return [f"Log file not found: {file_path}"]
                
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
                all_lines = content.split('\n')
                return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception as e:
            logger.error(f"Error tailing log file {file_path}: {e}")
            return [f"Error reading log file: {str(e)}"]
    
    async def watch_log_file(self, file_path: str, callback):
        """Watch a log file for new entries"""
        if not os.path.exists(file_path):
            logger.warning(f"Log file does not exist: {file_path}")
            return
            
        try:
            # Get initial file size
            stat = os.stat(file_path)
            size = stat.st_size
            
            async with aiofiles.open(file_path, 'r') as f:
                # Start from the end
                await f.seek(size)
                
                while True:
                    line = await f.readline()
                    if line:
                        await callback(line.strip())
                    else:
                        # Check if file was rotated
                        current_stat = os.stat(file_path)
                        if current_stat.st_size < size:
                            # File was rotated, start from beginning
                            await f.seek(0)
                            size = 0
                        else:
                            size = current_stat.st_size
                            await asyncio.sleep(0.1)
                            
        except Exception as e:
            logger.error(f"Error watching log file {file_path}: {e}")
    
    def parse_log_line(self, line: str, source: str) -> Optional[LogEntry]:
        """Parse a log line into a LogEntry"""
        if not line.strip():
            return None
            
        # Common log patterns
        patterns = [
            # 2024-01-01 12:00:00 - module.name - INFO - message
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([^-]+) - (\w+) - (.+)',
            # 2024-01-01 12:00:00,123 - module.name - INFO - filename:line - message
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) - ([^-]+) - (\w+) - ([^-]+) - (.+)',
            # [2024-01-01 12:00:00] INFO module.name: message
            r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (\w+) ([^:]+): (.+)',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                groups = match.groups()
                try:
                    timestamp_str = groups[0]
                    # Handle comma milliseconds
                    timestamp_str = timestamp_str.replace(',', '.')
                    timestamp = datetime.strptime(timestamp_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    
                    if len(groups) == 4:
                        logger_name, level, message = groups[1], groups[2], groups[3]
                        filename, line_number = "unknown", 0
                    else:
                        logger_name, level, location, message = groups[1], groups[2], groups[3], groups[4]
                        filename = location.split(':')[0] if ':' in location else location
                        line_number = int(location.split(':')[1]) if ':' in location and location.split(':')[1].isdigit() else 0
                    
                    return LogEntry(
                        timestamp=timestamp,
                        level=level.strip(),
                        logger_name=logger_name.strip(),
                        message=message.strip(),
                        filename=filename,
                        line_number=line_number,
                        extra_data={'source': source, 'raw_line': line}
                    )
                except Exception as e:
                    logger.debug(f"Failed to parse timestamp in line: {line} - {e}")
        
        # Fallback: treat as unstructured log
        return LogEntry(
            timestamp=datetime.now(),
            level="INFO",
            logger_name=source,
            message=line,
            filename="unknown",
            line_number=0,
            extra_data={'source': source, 'raw_line': line, 'unstructured': True}
        )
    
    def add_frontend_log(self, log_data: Dict[str, Any]):
        """Add a frontend log entry"""
        entry = LogEntry(
            timestamp=datetime.fromtimestamp(log_data.get('timestamp', datetime.now().timestamp())),
            level=log_data.get('level', 'INFO'),
            logger_name='frontend',
            message=log_data.get('message', ''),
            filename=log_data.get('filename', 'unknown'),
            line_number=log_data.get('line_number', 0),
            extra_data={'source': 'frontend', 'data': log_data}
        )
        self.frontend_logs.append(entry)
        self.log_buffer.append(entry)
    
    def add_db_log(self, query: str, params: List[Any] = None, duration: float = None, error: str = None):
        """Add a database operation log"""
        entry = LogEntry(
            timestamp=datetime.now(),
            level="ERROR" if error else "INFO",
            logger_name="database",
            message=f"Query: {query}" + (f" | Error: {error}" if error else ""),
            filename="database",
            line_number=0,
            extra_data={
                'source': 'database',
                'query': query,
                'params': params,
                'duration': duration,
                'error': error
            }
        )
        self.db_logs.append(entry)
        self.log_buffer.append(entry)
    
    def get_logs(self, 
                 sources: List[str] = None,
                 levels: List[str] = None,
                 since: datetime = None,
                 limit: int = 100) -> List[Dict[str, Any]]:
        """Get filtered logs"""
        logs = list(self.log_buffer)
        
        # Apply filters
        if sources:
            logs = [log for log in logs if log.extra_data and log.extra_data.get('source') in sources]
        
        if levels:
            logs = [log for log in logs if log.level in levels]
        
        if since:
            logs = [log for log in logs if log.timestamp >= since]
        
        # Sort by timestamp (newest first)
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Limit results
        logs = logs[:limit]
        
        # Convert to dict format
        return [
            {
                'timestamp': log.timestamp.isoformat(),
                'level': log.level,
                'logger_name': log.logger_name,
                'message': log.message,
                'filename': log.filename,
                'line_number': log.line_number,
                'source': log.extra_data.get('source') if log.extra_data else 'unknown',
                'extra_data': log.extra_data
            }
            for log in logs
        ]

# Initialize the log stream manager
log_manager = LogStreamManager()

# Initialize FastMCP server
mcp = FastMCP(name="NanoDLNA Log Streaming")

@mcp.tool()
async def get_backend_logs(
    lines: int = 100,
    log_type: str = "dashboard"
) -> List[TextContent]:
    """
    Get backend Python logs from dashboard_run.log or errors.log
    
    Args:
        lines: Number of lines to retrieve (default: 100)
        log_type: Type of log file ('dashboard', 'errors', 'root_dashboard', 'root_errors')
    """
    if log_type not in log_manager.log_files:
        available_types = ", ".join(log_manager.log_files.keys())
        return [TextContent(
            type="text",
            text=f"Invalid log_type. Available types: {available_types}"
        )]
    
    file_path = log_manager.log_files[log_type]
    log_lines = await log_manager.tail_log_file(file_path, lines)
    
    # Format logs for better readability
    formatted_logs = []
    for line in log_lines:
        if line.strip():
            parsed = log_manager.parse_log_line(line, log_type)
            if parsed:
                formatted_logs.append(
                    f"[{parsed.timestamp}] {parsed.level} {parsed.logger_name}: {parsed.message}"
                )
            else:
                formatted_logs.append(line)
    
    content = "\n".join(formatted_logs)
    
    return [TextContent(
        type="text",
        text=f"=== {log_type.upper()} LOGS (Last {lines} lines) ===\n\n{content}"
    )]

@mcp.tool()
async def get_frontend_logs(limit: int = 50) -> List[TextContent]:
    """
    Get frontend React console logs
    
    Args:
        limit: Maximum number of log entries to return
    """
    logs = [
        {
            'timestamp': log.timestamp.isoformat(),
            'level': log.level,
            'message': log.message,
            'filename': log.filename,
            'extra_data': log.extra_data
        }
        for log in list(log_manager.frontend_logs)[-limit:]
    ]
    
    if not logs:
        return [TextContent(
            type="text",
            text="No frontend logs available. Frontend logs are collected when the React app sends them to the backend."
        )]
    
    formatted_logs = []
    for log in logs:
        formatted_logs.append(
            f"[{log['timestamp']}] {log['level']} {log['filename']}: {log['message']}"
        )
    
    content = "\n".join(formatted_logs)
    
    return [TextContent(
        type="text",
        text=f"=== FRONTEND LOGS (Last {limit} entries) ===\n\n{content}"
    )]

@mcp.tool()
async def get_database_logs(limit: int = 50) -> List[TextContent]:
    """
    Get database operation logs
    
    Args:
        limit: Maximum number of log entries to return
    """
    logs = [
        {
            'timestamp': log.timestamp.isoformat(),
            'level': log.level,
            'message': log.message,
            'query': log.extra_data.get('query') if log.extra_data else None,
            'duration': log.extra_data.get('duration') if log.extra_data else None,
            'error': log.extra_data.get('error') if log.extra_data else None
        }
        for log in list(log_manager.db_logs)[-limit:]
    ]
    
    if not logs:
        return [TextContent(
            type="text",
            text="No database logs available. Database logs are collected when SQL operations are performed."
        )]
    
    formatted_logs = []
    for log in logs:
        duration_str = f" ({log['duration']:.3f}s)" if log['duration'] else ""
        error_str = f" | ERROR: {log['error']}" if log['error'] else ""
        formatted_logs.append(
            f"[{log['timestamp']}] {log['level']}: {log['query']}{duration_str}{error_str}"
        )
    
    content = "\n".join(formatted_logs)
    
    return [TextContent(
        type="text",
        text=f"=== DATABASE LOGS (Last {limit} entries) ===\n\n{content}"
    )]

@mcp.tool()
async def get_aggregated_logs(
    sources: Optional[List[str]] = None,
    levels: Optional[List[str]] = None,
    minutes_back: int = 60,
    limit: int = 200
) -> List[TextContent]:
    """
    Get aggregated logs from all sources with filtering
    
    Args:
        sources: List of sources to include (e.g., ['backend', 'frontend', 'database'])
        levels: List of log levels to include (e.g., ['ERROR', 'WARNING'])
        minutes_back: How many minutes back to search (default: 60)
        limit: Maximum number of log entries to return
    """
    since = datetime.now() - timedelta(minutes=minutes_back)
    
    # Get filtered logs
    logs = log_manager.get_logs(
        sources=sources,
        levels=levels,
        since=since,
        limit=limit
    )
    
    if not logs:
        filter_desc = []
        if sources:
            filter_desc.append(f"sources: {sources}")
        if levels:
            filter_desc.append(f"levels: {levels}")
        filter_desc.append(f"last {minutes_back} minutes")
        
        return [TextContent(
            type="text",
            text=f"No logs found with filters: {', '.join(filter_desc)}"
        )]
    
    # Format logs
    formatted_logs = []
    for log in logs:
        source_prefix = f"[{log['source'].upper()}]"
        timestamp = log['timestamp']
        level = log['level']
        logger_name = log['logger_name']
        message = log['message']
        
        formatted_logs.append(
            f"{source_prefix} [{timestamp}] {level} {logger_name}: {message}"
        )
    
    content = "\n".join(formatted_logs)
    
    # Add summary header
    summary = f"Found {len(logs)} log entries"
    if sources:
        summary += f" from sources: {sources}"
    if levels:
        summary += f" with levels: {levels}"
    summary += f" in the last {minutes_back} minutes"
    
    return [TextContent(
        type="text",
        text=f"=== AGGREGATED LOGS ===\n{summary}\n\n{content}"
    )]

@mcp.tool()
async def search_logs(
    query: str,
    sources: Optional[List[str]] = None,
    case_sensitive: bool = False,
    limit: int = 100
) -> List[TextContent]:
    """
    Search through all logs for specific text patterns
    
    Args:
        query: Text to search for in log messages
        sources: List of sources to search in (optional)
        case_sensitive: Whether search should be case sensitive
        limit: Maximum number of results to return
    """
    # Get all logs
    all_logs = log_manager.get_logs(sources=sources, limit=10000)
    
    # Search through logs
    search_query = query if case_sensitive else query.lower()
    matching_logs = []
    
    for log in all_logs:
        message = log['message'] if case_sensitive else log['message'].lower()
        logger_name = log['logger_name'] if case_sensitive else log['logger_name'].lower()
        
        if search_query in message or search_query in logger_name:
            matching_logs.append(log)
            
        if len(matching_logs) >= limit:
            break
    
    if not matching_logs:
        return [TextContent(
            type="text",
            text=f"No logs found matching query: '{query}'"
        )]
    
    # Format results
    formatted_logs = []
    for log in matching_logs:
        source_prefix = f"[{log['source'].upper()}]"
        timestamp = log['timestamp']
        level = log['level']
        logger_name = log['logger_name']
        message = log['message']
        
        # Highlight the search term (simple approach)
        if not case_sensitive:
            highlighted_message = message.replace(
                query.lower(), 
                f"**{query.lower()}**"
            )
        else:
            highlighted_message = message.replace(
                query, 
                f"**{query}**"
            )
        
        formatted_logs.append(
            f"{source_prefix} [{timestamp}] {level} {logger_name}: {highlighted_message}"
        )
    
    content = "\n".join(formatted_logs)
    
    return [TextContent(
        type="text",
        text=f"=== SEARCH RESULTS ===\nQuery: '{query}'\nFound {len(matching_logs)} matches\n\n{content}"
    )]

@mcp.tool()
async def tail_logs_realtime(
    sources: Optional[List[str]] = None,
    levels: Optional[List[str]] = None,
    duration_seconds: int = 30
) -> List[TextContent]:
    """
    Tail logs in real-time for a specified duration
    
    Args:
        sources: List of sources to monitor
        levels: List of log levels to show
        duration_seconds: How long to monitor (default: 30 seconds)
    """
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=duration_seconds)
    
    collected_logs = []
    
    # Monitor for the specified duration
    while datetime.now() < end_time:
        # Get recent logs
        logs = log_manager.get_logs(
            sources=sources,
            levels=levels,
            since=start_time,
            limit=1000
        )
        
        # Add new logs to collection
        for log in logs:
            if log not in collected_logs:
                collected_logs.append(log)
        
        await asyncio.sleep(1)  # Check every second
    
    if not collected_logs:
        return [TextContent(
            type="text",
            text=f"No new logs captured during {duration_seconds} seconds of monitoring."
        )]
    
    # Sort by timestamp
    collected_logs.sort(key=lambda x: x['timestamp'])
    
    # Format logs
    formatted_logs = []
    for log in collected_logs:
        source_prefix = f"[{log['source'].upper()}]"
        timestamp = log['timestamp']
        level = log['level']
        logger_name = log['logger_name']
        message = log['message']
        
        formatted_logs.append(
            f"{source_prefix} [{timestamp}] {level} {logger_name}: {message}"
        )
    
    content = "\n".join(formatted_logs)
    
    return [TextContent(
        type="text",
        text=f"=== REAL-TIME LOG TAIL ===\nMonitored for {duration_seconds} seconds\nCaptured {len(collected_logs)} log entries\n\n{content}"
    )]

# Export the MCP app for use with the standard MCP server
app = mcp.http_app()

if __name__ == "__main__":
    # Run the MCP server via stdio
    import asyncio
    asyncio.run(mcp.run_stdio_async())