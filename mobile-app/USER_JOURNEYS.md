# Mobile local-mode user journeys

This document maps the primary local-first journeys for the nano-dlna Expo operator console. It is intended to guide UI/UX, implementation, QA, and future parity decisions.

## Experience principles

- **Local first:** the app should be useful on first launch without a backend.
- **Operator confidence:** every action should produce a clear state change, action-history entry, or explainable deferred response.
- **No fake affordances:** remote/native-heavy features should remain visible only with honest constraints and recovery paths.
- **One shared seam:** screens should use the control-plane client so local and remote behavior stay consistent.

## Persona

**Operator / installer** managing local media playback, discovery, diagnostics, and advanced projection workflows from a phone or tablet.

Primary goals:
- Confirm the app is ready without a server.
- Select a playback target.
- Play or manage sample/local media.
- Understand what is local-ready, backend-backed, or native-deferred.
- Switch to remote mode only when heavyweight workflows require it.

Likely barriers:
- Local network permissions may be unavailable.
- Expo Go/simulators may not expose native discovery modules.
- Protocol-specific sender/receiver transport is not complete for all device types.
- Backend URLs differ between iOS simulator, Android emulator, and physical devices.

## Global action response model

Every user action should resolve to one of four UX states:

1. **Success** — local state updates or remote action completes.
2. **Deferred** — the app recognizes the workflow, but it requires native transport or backend support.
3. **Needs input** — the user must select a device, media item, config, or session first.
4. **Error** — unexpected failure with an actionable retry or settings path.

Deferred is not treated as a crash. It should be shown as an intentional product state and recorded in local action history.

## Journey 1 — First launch and local readiness

User goal: confirm the app works immediately.

1. User launches the app.
2. Header shows `Mode: local`.
3. Overview loads local health, seeded devices, session count, and discovery status.
4. User sees that the local control plane is ready.

Touchpoints:
- Header mode chip.
- Overview metrics.
- Settings connection notes.
- Operations action history.

System responses:
- Restore saved app mode, API URL, and selected target when state exists.
- Seed a local simulator display and sample media when state does not exist.

Opportunity:
- Add a first-run checklist: “Local mode ready”, “Select a target”, “Play demo media”.

## Journey 2 — Discover and select a device

User goal: choose a target for playback and operations.

1. User opens Devices.
2. Device list shows local simulator, saved manual profile, and native-discovered devices when available.
3. User taps Discover.
4. App runs native discovery if available; otherwise it refreshes saved/manual profiles.
5. User selects a target.
6. Header target chip updates globally.

Scenarios:
- Native discovery finds services: show discovered devices with a `native discovery` status.
- Native discovery unavailable: keep local/manual devices visible and explain runtime limitations.
- User selects discovery-only target: allow selection, but playback/control actions return deferred transport messages.

Opportunity:
- Badge devices as `Playable locally`, `Profile`, or `Discovery-only`.

## Journey 3 — Play local media

User goal: play a sample/local video on the selected target.

1. User opens Media.
2. App lists videos, photos, directories, lists, channels, and photo lists from local state.
3. User taps play on a video.
4. If the selected target supports local/manual actions, playback state becomes playing.
5. Overview and Operations reflect the active session.

Scenarios:
- No selected device: prompt the user to choose a device.
- Local/manual target: create or update a local streaming session.
- Discovery-only target: return a deferred response explaining sender transport is not wired yet.
- Deleted active video: stop playback and clear the related session.

Opportunity:
- Show a “Try demo reel” CTA when no user media exists.

## Journey 4 — Manage playback and device controls

User goal: pause, stop, and change control mode safely.

1. User opens Devices or Operations.
2. User taps Pause, Stop, Manual, or Auto.
3. App updates local state and action history.
4. UI refreshes playback state and session metrics.

Scenarios:
- Manual-capable target: action succeeds locally.
- Discovery-only target: action is deferred with a plain-language reason.
- Manual mode expires: app can return the target to automatic local mode.

Opportunity:
- Use concise inline feedback: “Paused locally” or “Discovery-only until sender transport is implemented”.

## Journey 5 — Review operations and action history

User goal: understand what the app has done and what is available.

