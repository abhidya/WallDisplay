#!/usr/bin/env python3

import asyncio
import logging
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from collections import deque
import threading
import websockets
from pathlib import Path

# FastAPI imports for SSE and WebSocket
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

try:
    from logging_config import get_logger
except ImportError:
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger(__name__)

@dataclass
class LogEvent:
    """Structured log event"""
    timestamp: datetime
    level: str
    source: str
    logger_name: str
    message: str
    filename: str = "unknown"
    line_number: int = 0
    extra_data: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())

class LogCollector:
    """Base class for log collectors"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_running = False
        self.callbacks = []
    
    def add_callback(self, callback: Callable[[LogEvent], None]):
        self.callbacks.append(callback)
    
    async def emit_log(self, event: LogEvent):
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error in log callback: {e}")
    
    async def start(self):
        self.is_running = True
    
    async def stop(self):
        self.is_running = False

class FileLogCollector(LogCollector):
    """Collects logs from rotating log files"""
    
    def __init__(self, name: str, file_path: str, source_name: str):
        super().__init__(name)
        self.file_path = file_path
        self.source_name = source_name
        self.last_position = 0
        self.last_inode = None
    
    def parse_log_line(self, line: str) -> Optional[LogEvent]:
        """Parse a log line into a LogEvent"""
        if not line.strip():
            return None
        
        # Try to parse structured log format
        import re
        patterns = [
            # 2024-01-01 12:00:00 - module.name - INFO - message
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?) - ([^-]+) - (\w+) - (.+)',
            # 2024-01-01 12:00:00 - module.name - INFO - filename:line - message
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?) - ([^-]+) - (\w+) - ([^-]+) - (.+)',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                groups = match.groups()
                try:
                    # Parse timestamp
                    timestamp_str = groups[0].replace(',', '.')
                    timestamp = datetime.strptime(timestamp_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    
                    if len(groups) == 4:
                        logger_name, level, message = groups[1].strip(), groups[2].strip(), groups[3].strip()
                        filename, line_number = "unknown", 0
                    else:
                        logger_name, level, location, message = groups[1].strip(), groups[2].strip(), groups[3].strip(), groups[4].strip()
                        if ':' in location:
                            filename, line_str = location.split(':', 1)
                            line_number = int(line_str) if line_str.isdigit() else 0
                        else:
                            filename, line_number = location, 0
                    
                    return LogEvent(
                        timestamp=timestamp,
                        level=level,
                        source=self.source_name,
                        logger_name=logger_name,
                        message=message,
                        filename=filename,
                        line_number=line_number,
                        extra_data={'raw_line': line}
                    )
                except Exception as e:
                    logger.debug(f"Failed to parse structured log line: {e}")
        
        # Fallback: unstructured log
        return LogEvent(
            timestamp=datetime.now(),
            level="INFO",
            source=self.source_name,
            logger_name=self.source_name,
            message=line,
            extra_data={'raw_line': line, 'unstructured': True}
        )
    
    async def start(self):
        await super().start()
        
        # Start monitoring in background task
        asyncio.create_task(self._monitor_file())
    
    async def _monitor_file(self):
        """Monitor the log file for changes"""
        while self.is_running:
            try:
                if not os.path.exists(self.file_path):
                    await asyncio.sleep(1)
                    continue
                
                # Check if file was rotated
                stat = os.stat(self.file_path)
                current_inode = stat.st_ino
                
                if self.last_inode is not None and current_inode != self.last_inode:
                    # File was rotated, start from beginning
                    self.last_position = 0
                    logger.info(f"Log file rotated: {self.file_path}")
                
                self.last_inode = current_inode
                
                # Read new content
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(self.last_position)
                    
                    for line in f:
                        if line.strip():
                            event = self.parse_log_line(line.strip())
                            if event:
                                await self.emit_log(event)
                    
                    self.last_position = f.tell()
                
                await asyncio.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                logger.error(f"Error monitoring log file {self.file_path}: {e}")
                await asyncio.sleep(5)  # Wait longer on error

class DatabaseLogCollector(LogCollector):
    """Collects database operation logs"""
    
    def __init__(self, name: str = "database"):
        super().__init__(name)
    
    def log_query(self, query: str, params: List[Any] = None, duration: float = None, error: str = None):
        """Log a database query"""
        event = LogEvent(
            timestamp=datetime.now(),
            level="ERROR" if error else "INFO",
            source="database",
            logger_name="sqlalchemy",
            message=f"Query: {query[:200]}{'...' if len(query) > 200 else ''}",
            extra_data={
                'query': query,
                'params': params,
                'duration': duration,
                'error': error
            }
        )
        
        # Emit synchronously (will be handled by async callbacks)
        asyncio.create_task(self.emit_log(event))

class FrontendLogCollector(LogCollector):
    """Collects frontend logs sent via API"""
    
    def __init__(self, name: str = "frontend"):
        super().__init__(name)
    
    def log_frontend_event(self, log_data: Dict[str, Any]):
        """Process a frontend log event"""
        event = LogEvent(
            timestamp=datetime.fromtimestamp(log_data.get('timestamp', time.time())),
            level=log_data.get('level', 'INFO').upper(),
            source="frontend",
            logger_name=log_data.get('component', 'unknown'),
            message=log_data.get('message', ''),
            filename=log_data.get('filename', 'unknown'),
            line_number=log_data.get('line_number', 0),
            extra_data=log_data
        )
        
        asyncio.create_task(self.emit_log(event))

class LogAggregationService:
    """Central service that aggregates logs from multiple sources"""
    
    def __init__(self):
        self.collectors = {}
        self.log_buffer = deque(maxlen=50000)  # Keep last 50k entries
        self.active_streams = set()
        self.websocket_clients = set()
        self.is_running = False
        
        # Filters for log levels
        self.level_priority = {
            'DEBUG': 0,
            'INFO': 1,
            'WARNING': 2,
            'ERROR': 3,
            'CRITICAL': 4
        }
    
    def add_collector(self, collector: LogCollector):
        """Add a log collector"""
        self.collectors[collector.name] = collector
        collector.add_callback(self._handle_log_event)
        logger.info(f"Added log collector: {collector.name}")
    
    async def _handle_log_event(self, event: LogEvent):
        """Handle a log event from any collector"""
        # Add to buffer
        self.log_buffer.append(event)
        
        # Broadcast to active streams
        await self._broadcast_log_event(event)
    
    async def _broadcast_log_event(self, event: LogEvent):
        """Broadcast log event to all connected clients"""
        if not self.websocket_clients:
            return
        
        event_json = event.to_json()
        disconnected_clients = set()
        
        for client in self.websocket_clients:
            try:
                await client.send_text(event_json)
            except Exception as e:
                logger.debug(f"WebSocket client disconnected: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        self.websocket_clients -= disconnected_clients
    
    def get_logs(self, 
                 sources: List[str] = None,
                 levels: List[str] = None,
                 since: datetime = None,
                 limit: int = 1000,
                 search: str = None) -> List[Dict[str, Any]]:
        """Get filtered logs"""
        logs = list(self.log_buffer)
        
        # Apply filters
        if sources:
            logs = [log for log in logs if log.source in sources]
        
        if levels:
            logs = [log for log in logs if log.level in levels]
        
        if since:
            logs = [log for log in logs if log.timestamp >= since]
        
        if search:
            search_lower = search.lower()
            logs = [log for log in logs if 
                   search_lower in log.message.lower() or 
                   search_lower in log.logger_name.lower()]
        
        # Sort by timestamp (newest first)
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Limit results
        logs = logs[:limit]
        
        return [log.to_dict() for log in logs]
    
    async def start(self):
        """Start the aggregation service"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Starting log aggregation service")
        
        # Start all collectors
        for collector in self.collectors.values():
            await collector.start()
        
        logger.info(f"Started {len(self.collectors)} log collectors")
    
    async def stop(self):
        """Stop the aggregation service"""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Stopping log aggregation service")
        
        # Stop all collectors
        for collector in self.collectors.values():
            await collector.stop()
        
        # Disconnect all WebSocket clients
        for client in self.websocket_clients:
            try:
                await client.close()
            except:
                pass
        self.websocket_clients.clear()
    
    def add_websocket_client(self, websocket: WebSocket):
        """Add a WebSocket client for real-time log streaming"""
        self.websocket_clients.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.websocket_clients)}")
    
    def remove_websocket_client(self, websocket: WebSocket):
        """Remove a WebSocket client"""
        self.websocket_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.websocket_clients)}")
    
    async def stream_logs_sse(self, 
                             sources: List[str] = None,
                             levels: List[str] = None,
                             search: str = None):
        """Stream logs via Server-Sent Events"""
        async def event_generator():
            # Send initial batch of recent logs
            recent_logs = self.get_logs(sources=sources, levels=levels, search=search, limit=50)
            for log in reversed(recent_logs):  # Send oldest first
                yield {
                    "event": "log",
                    "data": json.dumps(log)
                }
            
            # Stream new logs
            last_timestamp = datetime.now()
            while True:
                await asyncio.sleep(1)  # Check every second
                
                new_logs = self.get_logs(
                    sources=sources, 
                    levels=levels, 
                    since=last_timestamp,
                    search=search,
                    limit=100
                )
                
                for log in reversed(new_logs):  # Send oldest first
                    yield {
                        "event": "log", 
                        "data": json.dumps(log)
                    }
                    last_timestamp = max(last_timestamp, datetime.fromisoformat(log['timestamp']))
        
        return EventSourceResponse(event_generator())

