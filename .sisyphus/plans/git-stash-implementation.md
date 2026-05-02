# Plan: Git Stash Implementation and Workspace Finalization

Review, implement, and complete working code from git stashes and patches. Finalize the workspace components (service, frontend, backend, db) and the mobile app rewrite.

## User Review Required

> [!IMPORTANT]
> - `stash@{1}` contains work that is already partially present in the codebase but in a messy/duplicated state (especially `projection_router.py`). I will consolidate these.
> - `transcreen.patch` introduces a standard `HTTPServer` which conflicts with the current `Twisted` architecture. I will merge the CLI improvements from the patch but retain `Twisted` for the streaming server to maintain stability.
> - I will apply `stash@{0}` and `stash@{2}` as they contain relevant agent and workspace configurations.

- [ ] **Acceptance Criteria**: All 16+ new animations visible in the dashboard.
- [ ] **Acceptance Criteria**: Mobile app successfully fetches AirPlay devices and Renderer status.
- [ ] **Acceptance Criteria**: CLI `play` command functional.

---

## Proposed Changes

### Configuration & Git
#### [STASH] Apply Configuration Stashes
- Apply `stash@{0}` (agent configs) and `stash@{2}` (workspace trust).
- Verify `.codex/config.toml` and `.codex/agents/*.toml` updates.

### Backend (FastAPI)
#### [CLEANUP] Consolidate Projection Animations
- File: `web/backend/routers/projection_router.py`
- Merge the two sets of animation definitions.
- Ensure each ID is unique and carries the best description (e.g., Shadertoy source references).
- Verify that the frontend `ANIMATION_LIBRARY` matches the backend IDs.

#### [FEATURE] Merge CLI Improvements
- File: `nanodlna/cli.py`
- Implement the `play` command logic from `transcreen.patch`.
- Wire the CLI to use the existing `nanodlna/streaming.py` logic instead of the patch's `HTTPServer` to avoid architectural drift.

### Mobile App (Expo)
#### [FIX] Finalize Controller Logic
- File: `mobile-app/src/features/operations/useOperationsController.ts`
- Ensure all stashed hooks (AirPlay discovery, Renderer status) are correctly wired to the `ControlPlaneClient`.
- Verify `api.ts` and `client.ts` have full parity with the FastAPI backend endpoints.

---

## Verification Plan

### Automated Tests
- Run backend tests: `pytest web/backend/tests_backend`
- Run mobile typecheck: `cd mobile-app && npm run typecheck`
- Run mobile tests: `cd mobile-app && npm test`

### Manual Verification
- Start the dashboard: `./run_dashboard.sh`
- Check `/api/projection/animations` for the consolidated list.
- Open the mobile app (in simulator or via Expo Go) and verify the "AirPlay devices" section in the Operations screen.
- Test CLI: `python3 -m nanodlna.cli play -c my_device_config.json`

## Final Verification Wave
- [ ] User confirms all stashed features are active and working.
- [ ] User confirms CLI `play` command is functional.
- [ ] Run `git stash clear` and `rm transcreen.patch`.
