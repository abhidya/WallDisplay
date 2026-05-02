# nano-dlna Test Infrastructure

## Overview

This document describes the test infrastructure that actually exists in the
repository today. It is intentionally narrower than an aspirational testing
roadmap: if a lane, directory, or tool is not committed in this repo, it is not
documented here as active infrastructure.

## Active test lanes

```text
tests/                          Legacy Python tests, helpers, mocks
tests/integration/              Older Python integration tests
tests/performance/              Lightweight performance/load probe
web/backend/tests_backend/      Backend service/runtime tests
web/frontend/src/tests/         Frontend component tests
mobile-app/tests/               Mobile control-plane tests
```

Important support files:

- `tests/conftest.py`
- `web/backend/tests_backend/conftest.py`
- `tests/factories/`
- `tests/mocks/`
- `tests/utils/test_helpers.py`

## What is configured

### Python

- Root pytest config lives in `pyproject.toml` and `pytest.ini`
- Root Python test paths:
  - `tests`
  - `web/backend/tests_backend`
- Coverage is configured for:
  - `nanodlna`
  - `web.backend`

### Mobile

- `mobile-app/package.json` provides:
  - `npm test`
  - `npm run typecheck`

### Performance

- The repository contains `tests/performance/test_load.py`
- `tests/validate_infrastructure.py` expects a performance marker in
  `pytest.ini`; keep that validator aligned with actual pytest config if the
  infra changes

## What is not currently active infrastructure

The repo does **not** currently contain committed first-class directories or
tooling for:

- `tests/e2e/`
- `tests/security/`
- `tests/contracts/`
- `tests/fixtures/`
- `tests/reports/`
- Playwright/Cypress-based web E2E automation
- bandit/safety/ZAP automation
- Locust or pytest-benchmark integration

If those capabilities are added later, document them only after the code and
tooling land.

## Execution paths

### Legacy Python wrapper

```bash
./run_tests.sh
```

Notes:

- uses `web/backend/venv/bin/python`
- assumes that backend virtualenv already exists
- enables `-n auto` in the wrapper, although xdist availability depends on the
  environment actually used

### Backend-focused Python tests

```bash
cd web/backend
venv/bin/python -m pytest tests_backend
```

### Mobile tests

```bash
cd mobile-app
npm test
npm run typecheck
```

## Current reliability notes

- The mobile test lane is the most consistently runnable automated path in the
  repo.
- Some older Python API/router tests are stale and should be considered cleanup
  targets rather than trusted contract coverage.
- Broad backend app imports can fail if optional dependencies are missing,
  because `web.backend.main` mounts optional routers during import.
- Backend Python tests are sensitive to working directory and import path setup
  because the backend still mixes repo-root and `web/backend` absolute imports.

## Fixtures and mocking strategy

- Older Python tests rely heavily on mocks under `tests/mocks/`
- Backend service tests rely heavily on `monkeypatch`, `SimpleNamespace`, and
  focused seam injection
- Temp DB setup lives in:
  - `tests/utils/test_helpers.py`
  - `web/backend/tests_backend/conftest.py`

This means much of the backend coverage is service-level and mocked, not
full-stack or hardware-backed.

## Maintenance rules

1. Update this file when adding or removing real test directories or tooling
2. Do not document aspirational test categories as active infrastructure
3. Verify live router/schema shapes before adding API contract assertions
4. Keep required docs (`tests/README.md`, `tests/TEST_INFRASTRUCTURE.md`)
   present because `tests/validate_infrastructure.py` checks for them