# Global instance
log_aggregation_service = LogAggregationService()

def get_log_aggregation_service() -> LogAggregationService:
    """Get the global log aggregation service instance"""
    return log_aggregation_service

# Convenience functions for external use
def setup_log_collectors():
    """Set up default log collectors"""
    # Backend log files
    backend_files = [
        ('/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/web/backend/dashboard_run.log', 'backend_dashboard'),
        ('/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/web/backend/errors.log', 'backend_errors'),
        ('/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/dashboard_run.log', 'root_dashboard'),
        ('/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/errors.log', 'root_errors'),
    ]
    
    for file_path, source_name in backend_files:
        if os.path.exists(os.path.dirname(file_path)):
            collector = FileLogCollector(f"file_{source_name}", file_path, source_name)
            log_aggregation_service.add_collector(collector)
    
    # Database collector
    db_collector = DatabaseLogCollector()
    log_aggregation_service.add_collector(db_collector)
    
    # Frontend collector
    frontend_collector = FrontendLogCollector()
    log_aggregation_service.add_collector(frontend_collector)
    
    logger.info("Log collectors set up successfully")

# Database logging integration
def log_database_operation(query: str, params: List[Any] = None, duration: float = None, error: str = None):
    """Log a database operation"""
    if 'database' in log_aggregation_service.collectors:
        collector = log_aggregation_service.collectors['database']
        collector.log_query(query, params, duration, error)

# Frontend logging integration
def log_frontend_event(log_data: Dict[str, Any]):
    """Log a frontend event"""
    if 'frontend' in log_aggregation_service.collectors:
        collector = log_aggregation_service.collectors['frontend']
        collector.log_frontend_event(log_data)