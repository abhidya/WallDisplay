# Technical Notes

This page keeps a short set of technical facts that are useful to repeat, while
leaving full behavioral detail to the code and the root `README.md`.

## Backend stack

- FastAPI application in `web/backend/`
- SQLite via SQLAlchemy ORM
- Pydantic schemas for API models
- Playwright + FFmpeg for overlay export/cast paths
- NumPy / Pillow / OpenCV-based processing for depth and structured-lighting
  features

## Frontend stack

- React dashboard in `web/frontend/`
- Axios-based API client in `web/frontend/src/services/api.js`
- Expo/React Native app in `mobile-app/`

## Import/runtime caveat

The backend still mixes repo-root and `web/backend` absolute import styles (for
example `database`, `routers`, `services`, `core`). This means direct execution
and ad hoc test runs can still depend on the working directory and `PYTHONPATH`.

## Optional feature dependencies

Some backend features are optional and can affect broad app imports:

- widget scraping: `beautifulsoup4`
- display enumeration: `screeninfo`
- AirPlay discovery: `zeroconf`
- some depth flows: `scikit-learn`

The app should degrade more gracefully over time, but these optional dependencies
still matter today when importing the full backend app.

## Testing reality

- Mobile control-plane tests are currently the most reliable automated lane.
- Backend Python tests are valuable but often service-level and heavily mocked.
- Full startup and hardware workflows are only lightly automated.
