# ✅ MCP Log Streaming Solution for nano-dlna - WORKING

This document describes the **working** MCP (Model Context Protocol) log streaming solution for the nano-dlna project.

## ✅ Status: FULLY FUNCTIONAL

**Tested and verified working!** Run `python test_mcp.py` to verify your setup.

## Overview

The solution provides:
- **FastMCP integration** with the existing FastAPI backend
- **Real-time log streaming** from backend Python logs, frontend React logs, and database operations  
- **Log aggregation service** that pipes all logs into Claude conversations
- **WebSocket and SSE streaming** for real-time log monitoring
- **Comprehensive filtering and search** capabilities

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Backend Logs  │    │   Frontend Logs  │    │ Database Logs   │
│ (dashboard_run, │    │  (React console) │    │ (SQL queries)   │
│    errors.log)  │    │                  │    │                 │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Log Aggregation       │
                    │      Service            │
                    │  - File monitoring      │
                    │  - Event collection     │
                    │  - Buffer management    │
                    └────────────┬─────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
     ┌────▼────┐          ┌─────▼─────┐          ┌─────▼─────┐
     │   MCP   │          │ WebSocket │          │    REST   │
     │ Server  │          │ Streaming │          │    API    │
     │ (Tools) │          │           │          │ (Export)  │
     └─────────┘          └───────────┘          └───────────┘
          │                      │                      │
     ┌────▼────┐          ┌─────▼─────┐          ┌─────▼─────┐
     │ Claude  │          │ Frontend  │          │   Admin   │
     │ (Debug) │          │Log Viewer │          │  Tools    │
     └─────────┘          └───────────┘          └───────────┘
```

## Files Created

### Backend Components

1. **`web/backend/mcp_server.py`** - FastMCP server with log streaming tools
2. **`web/backend/log_aggregation_service.py`** - Central log aggregation service
3. **`web/backend/routers/log_router.py`** - FastAPI router for log endpoints

### Frontend Components

4. **`web/frontend/src/services/logService.js`** - Frontend log collection service
5. **`web/frontend/src/hooks/useLogStreaming.js`** - React hooks for log streaming
6. **`web/frontend/src/pages/LogViewer.js`** - Log viewer component
7. **`web/frontend/src/pages/LogViewer.css`** - Styles for log viewer

### Configuration

8. **`mcp-config.json`** - MCP server configuration for Claude
9. **`run_mcp_server.py`** - Startup script for MCP server

## Setup Instructions

### 1. Install Dependencies

```bash
# Backend dependencies
cd web/backend
pip install -r requirements.txt

