# WallDisplay

`WallDisplay` is a local media control and projection workspace built around the original `nanodlna` CLI. A FastAPI backend discovers and controls DLNA TVs, AirPlay receivers, and overlay targets on the LAN. A React dashboard and an Expo mobile app provide operator surfaces.

## What Is In This Repo

| Component | Location | Description |
|-----------|----------|-------------|
| FastAPI backend | `web/backend/` | API server + device control + media management |
| React dashboard | `web/frontend/` | MUI-based web UI |
| Expo mobile app | `mobile-app/` | React Native cross-platform app (in progress) |
| CLI | `nanodlna/` | Original command-line DLNA client |
| Discovery v2 | `web/backend/discovery/` | Unified discovery subsystem (DLNA, AirPlay, Overlay backends) |
| Overlay casting | `web/backend/services/overlay_cast_service.py` | Playwright + CDP + FFmpeg pipeline |
| Renderer | `web/backend/core/renderer_service/` | Scene rendering + DLNA/AirPlay delivery |
| Structured lighting | `web/backend/services/structured_lighting_service.py` | Calibration sessions, capture, decode, review |
| Migration bridge | `web/backend/discovery/migration.py` | Bridges legacy DeviceManager ↔ discovery-v2 |

The runtime is transitional: the legacy `DeviceManager` loop is still active by default while discovery-v2 and newer subsystems run in parallel.

## Operator Surfaces

### Web Dashboard Routes

`web/frontend/src/App.js` exposes:

| Route | Page |
|-------|------|
| `/` | Dashboard |
| `/devices` | Device list and discovery controls |
| `/devices/:id` | Device detail |
| `/devices/:id/play` | Play video on device |
| `/devices/discover` | Discovery trigger |
| `/videos` | Video library and uploads |
| `/videos/:id` | Video detail |
| `/videos/:id/play` | Play on selected device |
| `/videos/add` | Add videos |
| `/videos/scan` | Scan directories |
| `/photos` | Photo library |
| `/settings` | Config and settings |
| `/settings/load-config` | Load device config |
| `/renderer` | Renderer service |
| `/depth` | Depth processing tools |
| `/projection` | Projection mapping |
| `/mappings` | Mapping scenes |
| `/overlay` | Overlay projection and cast control |
| `/streaming` | Streaming diagnostics |
| `/structured-lighting` | Structured-lighting sessions, decode, review, export |
| `/scene-control` | Scene control presets |
| `/projection-animation` | Projection animation tools |

### Mobile App Screens

`mobile-app/` is an Expo React Native rewrite in progress. 10 screens:

| Screen | Purpose |
|--------|---------|
| OverviewScreen | Backend health, device count, streaming analytics |
| DevicesScreen | Device inventory, discovery, control modes |
| MediaScreen | Video/photo/directory/list/channel inventory |
| OperationsScreen | Streaming, renderer, overlay, mapping, projection workflows |
| OverlayProjectionScreen | Overlay cast control |
| ProjectionAnimationScreen | Projection animation lists |
| StructuredLightingScreen | Calibration sessions |
| DepthProcessingScreen | Depth map tools |
| SettingsScreen | Backend URL config, connection test |
| LogsScreen | Backend log viewer |

The mobile app runs in **two modes**:

- **local** (default) — fully offline using simulated data. No backend needed. Actions that require a backend are recorded as deferred features.
- **remote** — connects to a real FastAPI backend via configurable base URL.

The `ControlPlaneClient` interface (`mobile-app/src/control-plane/client.ts`) abstracts both modes behind ~70 methods.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENTS                             │
│                                                             │
│  React Dashboard    Expo Mobile App     CLI (nanodlna)      │
│  (web/frontend/)    (mobile-app/)       (nanodlna/cli.py)   │
│  MUI + axios        local/remote modes  direct DLNA         │
└────────┬───────────────────┬──────────────────┬─────────────┘
         │ REST API          │ REST API         │ SSDP/SOAP
         ▼                   ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                           │
