# nano-dlna mobile app

This is the separate cross-platform rewrite shell for `nano-dlna`, built with Expo + React Native and kept isolated from the existing React dashboard in `web/frontend`.

## What it covers

- overview of the current backend/web platform shape
- device discovery and inventory via the existing FastAPI APIs
- media library shell for indexed videos
- operations/diagnostics surface for streaming and advanced feature migration
- backend URL configuration for simulator, emulator, and LAN-device use

## Backend contract

The mobile app is intentionally thin. It reuses the current backend instead of duplicating DLNA, overlay, or projection logic on-device.

Primary API groups:

- `/health`
- `/api/devices`
- `/api/devices/discover`
- `/api/videos`
- `/api/streaming/analytics`
- future targets: `/api/renderer`, `/api/overlay`, `/api/mappings`, `/api/projection`

## Local development

```bash
cd mobile-app
npm install
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

## OMX team workflow

oh-my-codex is installed and initialized in this repo. To continue the rewrite with durable team mode:

```bash
omx team 3:executor "Continue the nano-dlna mobile rewrite in mobile-app using the existing FastAPI endpoints as the control plane."
```

The root `AGENTS.md` now includes project-specific guidance telling OMX to keep mobile work in `mobile-app/` and treat `web/backend` as the shared backend.
