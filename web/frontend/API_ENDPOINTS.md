# Frontend Dashboard API Notes

This file documents the backend API groups the React dashboard relies on today.
It is intentionally compact: the live source of truth is the router code under
`web/backend/routers/` plus the generated docs at `http://localhost:8000/docs`.

## API configuration

The frontend development server proxies backend requests to
`http://localhost:8000` via the `proxy` field in `web/frontend/package.json`.
The API client lives in `web/frontend/src/services/api.js` and targets the
backend `/api` base.

## High-value API groups

### Devices

Base router: `web/backend/routers/device_router.py`

Common endpoints used by the dashboard:

- `GET /api/devices`
- `GET /api/devices/{device_id}`
- `GET /api/devices/discovery/status`
- `GET /api/devices/discover`
- `POST /api/devices/discover`
- `POST /api/devices/{device_id}/play`
- `POST /api/devices/{device_id}/pause`
- `POST /api/devices/{device_id}/stop`
- `POST /api/devices/{device_id}/seek`
- `POST /api/devices/{device_id}/control/auto`
- `POST /api/devices/{device_id}/control/manual`
- `GET /api/devices/{device_id}/control`
- `POST /api/devices/load-config`
- `POST /api/devices/save-config`

### Videos and photos

Routers:

- `web/backend/routers/video_router.py`
- `web/backend/routers/photo_router.py`
- `web/backend/routers/photo_list_router.py`

Common endpoints:

- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `POST /api/videos`
- `PUT /api/videos/{video_id}`
- `DELETE /api/videos/{video_id}`
- `POST /api/videos/upload`
- `POST /api/videos/scan`
- `POST /api/videos/scan-directory`
- `GET /api/photos`

### Streaming

Base router: `web/backend/routers/streaming_router.py`

Common endpoints:

- `GET /api/streaming/analytics`
- `GET /api/streaming/sessions`
- `GET /api/streaming/health`
- `POST /api/streaming/sessions/{session_id}/complete`
- `POST /api/streaming/sessions/{session_id}/reset`
- `DELETE /api/streaming/sessions/{session_id}`

### Renderer / overlay / projection

Routers:

- `web/backend/routers/renderer_router.py`
- `web/backend/routers/overlay_router.py`
- `web/backend/routers/projection_router.py`
- `web/backend/routers/mapping_router.py`

Examples:

- `GET /api/renderer/list`
- `GET /api/renderer/projectors`
- `GET /api/renderer/scenes`
- `POST /api/renderer/start`
- `POST /api/renderer/start_projector`
- `POST /api/renderer/pause/{projector_id}`
- `POST /api/renderer/resume/{projector_id}`
- `POST /api/renderer/stop`
- `GET /api/overlay/configs`
- `GET /api/overlay/status`
- `POST /api/overlay/sync`
- `POST /api/overlay/cast`
- `GET /api/mappings/scenes`
- `GET /api/mappings/ranks`
- `GET /api/mappings/scene-control-presets`
- `GET /api/projection/configs`
- `POST /api/projection/configs/{config_id}/launch`

### Structured lighting and depth

Routers:

- `web/backend/routers/structured_lighting_router.py`
- `web/backend/routers/depth_router.py`

These features are more specialized and may depend on optional packages or host
hardware.

## Operational notes

- Health check lives at `/health`, not `/api/health`.
- Some backend features are optional and can fail import or startup if packages
  like `scikit-learn`, `screeninfo`, `zeroconf`, or `beautifulsoup4` are
  missing.
- For exact request/response models, prefer FastAPI docs and the live router
  code over static prose here.
