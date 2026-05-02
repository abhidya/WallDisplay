# Architecture Overview

This file is a compact companion to the root `README.md`. The README is the
canonical architecture and workflow overview; this page exists to highlight the
few structural facts worth keeping separate.

## Canonical entrypoints

- Top-level system overview: `README.md`
- Backend app entry: `web/backend/main.py`
- Backend service wiring: `web/backend/services/app_runtime.py`
- Unified discovery and migration: `web/backend/discovery/`
- React dashboard routes: `web/frontend/src/App.js`
- Mobile control plane: `mobile-app/src/control-plane/client.ts`

## Architectural shape today

The repo has three operator surfaces over a shared LAN-control backend:

1. `nanodlna/` CLI for direct DLNA interactions
2. `web/frontend/` React dashboard talking to the FastAPI backend
3. `mobile-app/` Expo app with local and remote control-plane modes

The backend is transitional rather than fully unified:

- legacy `DeviceManager` paths still exist
- unified discovery (`DiscoveryManager`) exists alongside them
- `DiscoveryMigrationAdapter` keeps compatibility state flowing between the two
- `AppRuntime` is the central service container used by routers and newer code

## Main backend subsystems

- device/discovery/runtime control
- streaming and playback orchestration
- overlay casting
- renderer/projector control
- projection mapping
- structured lighting
- media library management
- diagnostics and log streaming

## Notes on drift

Older repo documents and plans sometimes describe historical or proposed states
that no longer match the live code. When in doubt, prefer:

1. `README.md`
2. router/service code
3. current tests that still run
