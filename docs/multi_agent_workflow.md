# Multi-Agent Workflow for nano-dlna

## Overview

This document outlines the setup and workflow for running multiple AI agents concurrently on the nano-dlna project, enabling parallel development and testing without conflicts.

## Problem Statement

- **Single instance conflicts**: Default setup runs backend on port 8000, uses single SQLite database
- **Testing bottlenecks**: Agents can't test simultaneously without interfering
- **Branch management**: Need to work on different features/fixes in parallel

## Architecture Analysis

### Current Setup
- **Backend**: FastAPI (Python) on port 8000 (`web/backend/app.py`)
- **Frontend**: React on port 3000 (`web/frontend/`)
- **Database**: SQLite (`nanodlna.db`)
- **No Docker**: Currently using direct Python/Node execution

### Key Conflict Points
1. Port binding (backend: 8000, frontend: 3000)
2. Database file access (SQLite single file)
3. Static file paths and uploads directory
4. Session/cache conflicts

## Implementation Strategy

### Phase 1: Environment Variable Isolation (Immediate)

Create agent-specific configurations:

```bash
# Agent 1 - Feature Development
export AGENT_NAME=feature
export BACKEND_PORT=8001
export FRONTEND_PORT=3001
export DATABASE_URL=sqlite:///nano_dlna_feature.db
export UPLOAD_DIR=./uploads_feature

# Agent 2 - Bug Fixes
export AGENT_NAME=bugfix
export BACKEND_PORT=8002
export FRONTEND_PORT=3002
export DATABASE_URL=sqlite:///nano_dlna_bugfix.db
export UPLOAD_DIR=./uploads_bugfix

# Agent 3 - Testing
export AGENT_NAME=testing
export BACKEND_PORT=8003
export FRONTEND_PORT=3003
export DATABASE_URL=sqlite:///nano_dlna_testing.db
export UPLOAD_DIR=./uploads_testing
```

### Phase 2: Git Worktrees (When Needed)

Setup for branch isolation:

```bash
# Create worktree structure
mkdir -p ../nano-dlna-worktrees
git worktree add ../nano-dlna-worktrees/feature feature-streaming
git worktree add ../nano-dlna-worktrees/bugfix bugfix-dlna-errors
git worktree add ../nano-dlna-worktrees/testing test-infrastructure
```

### Phase 3: Docker Compose (Future)

```yaml
version: '3.8'
services:
  backend-agent1:
    build: ./web/backend
    ports:
      - "8001:8000"
    environment:
      - DATABASE_URL=sqlite:///data/agent1.db
    volumes:
      - ./data/agent1:/data

  backend-agent2:
    build: ./web/backend
    ports:
      - "8002:8000"
    environment:
      - DATABASE_URL=sqlite:///data/agent2.db
    volumes:
      - ./data/agent2:/data
```

## Quick Start Scripts

### 1. Create Agent Setup Script

```bash
#!/bin/bash
# setup_agent.sh
AGENT_ID=$1
BASE_PORT=$((8000 + AGENT_ID))

cat > .env.agent${AGENT_ID} << EOF
BACKEND_PORT=${BASE_PORT}
FRONTEND_PORT=$((3000 + AGENT_ID))
DATABASE_URL=sqlite:///nano_dlna_agent${AGENT_ID}.db
UPLOAD_DIR=./uploads_agent${AGENT_ID}
EOF

mkdir -p uploads_agent${AGENT_ID}
echo "Agent ${AGENT_ID} configured on port ${BASE_PORT}"
```

### 2. Start Agent Script

```bash
#!/bin/bash
# start_agent.sh
AGENT_ID=$1
source .env.agent${AGENT_ID}

# Start backend
cd web/backend
python app.py --port ${BACKEND_PORT} &

# Start frontend
cd ../frontend
REACT_APP_API_URL=http://localhost:${BACKEND_PORT} \
PORT=${FRONTEND_PORT} npm start &
```

### 3. Health Check Script

```bash
#!/bin/bash
# check_agents.sh
for i in 1 2 3; do
  PORT=$((8000 + i))
  if curl -s http://localhost:${PORT}/health > /dev/null; then
    echo "Agent $i (port $PORT): ✓ Running"
  else
    echo "Agent $i (port $PORT): ✗ Down"
  fi
done
```

## Testing Workflow

### Parallel Testing Example

```bash
# Agent 1: API Testing
cd /path/to/nano-dlna
source .env.agent1
pytest tests/test_api_live.py -v

# Agent 2: Frontend Testing  
cd /path/to/nano-dlna
source .env.agent2
cd web/frontend && npm test

# Agent 3: Integration Testing
cd /path/to/nano-dlna
source .env.agent3
pytest tests/integration/ -v
```

## Subagent Commands

### Basic Spawn Commands

```bash
# Spawn frontend agent
/user:spawn --task "Implement dashboard UI improvements in agent1 environment"

# Spawn backend agent
/user:spawn --task "Fix DLNA streaming issues using agent2 setup"

# Spawn test agent
/user:spawn --task "Create comprehensive test suite in agent3 environment"
```

### Advanced Coordination

```bash
# Parallel feature development
/user:spawn --task "Agent1: Implement video overlay feature" --think
/user:spawn --task "Agent2: Add depth processing API" --think
/user:spawn --task "Agent3: Create frontend components" --think
```

## Conflict Resolution

### Database Migrations
- Each agent maintains separate database
- Merge migrations carefully when combining work
- Use migration scripts to sync schema changes

### Configuration Management
- Base config: `config/base.json`
- Agent overrides: `config/agent1.json`
- Environment precedence: ENV > agent config > base config

### Port Management
- Backend: 8001-8010 reserved for agents
- Frontend: 3001-3010 reserved for agents
- Database: Separate files per agent

## Monitoring and Cleanup

### Active Agent Monitoring
```bash
# List all agent processes
ps aux | grep -E "(python.*app.py|node.*react)"

# Show port usage
lsof -i :8001-8010
```

### Cleanup Script
```bash
#!/bin/bash
# cleanup_agents.sh
# Kill all agent processes
pkill -f "python.*app.py.*agent"
pkill -f "react-scripts.*agent"

# Remove agent databases
rm -f nano_dlna_agent*.db

# Clean upload directories
rm -rf uploads_agent*
```

## Best Practices

1. **Resource Management**
   - Limit to 3-4 concurrent agents
   - Monitor memory usage
   - Use lightweight test data

2. **Code Synchronization**
   - Commit frequently
   - Use feature branches
   - Merge regularly to avoid conflicts

3. **Testing Strategy**
   - Unit tests: Any agent
   - Integration tests: Dedicated test agent
   - Performance tests: Isolated agent

4. **Communication**
   - Document changes in CLAUDE_PROGRESS.md
   - Use clear commit messages
   - Tag agent-specific work

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   lsof -i :PORT_NUMBER
   kill -9 PID
   ```

2. **Database locked**
   - Use separate database files
   - Implement connection pooling
   - Add retry logic

3. **Memory exhaustion**
   - Limit concurrent agents
   - Use process managers
   - Monitor with `htop`

## Future Enhancements

1. **Automated Orchestration**
   - PM2 for process management
   - Kubernetes for container orchestration
   - CI/CD integration

2. **Shared Services**
   - Redis for caching
   - PostgreSQL for better concurrency
   - Message queue for agent communication

3. **Monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - Centralized logging

## References

- Project structure: `/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/`
- Backend entry: `web/backend/app.py`
- Frontend entry: `web/frontend/src/index.js`
- Test suite: `tests/` and `web/backend/tests_backend/`
- Previous research: Task tool analysis, MCP documentation