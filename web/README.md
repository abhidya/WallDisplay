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

## HDMI Projector Runtime

For a projector connected as a second monitor, run the backend in the logged-in user's desktop session. Windows background services, scheduled tasks that run without an interactive user, and Docker containers may not be able to enumerate displays or launch the kiosk browser on the projector. Prefer a user-session startup task or direct `run_direct.sh`/`run_dashboard.sh` startup for HDMI projection.

If the backend uses a non-default port, set `NANODLNA_SERVER_BASE_URL` so identify, structured-light, overlay, blank, and heartbeat pages point back to the correct API.

On Windows, the root `scripts/` directory includes logon-task helpers for user-session startup:

```powershell
powershell -ExecutionPolicy Bypass -File ..\scripts\register-walldisplay-task.ps1
schtasks /Run /TN WallDisplay
powershell -ExecutionPolicy Bypass -File ..\scripts\stop-walldisplay.ps1
```

Run `..\scripts\add-walldisplay-firewall-admin.ps1` once from Administrator PowerShell for LAN access. The helper launcher defaults to port `8088` and sets `NANODLNA_SERVER_BASE_URL` to the detected LAN URL.

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