# Frontend dependencies (if needed)
cd ../frontend
npm install
```

### 2. Start the Backend with Log Aggregation

The log aggregation service is automatically started when you run the FastAPI backend:

```bash
cd web/backend
python main.py
```

The service will:
- Monitor log files for changes
- Collect frontend logs via API
- Track database operations
- Provide WebSocket streaming

### 3. Configure MCP for Claude

Add the MCP server to your Claude configuration:

```json
{
  "mcpServers": {
    "nano-dlna-logs": {
      "command": "python",
      "args": ["/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/run_mcp_server.py"],
      "env": {
        "PYTHONPATH": "/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna"
      }
    }
  }
}
```

Or use the provided config file: `/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/mcp-config.json`

### 4. Start the MCP Server

```bash
python run_mcp_server.py
```

## Available MCP Tools

### 1. `get_backend_logs`
Get backend Python logs from log files.

**Parameters:**
- `lines` (int): Number of lines to retrieve (default: 100)
- `log_type` (str): Type of log file ('dashboard', 'errors', 'root_dashboard', 'root_errors')

**Example:**
```python
# Get last 50 lines from dashboard logs
get_backend_logs(lines=50, log_type="dashboard")
```

### 2. `get_frontend_logs`
Get frontend React console logs.

**Parameters:**
- `limit` (int): Maximum number of log entries (default: 50)

### 3. `get_database_logs`
Get database operation logs.

**Parameters:**
- `limit` (int): Maximum number of log entries (default: 50)

### 4. `get_aggregated_logs`
Get filtered logs from all sources.

**Parameters:**
- `sources` (list): Filter by sources ['backend', 'frontend', 'database']
- `levels` (list): Filter by levels ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
- `minutes_back` (int): Time range in minutes (default: 60)
- `limit` (int): Maximum entries (default: 200)

**Example:**
```python
# Get error logs from all sources in last 30 minutes
get_aggregated_logs(levels=["ERROR", "CRITICAL"], minutes_back=30)
```

### 5. `search_logs`
Search through logs for specific patterns.

**Parameters:**
- `query` (str): Search term
- `sources` (list): Sources to search (optional)
- `case_sensitive` (bool): Case sensitivity (default: false)
- `limit` (int): Max results (default: 100)

**Example:**
```python
# Search for database errors
search_logs(query="database error", case_sensitive=False)
```

### 6. `tail_logs_realtime`
Monitor logs in real-time.

**Parameters:**
- `sources` (list): Sources to monitor (optional)
- `levels` (list): Log levels to show (optional)
- `duration_seconds` (int): Monitoring duration (default: 30)

## API Endpoints

### REST API

- `GET /api/logs/` - Get filtered logs
- `GET /api/logs/sources` - Get available log sources
- `GET /api/logs/levels` - Get available log levels
- `GET /api/logs/stats` - Get logging statistics
- `GET /api/logs/export` - Export logs (JSON, CSV, TXT)
- `POST /api/logs/frontend` - Submit frontend logs
- `GET /api/logs/health` - Health check

### WebSocket

- `WS /api/logs/ws` - Real-time log streaming

### Server-Sent Events

- `GET /api/logs/stream` - SSE log streaming

## Usage Examples

### Debugging with Claude

1. **Quick Error Check:**
```
Get recent errors from all sources
```
Claude will use: `get_aggregated_logs(levels=["ERROR", "CRITICAL"], minutes_back=15)`

2. **Database Issues:**
```
Show me database logs with any errors
```
Claude will use: `get_database_logs()` + `search_logs(query="error")`

3. **Frontend Problems:**
```
What frontend errors occurred in the last hour?
```
Claude will use: `get_frontend_logs()` + filtering

4. **Real-time Monitoring:**
```
Monitor logs for the next 60 seconds while I test this feature
```
Claude will use: `tail_logs_realtime(duration_seconds=60)`

### Frontend Log Viewer

Access the log viewer at: `http://localhost:3000/logs` (when React app is running)

Features:
- Real-time log streaming via WebSocket
- Historical log fetching
- Filtering by source, level, and search terms
- Export functionality
- Auto-scroll and timestamp display options

## Integration with Existing Code

### Database Logging

Database operations are automatically logged when using the existing database service. No additional code changes needed.

### Frontend Logging

The frontend service automatically captures:
- Console logs (log, warn, error, info, debug)
- Unhandled errors and promise rejections
- User interactions (when explicitly logged)
- API calls (when using the enhanced HTTP client)

### Backend Logging

All existing backend logs are automatically monitored from the log files.

## Troubleshooting

### MCP Server Issues

1. **Server won't start:**
   - Check Python path in configuration
   - Ensure all dependencies are installed
   - Check log files for errors

2. **Tools not available in Claude:**
   - Verify MCP configuration is correct
   - Restart Claude after configuration changes
   - Check MCP server logs for connection issues

### Log Aggregation Issues

1. **No logs appearing:**
   - Check if backend is running
   - Verify log file paths exist
   - Check WebSocket connections

2. **Frontend logs missing:**
   - Ensure frontend logService is initialized
   - Check network connectivity to backend
   - Verify CORS configuration

### Performance Considerations

- Log buffer is limited to 50,000 entries
- File monitoring checks every 500ms
- WebSocket clients are automatically cleaned up
- Large log exports may take time

## Development

### Adding New Log Sources

1. Create a new collector class extending `LogCollector`
2. Implement log parsing and emission
3. Add collector to `setup_log_collectors()`
4. Update MCP tools if needed

### Adding New MCP Tools

1. Add tool function to `mcp_server.py`
2. Use `@mcp.tool()` decorator
3. Update `mcp-config.json`
4. Test with Claude

## Security Notes

- Log data may contain sensitive information
- WebSocket connections are not authenticated
- File access is limited to configured log directories
- Consider adding authentication for production use

## Future Enhancements

- Log retention policies
- Log compression and archival
- Authentication and authorization
- Real-time alerting
- Log analytics and dashboards
- Integration with external log management systems