1. User opens Operations.
2. Local mode loads analytics, health, sessions, capabilities, action history, and deferred features.
3. User reviews active sessions and recent actions.
4. User can complete, reset, or stop local sessions.

Scenarios:
- No sessions: show empty-state guidance to play sample media.
- Deferred feature history exists: show it as informational, not failure.
- Remote mode active: expand to renderer, projector, AirPlay, overlay, mapping, and projection controls.

Opportunity:
- Group history into `Completed`, `Deferred`, and `Needs backend/native build`.

## Journey 6 — Inspect logs in local mode

User goal: inspect app activity without a backend.

1. User opens Logs.
2. App reads local action history through the log UI.
3. Sources show `local-control-plane`.
4. User can search or tail local activity.

Scenarios:
- No backend: local logs still populate from action history.
- Search has no matches: show “No local actions match this search.”
- Remote mode: logs use backend endpoints.

Opportunity:
- Label local logs as “On-device activity” to avoid confusion with server logs.

## Journey 7 — Overlay and projection workflows

User goal: create overlay configs or understand casting/export constraints.

1. User opens Overlay.
2. Local mode lists local videos, local overlay configs, local/manual devices, and brightness state.
3. User creates an overlay config; it is stored locally.
4. User starts cast or export; app returns deferred/safe no-op response when native/backend transport is required.
5. Action history records the deferred action.

Scenarios:
- Create/delete overlay config: supported locally.
- Start overlay cast: deferred until sender transport exists.
- Export MP4: deferred/remote-only; no hidden network call.
- Adjust brightness: local state updates safely.

Opportunity:
- Disable cast/export only when paired with a visible “Why?” explanation and remote-mode CTA.

## Journey 8 — Projection animation lists

User goal: manage projection animation flows or see why they are unavailable locally.

1. User opens Projection.
2. Local mode loads animation/list state through the control-plane seam.
3. User attempts to save an animation list.
4. App returns an explicit deferred response and records the action.

Scenarios:
- Remote mode: full CRUD routes are available.
- Local mode: list management is safely deferred.

Opportunity:
- Provide sample preview cards for future animation support without implying live projection is available.

## Journey 9 — Structured lighting

User goal: start calibration or understand local constraints.

1. User opens Structured Lighting.
2. Local mode shows deferred capabilities/status and available local device/projector profiles.
3. User creates or starts a session.
4. App returns a deferred response explaining structured lighting remains backend/native-heavy.
5. Capture subflows remain navigable where camera/file support exists; upload/decode/publish defer locally.

Scenarios:
- Remote backend configured: structured lighting routes work through the backend.
- Local mode: forms remain navigable, actions are explainable and non-destructive.

Opportunity:
- Add a “Requires backend/native build” banner with a direct Settings shortcut.

## Journey 10 — Depth processing

User goal: upload, segment, preview, export masks, or create projection from a depth map.

1. User opens Depth.
2. Remote mode supports web upload and backend processing.
3. Local mode keeps preview URLs stable, but upload/segmentation/export/projection return safe deferred responses.
4. UI surfaces the deferred message as action feedback instead of failure.

Scenarios:
- User taps upload in local mode: app says depth processing is deferred/remote-only.
- User has a depth ID from a remote workflow: preview URL can still be generated consistently.
- User exports masks in local mode: receives a JSON deferred payload instead of a network failure.

Opportunity:
- Offer “Switch to remote mode” on deferred depth actions.

## Journey 11 — Settings and mode switching

User goal: move between local mode and backend-backed remote mode.

1. User opens Settings.
2. User sees Local and Remote mode options.
3. If remote, user edits fallback API URL.
4. User applies/tests connection.
5. App stores mode/API URL locally and refreshes health/discovery status.

Scenarios:
- Bad remote URL: show normalized URL and clear connection error.
- Local mode selected: hide remote-only urgency and show local readiness.
- Physical device: notes explain localhost/emulator/LAN differences.

Opportunity:
- Pair “Test backend” and “Return to local mode” as safe controls.

## Completion criteria

- Every tab loads in local mode without backend network calls.
- Every control succeeds locally, returns a useful deferred response, or asks for missing input.
- Local action history is visible through Operations and Logs.
- Advanced features are labeled as deferred/remote/native requirements, never as broken hidden failures.
- Remote mode remains available for heavyweight workflows.
