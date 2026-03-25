# nano-dlna

`nano-dlna` is a local media control and projection workspace built around a FastAPI backend, a React dashboard, legacy DLNA playback/runtime code, and newer discovery/projection tooling.

This README is based on the current code layout and entry points in this repo. It does not assume the older product shape is still fully accurate.

## What Is In This Repo

The repo currently contains several related systems:

- a legacy DLNA device runtime centered on `web/backend/core/device_manager.py`
- a FastAPI backend in `web/backend/main.py`
- a React dashboard in `web/frontend`
- a newer discovery-v2 subsystem in `web/backend/discovery`
- overlay/projection tooling and overlay-to-DLNA cast support
- renderer and projection-mapping pages/services
- structured-lighting capture/decode/calibration workflows
- the original `nanodlna` CLI package in `nanodlna/`

The current runtime is transitional: the legacy `DeviceManager` loop is still active, while discovery-v2 and newer subsystems are also live.

## Main Operator Surfaces

The dashboard routes in `web/frontend/src/App.js` currently expose:

- `/` dashboard
- `/devices` device list and discovery controls
- `/devices/:id` device detail
- `/videos` video library and uploads
- `/settings` config/settings
- `/renderer` renderer service pages
- `/projection` projection mapping
- `/mappings` mapping scenes
- `/overlay` overlay projection and cast control
- `/streaming` streaming diagnostics
- `/structured-lighting` structured-lighting sessions, decode, review, export
- `/depth` depth-processing tools
- `/projection-animation` projection animation tools

## Runtime Shape

The backend currently starts these major pieces from `web/backend/main.py`:

- FastAPI routers under `/api`
- the legacy singleton `DeviceManager`
- database initialization
- streaming services
- overlay cast service integration
- renderer service integration
- structured-lighting routes
- discovery-v2 routes under `/api/v2/discovery`
- a migration bridge between legacy discovery and discovery-v2

The important architectural reality is:

- legacy device discovery/playback state still matters
- discovery-v2 is present but not yet the only control plane
- frontend pages consume both legacy `/api/devices` and newer `/api/v2/discovery/*` data

## Quick Start

### 1. Prepare environment

Copy one of the checked-in env templates to `.env` and adjust paths if needed:

```bash
cp .env.dev-laptop.example .env
```

or

```bash
cp .env.mac-mini.example .env
```

Important environment values are loaded by `scripts/common_env.sh`:

- `NANODLNA_HOST`
- `NANODLNA_BACKEND_PORT`
- `NANODLNA_FRONTEND_PORT`
- `NANODLNA_FRONTEND_ENABLED`
- `NANODLNA_CONFIG_FILE`
- `NANODLNA_DB_PATH`
- `NANODLNA_INSTALL_PLAYWRIGHT`

### 2. Start the dashboard

```bash
./run_dashboard.sh
```

What this script does today:

- stops any existing dashboard processes
- cleans the database video entries
- imports videos from the selected config file
- starts backend and frontend via `web/run_direct.sh`
- waits for backend health
- POSTs `/api/devices/load-config` with the selected config file

