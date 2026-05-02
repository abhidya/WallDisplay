# nano-dlna Web Dashboard

The web operator surface for nano-dlna — a FastAPI backend serving REST APIs and a React frontend for device discovery, media management, overlay casting, projection mapping, and structured-lighting calibration.

For the full architecture overview, environment variables, and all start modes, see the [root README](../README.md).

## Quick Start

```bash
# From repo root — full dashboard with DB reset and config import
./run_dashboard.sh

# Or from this directory — backend + frontend only, no DB reset
./run_direct.sh
```

Stop:

```bash
# From repo root
./stop_dashboard.sh

# Or from this directory
./stop_direct.sh
```

Default URLs:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Directory Structure

- `backend/` — FastAPI backend (routers, services, models, discovery, core runtime)
- `frontend/` — React dashboard (MUI pages, API client, hooks)
- `data/` — SQLite database (default: `backend/nanodlna.db`)
- `uploads/` — Uploaded media files

## Development

Backend only:

```bash
cd backend
python run.py --reload --debug
```

Frontend only:

```bash
cd frontend
npm install
npm start
```

Configuration is via environment variables — see `scripts/common_env.sh` and the [root README](../README.md) for the full list.
