# nano-dlna mobile app

This is the separate cross-platform rewrite shell for `nano-dlna`, built with Expo + React Native and kept isolated from the existing React dashboard in `web/frontend`.

## Rewrite boundaries

- Work only inside `mobile-app/`.
- Reuse the existing FastAPI backend as the control plane.
- Do not fork or reimplement DLNA, overlay, renderer, mapping, or projection logic on-device.
- Keep the current web/frontend and backend source untouched while mobile parity grows here.

## Current operator-first coverage

- overview of the current backend/web platform shape
- device discovery, selection, and control-mode/runtime actions via the existing FastAPI APIs
- media inventory for videos, photos, directories, lists, and channels
- operations/diagnostics surface for streaming, renderer, overlay, mapping, and projection workflows
- backend URL configuration for simulator, emulator, and LAN-device use

### Screen-to-endpoint map

| Screen | Current mobile behavior | FastAPI endpoints in use |
| --- | --- | --- |
| Overview | Live landing screen for backend health, discovery status, device count, streaming analytics, renderer count, and projection inventory | `/health`, `/api/devices`, `/api/streaming/analytics`, `/api/renderer/list`, `/api/projection/configs`, `/api/v2/discovery/status` |
| Devices | Device inventory, discovery run/pause/resume, unified discovery backend toggles, per-device detail, control mode, pause/stop/manual/auto actions | `/api/devices`, `/api/devices/discover`, `/api/devices/discovery/status`, `/api/devices/discovery/pause`, `/api/devices/discovery/resume`, `/api/devices/{id}`, `/api/devices/{id}/control`, `/api/devices/{id}/control/auto`, `/api/devices/{id}/control/manual`, `/api/devices/{id}/pause`, `/api/devices/{id}/stop`, `/api/v2/discovery/status`, `/api/v2/discovery/capabilities`, `/api/v2/discovery/backends`, `/api/v2/discovery/backends/{name}/enable`, `/api/v2/discovery/backends/{name}/disable` |
| Media | Video inventory plus selected-device playback, with read-first parity for photos, directories, lists, and channels | `/api/videos`, `/api/photos`, `/api/media-library/directories`, `/api/media-library/lists`, `/api/media-library/channels`, `/api/devices/{id}/play` |
| Operations | Streaming analytics, active sessions, renderer/projector/scene selection, overlay sync, mapping inventory, scene ranks/presets, projection launch/status | `/api/streaming/analytics`, `/api/streaming/sessions`, `/api/renderer/list`, `/api/renderer/projectors`, `/api/renderer/scenes`, `/api/renderer/start`, `/api/renderer/start_projector`, `/api/renderer/pause/{projector}`, `/api/renderer/resume/{projector}`, `/api/renderer/stop`, `/api/overlay/configs`, `/api/overlay/status`, `/api/overlay/sync`, `/api/mappings/scenes`, `/api/mappings/ranks`, `/api/mappings/scene-control-presets`, `/api/projection/configs`, `/api/projection/configs/{id}/launch`, `/api/projection/sessions/{id}` |
| Settings | Base URL normalization, connection testing, backend health confirmation, and discovery visibility | `/health`, `/api/v2/discovery/status` |

## Code-quality notes

- The mobile shell keeps controller logic in `src/features/**` and presentation in `src/screens/**` to avoid coupling backend requests directly into screen components.
- Selection state is shared across tabs so a device chosen in Devices is immediately reused by Media.
- The UI intentionally favors operator actions and read-heavy diagnostics over authoring-heavy projection editors for now.
- Current verification baseline is TypeScript-only; there are not yet dedicated `test` or `lint` npm scripts in `mobile-app/package.json`.

## Backend contract

The mobile app is intentionally thin. It reuses the current backend instead of duplicating DLNA, overlay, or projection logic on-device.

Primary API groups:

- `/health`
- `/api/devices`
- `/api/devices/discover`
- `/api/videos`
- `/api/streaming/analytics`
- `/api/renderer`
- `/api/overlay`
- `/api/mappings`
- `/api/projection`
- `/api/media-library`

## Local development

```bash
cd mobile-app
npm install
npm run typecheck
npm run ios
```

Use `EXPO_PUBLIC_API_BASE_URL` to point the app at the backend:

```bash
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api npm start
```

Typical addresses:

- iOS simulator: `http://127.0.0.1:8000/api`
- Android emulator: `http://10.0.2.2:8000/api`
- physical device: `http://<your-mac-or-backend-host-ip>:8000/api`

## Verification

```bash
cd mobile-app
npm install
npm run typecheck
```

The current repo state provides TypeScript verification for the Expo shell. If you need broader coverage, add mobile-specific test/lint scripts here rather than reaching into `web/frontend` or backend source.

## OMX team workflow

oh-my-codex is installed and initialized in this repo. To continue the rewrite with durable team mode:

```bash
omx team 3:executor "Continue the nano-dlna mobile rewrite in mobile-app using the existing FastAPI endpoints as the control plane."
```

The root `AGENTS.md` now includes project-specific guidance telling OMX to keep mobile work in `mobile-app/` and treat `web/backend` as the shared backend.