Default URLs:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`

### 3. Stop the dashboard

```bash
./stop_dashboard.sh
```

## Direct Web Start

If you want to run the web app without the higher-level wrapper:

```bash
cd web
./run_direct.sh
```

This path:

- creates a venv if needed
- installs backend requirements
- optionally installs Playwright Chromium if `NANODLNA_INSTALL_PLAYWRIGHT=1`
- starts the FastAPI backend
- installs frontend npm dependencies
- starts the React dev server if `NANODLNA_FRONTEND_ENABLED=1`

Stop it with:

```bash
cd web
./stop_direct.sh
```

## CLI

The original CLI still exists under `nanodlna/cli.py`.

Typical usage:

```bash
nanodlna list
nanodlna play video.mp4 -q "TV"
nanodlna play video.mp4 -d "http://192.168.1.13:1082/"
nanodlna seek -q "TV" "00:17:25"
```

The CLI and the dashboard are related but not identical runtime paths. The web stack adds database-backed state, newer discovery services, projection tooling, and operator workflows that do not exist in the original CLI package.

## Config Files

Device/video bootstrap config is typically provided through:

- `my_device_config.json`
- `web/backend/my_device_config.json`
- `NANODLNA_CONFIG_FILE`
- `NANODLNA_CONFIG_FILES`

`run_dashboard.sh` defaults to `my_device_config.json` unless overridden.

These config files are used to seed:

- persisted device rows
- video mappings
- auto-play and related runtime behavior

## Key Backend APIs

The backend currently exposes several API groups:

- `/api/devices`
  - legacy device CRUD, discovery, playback control, discovery pause/resume/status
- `/api/videos`
  - video library management
- `/api/streaming`
  - streaming diagnostics/session views
- `/api/renderer`
  - renderer service routes
- `/api/overlay`
  - overlay config and overlay cast routes
- `/api/projection`
  - projection window/mapping routes
- `/api/mappings`
  - mapping scene routes
- `/api/media-library`
  - media library routes
- `/api/structured-lighting`
  - session, capture, decode, review, calibration, export routes
- `/api/logs`
  - log streaming routes
- `/api/v2/discovery`
  - newer unified discovery/cast routes

For the exact current route set, use:

```bash
open http://localhost:8000/docs
```

or inspect:

- `web/backend/main.py`
- `web/backend/routers/`
- `web/backend/api/discovery_router.py`

## Overlay, Projection, And Renderer Features

This repo is no longer just “play a file to a TV”.

Current code supports:

- overlay configuration persistence
- overlay projection pages
- backend-managed overlay cast sessions
- discovery-backed cast target selection
- projection mapping pages and mapping scenes
- renderer service pages
- streaming diagnostics for both media and overlay sessions

The overlay cast path depends on:

- Playwright/Chromium
- FFmpeg
- discovery/cast integration

If you use overlay casting, ensure those local dependencies exist on the host machine.

## Structured Lighting

Structured lighting is now a first-class subsystem in this repo.

The backend and frontend support:

- session creation and status
- Gray-code pattern planning
- capture upload workflow
- a host-side worker at `web/backend/structured_lighting_worker.py`
- decode artifacts
- artifact review
- operator accept/recapture workflow
- calibration/export outputs

The operator page is:

- `/structured-lighting`

The worker is intended to run on the host connected to the projector/camera.

## Current Architecture Caveat

The codebase is in the middle of a migration.

Today:

- legacy discovery/playback still runs through `DeviceManager`
- discovery-v2 exists in parallel
- frontend pages already consume both systems
- some APIs are newer and service-oriented, others still depend on blended legacy state

If you are changing runtime behavior, inspect the code before assuming one single source of truth.

Good starting files:

- `web/backend/main.py`
- `web/backend/core/device_manager.py`
- `web/backend/services/device_service.py`
- `web/backend/discovery/discovery_manager.py`
- `web/backend/discovery/migration.py`
- `web/backend/services/overlay_cast_service.py`
- `web/backend/services/structured_lighting_service.py`

## Development Notes

### Backend tests

```bash
pytest
```

The pytest configuration lives in `pyproject.toml` and currently includes backend test paths under `web/backend/tests_backend`.

### Frontend

```bash
cd web/frontend
npm install
npm start
```

Other frontend scripts:

```bash
npm test
npm run build
```

### Database and media helpers

Common repo scripts include:

```bash
python clean_videos.py
python add_config_videos.py
python scan_videos.py --directory "/path/to/videos" --recursive
python fix_device.py --device "DeviceName"
```

## macOS Service Mode

For an always-on macOS install:

```bash
./service/install_launchd.sh
```

This renders and installs launch agents based on the current `.env` values and service label.

Useful commands:

```bash
launchctl kickstart -k gui/$UID/com.nanodlna.dashboard
launchctl print gui/$UID/com.nanodlna.dashboard
tail -f logs/backend.stderr.log
tail -f logs/frontend.stderr.log
```

## Logs

Current startup scripts write logs under `logs/`, including:

- `logs/backend.stdout.log`
- `logs/backend.stderr.log`
- `logs/frontend.stdout.log`
- `logs/frontend.stderr.log`
- `logs/dashboard_run.log`

There is also a log streaming API and UI surface under `/api/logs`.

## Where To Look Next

If you are working on specific areas, start here:

- legacy playback/discovery runtime:
  - `web/backend/core/device_manager.py`
- device API/read models:
  - `web/backend/services/device_service.py`
- unified discovery:
  - `web/backend/discovery/`
- overlay cast runtime:
  - `web/backend/services/overlay_cast_service.py`
- structured lighting:
  - `web/backend/services/structured_lighting_service.py`
  - `web/backend/structured_lighting_worker.py`
- frontend pages:
  - `web/frontend/src/App.js`
  - `web/frontend/src/pages/`

## Status

This repo is active and evolving, but the architecture is not fully unified yet. Treat the code as the source of truth, especially for runtime ownership and control flow.