│                  web/backend/main.py                         │
│                                                             │
│  Middleware: projector_redirect → CORS → GZip               │
│                                                             │
│  16 API Routers under /api/*                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Service Layer (AppRuntime wires everything)          │   │
│  │                                                       │   │
│  │  DeviceManager (legacy)     DiscoveryManager (v2)    │   │
│  │  ├── DeviceInventoryService ├── DLNABackend           │   │
│  │  ├── RuntimeRegistryService ├── AirPlayBackend        │   │
│  │  ├── PlaybackOrchestrator   └── OverlayBackend        │   │
│  │  ├── PlaybackMonitoringService                        │   │
│  │  └── DiscoveryCoordinator                             │   │
│  │                                                       │   │
│  │  OverlayCastService  (Playwright+CDP+FFmpeg pipeline) │   │
│  │  RendererService     (scene render → DLNA/AirPlay)    │   │
│  │  StreamingService    (HTTP file server for DLNA)      │   │
│  │  StructuredLightingService (calibration workflow)     │   │
│  │  ProjectionService   (mapping configs + zones)        │   │
│  │  DiscoveryMigrationAdapter (legacy ↔ v2 bridge)       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  SQLite Database (SQLAlchemy ORM, 12 tables)                │
│  External: Playwright/Chrome, FFmpeg, Pillow/NumPy          │
└─────────────────────────────────────────────────────────────┘
         │
         │ Network protocols
         ▼
┌─────────────────────────────────────────────────────────────┐
│                     LAN DEVICES                             │
│                                                             │
│  DLNA TVs        ← SSDP discovery + SOAP AVTransport        │
│  AirPlay devices  ← mDNS/Bonjour + AirPlay casting          │
│  Overlay targets  ← HTTP live stream (MP4 via FFmpeg relay) │
└─────────────────────────────────────────────────────────────┘
```

## Key Workflows

### Device Discovery → Playback

1. Frontend calls `POST /api/devices/discover`
2. `DeviceDiscoveryService` → `DiscoveryCoordinator` → SSDP broadcast
3. DLNA devices respond with location XML → parsed into `DeviceModel`
4. Database upserts into `devices` table
5. User selects device + video → `POST /api/devices/{id}/play`
6. `PlaybackOrchestrator` resolves video path → starts HTTP streaming server → sends DLNA SOAP `SetAVTransportURI` + `Play`
7. `PlaybackMonitoringService` polls playback state every 30s

### Overlay Casting (Web → DLNA)

1. Frontend calls `POST /api/overlay/cast`
2. `OverlayCastService` launches Playwright Chromium headless
3. Navigates to overlay URL → starts CDP screencast (frame capture as base64 JPEG)
4. Spawns FFmpeg subprocess (raw frames → MP4 stream)
5. `FanoutRelayState` provides thread-safe pub/sub for stream chunks
6. HTTP relay serves `GET /live.mp4` → chunks to clients
7. Target DLNA device receives the relay URL via SOAP → plays live stream

### Structured Lighting Calibration

1. Create calibration session → Gray-code pattern sequence planned
2. Host-side worker (`structured_lighting_worker.py`) captures camera frames per pattern
3. Each pattern: send to projector via DLNA → settle → capture → upload
4. Decode Gray-code patterns → depth/geometry map
5. Operator reviews artifacts (accept/recapture workflow)
6. Calibration export → mapping scene for projection use

## Quick Start

### Hardware-free verification

```bash
python3 scripts/offline_demo_smoke.py
python3 -m compileall nanodlna web/backend
npm --prefix mobile-app install
npm --prefix mobile-app run typecheck
```

The offline smoke summarizes the checked-in dashboard/backend/static demo
surface. The compile check catches Python syntax/import-shape regressions
without touching DLNA, AirPlay, cameras, Chrome, or FFmpeg devices. The Expo
mobile typecheck validates the local/offline control-plane shell. Full
dashboard, overlay, structured-lighting, and casting demos require the intended
LAN devices and native tools to be present.

### 1. Prepare environment

Copy an env template to `.env` and adjust paths:

```bash
cp .env.example .env
```

All env vars and defaults are defined in `scripts/common_env.sh`.

### 2. Start the dashboard

```bash
./run_dashboard.sh
```

Optionally pass a config file:

```bash
./run_dashboard.sh path/to/my_config.json
```

What this does:

- stops any existing dashboard processes
- cleans database video entries
- imports videos from the selected config file
- starts backend and frontend via `web/run_direct.sh`
  - creates Python venv if needed
  - installs pip requirements
  - optionally installs Playwright Chromium
  - starts uvicorn backend
  - starts React dev server (if `NANODLNA_FRONTEND_ENABLED=1`)
  - runs a watchdog loop that restarts the stack if backend or frontend crashes
- waits for backend health check
- POSTs `/api/devices/load-config` with the selected config file

Default URLs:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`

### 3. Stop the dashboard

```bash
./stop_dashboard.sh
```

Or press Ctrl+C in the `run_dashboard.sh` terminal.

### 4. Direct web start (no DB reset or config import)

```bash
cd web
./run_direct.sh
```

Stop:

```bash
cd web
./stop_direct.sh
```

### 5. Mobile app

```bash
cd mobile-app
npm install
```

Local mode (offline, no backend):

```bash
npm start
```

Remote mode (needs running backend):

```bash
# iOS simulator
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api npm start

# Android emulator
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000/api npm start

# Physical device on same LAN
EXPO_PUBLIC_API_BASE_URL=http://<your-mac-ip>:8000/api npm start
```

TypeScript verification:

```bash
cd mobile-app
npm run typecheck
```

## Environment Variables

Loaded by `scripts/common_env.sh`, defaults shown:

| Variable | Default | Purpose |
|----------|---------|---------|
| `NANODLNA_HOST` | `0.0.0.0` | Backend bind host |
| `NANODLNA_BACKEND_PORT` | `8000` | Backend port |
| `NANODLNA_FRONTEND_PORT` | `3000` | Frontend dev server port |
| `NANODLNA_FRONTEND_ENABLED` | `1` | Start React dev server |
| `NANODLNA_CONFIG_FILE` | `my_device_config.json` | Device/video bootstrap config |
| `NANODLNA_DB_PATH` | `web/backend/nanodlna.db` | SQLite database path |
| `NANODLNA_INSTALL_PLAYWRIGHT` | `1` | Install Playwright Chromium on start |
| `NANODLNA_VENV_DIR` | `.venv` (root) or `web/backend/venv` | Python virtual environment |
| `NANODLNA_MEDIA_ROOT` | `$HOME/Movies` | Default media directory |
| `NANODLNA_LOG_DIR` | `logs/` | Log output directory |
| `NANODLNA_SERVICE_LABEL` | `com.nanodlna.dashboard` | launchd service label |
| `NANODLNA_SERVICE_RESTART_DELAY` | `5` | Seconds between service restarts |
| `NANODLNA_GIT_BRANCH` | `main` | Branch for auto-update |
| `NANODLNA_GIT_REMOTE` | `origin` | Remote for auto-update |
| `NANODLNA_GIT_AUTO_UPDATE` | `0` | Enable git auto-update in service mode |
| `NANODLNA_BACKEND_START_TIMEOUT` | `120` | Seconds to wait for backend health |
| `NANODLNA_DASHBOARD_START_TIMEOUT` | `180` | Seconds to wait for full dashboard |
| `NANODLNA_PORT_RELEASE_TIMEOUT` | `10` | Seconds to wait for port release |
| `NANODLNA_DISCOVERY_AUTHORITY` | `legacy` | `legacy` or `unified` — controls which discovery system is authoritative |

## Backend APIs

| Router | Prefix | Purpose |
|--------|--------|---------|
| device_router | `/api/devices` | Device CRUD, discovery, play/stop/pause/seek, control modes |
| video_router | `/api/videos` | Video library, upload, scan, stream |
| photo_router | `/api/photos` | Photo library |
| photo_list_router | `/photo-lists` | Photo playlists |
| streaming_router | `/api/streaming` | Session analytics, health |
| renderer_router | `/api/renderer` | Scene rendering, projector control, AirPlay discovery |
| overlay_router | `/api/overlay` | Overlay configs, cast sessions, projector redirect |
| projection_router | `/api/projection` | Mapping configs, zones, animations |
| mapping_router | `/api/mappings` | Mapping scenes, ranks, presets, masks |
| media_library_router | `/api/media-library` | Directories, lists, channels |
| structured_lighting_router | `/api/structured-lighting` | Calibration sessions, capture, decode, review |
| depth_router | `/api/depth` | Depth maps, segmentation, masks |
| diagnostics_router | `/api/diagnostics` | Service health, incidents |
| log_router | `/api/logs` | Log streaming |
| widget_router | `/api/widgets` | Widget data |
| discovery_router | `/api/v2/discovery` | Unified discovery v2: devices, backends, configs, casting |

For the exact current route set, see the interactive docs at `http://localhost:8000/docs` or inspect `web/backend/routers/` and `web/backend/api/discovery_router.py`.

## Config Files

Device/video bootstrap config:

```bash
./run_dashboard.sh                        # defaults to my_device_config.json
./run_dashboard.sh path/to/config.json     # override
```

Set via env:

```bash
export NANODLNA_CONFIG_FILE=my_device_config.json
```

Config files seed persisted device rows, video mappings, and auto-play behavior.

## CLI

```bash
nanodlna list
nanodlna play video.mp4 -q "TV"
nanodlna play video.mp4 -d "http://192.168.1.13:1082/"
nanodlna seek -q "TV" "00:17:25"
```

The CLI makes direct DLNA calls. It does not use the backend, database, or discovery-v2 subsystems.

## macOS Service Mode

For an always-on macOS install:

```bash
./service/install_launchd.sh
```

Renders launchd plist templates with current env vars and installs to `~/Library/LaunchAgents/`. Includes a separate git-updater agent for auto-pulling updates when `NANODLNA_GIT_AUTO_UPDATE=1`.

Manage:

```bash
launchctl kickstart -k gui/$UID/com.nanodlna.dashboard
launchctl print gui/$UID/com.nanodlna.dashboard
tail -f logs/backend.stderr.log
tail -f logs/frontend.stderr.log
```

## Database

SQLite via SQLAlchemy ORM. Default location: `web/backend/nanodlna.db`.

Key tables: `devices`, `videos`, `photos`, `overlay_configs`, `mapping_scenes`, `scene_control_presets`, `scene_rank`, `media_directories`, `media_lists`, `media_channels`, `photo_lists`, `projection_configs`.

## Logs

Startup scripts write to `logs/`:

- `logs/backend.stdout.log`
- `logs/backend.stderr.log`
- `logs/frontend.stdout.log`
- `logs/frontend.stderr.log`
- `logs/dashboard_run.log`

Log streaming API and UI: `/api/logs`.

## Database and Media Helpers

```bash
python clean_videos.py <db_path>
python add_config_videos.py <config_path> <db_path>
python scan_videos.py --directory "/path/to/videos" --recursive
python fix_device.py --device "DeviceName"
```

## Development

### Backend tests

```bash
./run_tests.sh
```

Repository wrapper for the legacy Python test suite. It expects the backend
virtualenv at `web/backend/venv/`.

For targeted backend work:

```bash
cd web/backend
venv/bin/python -m pytest tests_backend
```

### Backend and test caveats

- Some backend modules still use cwd-sensitive absolute imports such as
  `database`, `routers`, `services`, and `core`. Direct backend commands and ad
  hoc pytest runs are safest from `web/backend/`, or with `PYTHONPATH`
  including both the repository root and `web/backend/`.
- Importing `web.backend.main` pulls in optional feature routers as part of app
  startup. Missing optional packages such as `beautifulsoup4`, `screeninfo`,
  `zeroconf`, or `scikit-learn` can break broad imports and test collection
  even when unrelated features are under test.

### Frontend

```bash
cd web/frontend
npm install
npm start        # dev server
npm test         # tests
npm run build    # production build
```

### Mobile

```bash
cd mobile-app
npm install
npm test           # Node-based contract/controller tests
npm run typecheck  # TypeScript verification
npm start          # Expo dev server
```

### Backend hot-reload

```bash
cd web/backend
python run.py --reload --debug
```

## Architecture Notes

### Legacy vs Unified Discovery

The codebase has two discovery systems running in parallel:

- **Legacy**: `DeviceManager` + `DiscoveryCoordinator` — SSDP-only DLNA discovery
- **Unified (v2)**: `DiscoveryManager` with pluggable backends (DLNA, AirPlay, Overlay)

`NANODLNA_DISCOVERY_AUTHORITY` controls which is authoritative:
- `legacy` (default) — legacy DeviceManager leads, `DiscoveryMigrationAdapter` syncs to v2 in background
- `unified` — DiscoveryManager leads, legacy discovery loop is skipped

The `DiscoveryMigrationAdapter` (`web/backend/discovery/migration.py`) keeps both systems in sync during the transition.

### AppRuntime

`services/app_runtime.py` is the central service container. Created at startup, accessed via `get_app_runtime()`. All routers depend on it to build service instances.

### Where To Look

| Area | Start here |
|------|-----------|
| Backend entry | `web/backend/main.py` |
| Backend run script | `web/backend/run.py` |
| Legacy device runtime | `web/backend/core/device_manager.py` |
| Device API/read models | `web/backend/services/device_service.py` |
| Unified discovery | `web/backend/discovery/` |
| Discovery migration | `web/backend/discovery/migration.py` |
| Overlay cast runtime | `web/backend/services/overlay_cast_service.py` |
| Structured lighting | `web/backend/services/structured_lighting_service.py` |
| Renderer service | `web/backend/core/renderer_service/service.py` |
| Streaming service | `web/backend/core/streaming_service.py` |
| Service wiring | `web/backend/services/app_runtime.py` |
| Frontend pages | `web/frontend/src/App.js`, `web/frontend/src/pages/` |
| Frontend API client | `web/frontend/src/services/api.js` |
| Mobile control plane | `mobile-app/src/control-plane/client.ts` |
| Mobile screens | `mobile-app/src/screens/` |

## Current Test Status

Automated tests are split across:

- `tests/` — legacy Python tests and older integration coverage
- `web/backend/tests_backend/` — backend service/runtime tests
- `mobile-app/tests/` — mobile control-plane and remote-contract tests

Current reality:

- The healthiest automated lane today is the mobile app test suite. The local
  and remote control-plane tests under `mobile-app/tests/` pass in the current
  repo.
- Some older Python API/router tests had drifted far enough from the live
  backend app shape, routes, and response schemas that they were removed during
  cleanup rather than treated as trusted contract coverage.
- Most backend verification is service-level and heavily mocked. Full startup,
  hardware-device, overlay-cast, and structured-lighting hardware workflows are
  not comprehensively end-to-end covered.

## Transition / Technical Debt Notes

- Discovery/runtime ownership is still transitional. `AppRuntime`, unified
  discovery, and compatibility bridges coexist with older
  `DeviceManager`-shaped code paths.
- Expect fallback logic and legacy compatibility seams in playback, discovery,
  and device-state flows until that migration is finished.

## Status

This repo is active and evolving. The architecture is not fully unified yet — treat the code as the source of truth, especially for runtime ownership and control flow.
