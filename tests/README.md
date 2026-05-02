# nano-dlna Test Guide

## Overview

The repository has three active automated test lanes:

1. `tests/` — legacy Python tests, older integration coverage, helper factories,
   and mocks
2. `web/backend/tests_backend/` — newer backend service/runtime tests
3. `mobile-app/tests/` — Node-based tests for the mobile control plane and
   remote API contract shaping

Treat the code and the current test results as the source of truth. Some older
Python tests are stale and no longer match the live backend routes or response
schemas.

## Current layout

```text
tests/                          Legacy Python tests, helpers, mocks
web/backend/tests_backend/      Backend service/runtime tests
mobile-app/tests/               Mobile control-plane tests
```

Useful support modules:

- `tests/mocks/` — DLNA/device/streaming mocks used by older tests
- `tests/factories/` — factory helpers for Python tests
- `tests/utils/test_helpers.py` — temp DB, async, file, and network helpers
- `web/backend/tests_backend/conftest.py` — backend-specific DB/app fixtures

## Running tests

### Legacy Python wrapper

```bash
./run_tests.sh
```

This wrapper assumes the backend virtualenv exists at `web/backend/venv/` and
uses that interpreter directly.

### Targeted backend tests

```bash
cd web/backend
venv/bin/python -m pytest tests_backend
```

### Targeted legacy/root Python tests

```bash
web/backend/venv/bin/python -m pytest tests/test_dlna_device.py -q
```

### Mobile tests

```bash
cd mobile-app
npm test
npm run typecheck
```

## Known realities

- The mobile test lane is currently the healthiest automated path in the repo.
- Older Python API/router tests had drifted badly enough from the live
  backend app shape, routes, and response schemas that they were removed during
  cleanup. Treat legacy-style contract assertions carefully and verify live
  routers/schemas first.
- Startup and hardware-backed workflows remain weakly automated. Several
  dashboard/startup tests are explicitly manual or skipped.

## Common issues

### Import-path sensitivity

The backend still uses cwd-sensitive imports such as `database`, `routers`,
`services`, and `core`. Running pytest from the wrong directory can break
collection unless `PYTHONPATH` includes both the repo root and `web/backend/`.

### Optional dependency breakage

Importing `web.backend.main` loads optional features such as widgets, display
enumeration, and depth processing. Missing packages like `beautifulsoup4`,
`screeninfo`, `zeroconf`, or `scikit-learn` can fail broad app imports during
test collection.

### SQLAlchemy metadata churn

The Python fixtures deliberately manage metadata and dependency overrides to
avoid test DB bleed-over. Prefer existing fixtures over hand-rolled DB setup.

## Writing and maintaining tests

- Prefer service-level or controller-level seams over giant end-to-end mocks.
- Keep backend tests focused on one subsystem at a time.
- When adding API tests, verify the live router signatures and Pydantic schemas
  first; several old tests drifted because they encoded outdated response
  shapes.
- For mobile work, keep testing at the control-plane/client layer unless a real
  React Native rendering assertion is necessary.
