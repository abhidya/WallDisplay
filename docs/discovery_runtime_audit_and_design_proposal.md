# Discovery Runtime Audit And Design Proposal

## Background

The current runtime is in a transitional state:

- the legacy runtime centered on `DeviceManager` is still the active business engine
- the newer discovery-v2 stack exists, but is not yet authoritative
- a migration adapter keeps both systems alive at once

This document is based on code traces only. It describes:

- what the current systems and loops do
- where they are called from
- what data they read and write
- which frontend and DB use cases depend on them
- a proposed target design
- the migration path

## Implementation Status

The following parts of the proposal are now partially implemented in code:

- `DeviceViewService`
  - frontend-facing device DTO assembly has been extracted from `DeviceService`
- `PlaybackIntentService`
  - assignment, priority, retry, and scheduling state now lives behind a dedicated service
- `PlaybackOrchestrator`
  - discovery-time playback decisions and overlay auto-cast decisions now delegate through an orchestrator service
  - streaming-stall and playback-restart recovery now share orchestrator helpers
- `RuntimeRegistryService`
  - live `device_status`, `last_seen`, and connection-timestamp state now lives behind a dedicated service
- `DeviceInventoryService`
  - live in-memory device inventory now lives behind a dedicated service while `device_manager.devices` remains a compatibility property
- `DiscoveryCoordinator`
  - raw DLNA discovery, device reconciliation, and discovery loop lifecycle now delegate through a coordinator service
  - discovery inventory reads now go through inventory helpers so the coordinator can work against either the extracted inventory service or the legacy dict surface
- `PlaybackMonitoringService`
  - playback health threads, playback history, and stalled/restart monitoring now live behind a dedicated service
  - internal monitoring/orchestration services now snapshot explicit dependencies and callables instead of treating `DeviceManager` as an unbounded shared state bag
- `AppRuntime`
  - backend startup now assembles extracted services through a composition root instead of hand-wiring them ad hoc in `main.py`
  - production callers like device routers, streaming routers, overlay cast fallback, and DLNA device creation now resolve the runtime through this composition root instead of reaching straight for `get_device_manager()`
  - discovery/migration background-service lifecycle and DB-device hydration now route through this runtime bundle instead of being orchestrated inline in `main.py`
  - startup inventory logging now reads through runtime inventory helpers instead of peeking into `device_manager.devices` directly
  - common inventory, assigned-video, playback-progress, and device-service wiring helpers now read from extracted inventory/registry/intent services first, with legacy manager fallbacks kept for compatibility
  - runtime helpers now also own the DB-backed “recover missing device” path and the DB-aware autoplay/manual-play handoff used for stream reuse
  - discovery lifecycle methods now target the extracted discovery coordinator directly instead of delegating through legacy manager wrapper methods
  - DB persistence for playback-progress updates now also routes through runtime helpers instead of being orchestrated inline in `DeviceManager`
- `DiscoveryMigrationAdapter`
  - the old-system side of the migration bridge now targets the runtime facade first, with compatibility fallbacks for raw `DeviceManager` behavior
- `DeviceRuntimeSyncService`
  - `DeviceService` runtime registration/update/unregister paths now go through a dedicated DB-to-runtime synchronization service instead of building manager interactions inline
- `DeviceLifecycleService`
  - runtime device lookup, registration, cleanup, unregister, and playing-state mutation now delegate through a dedicated lifecycle service instead of living inline in `DeviceManager`
- `AppRuntime`
  - basic runtime lifecycle operations like get/register/unregister/cleanup now route to extracted lifecycle and registry services directly instead of tunneling through `DeviceManager`
  - playback-progress updates now route through runtime-state helpers first and only update the core device object as a local compatibility step
  - shared runtime metadata like the device-state lock, connectivity timeout, and discovery coordinator are now stored explicitly on the runtime bundle instead of always being re-read through `DeviceManager`
  - autoplay execution now routes through a dedicated `RuntimePlaybackService`, so `DeviceManager.auto_play_video(...)` has become a delegating compatibility method instead of the owner of stream-and-play execution
- `DeviceService`
  - no longer needs to retain a direct `DeviceManager` handle internally; its constructor now prefers the runtime facade and only uses a passed manager to recover the matching runtime bundle
- `RuntimePlaybackService`
  - owns runtime autoplay / direct stream-and-play execution that previously lived inline in `DeviceManager.auto_play_video(...)`
  - is now the runtime-side execution path used by `AppRuntime.auto_play_video(...)`
  - `AppRuntime.auto_play_video(...)` now self-bootstraps this service on demand instead of falling back to `DeviceManager`, which removes another manager-owned playback path from the normal runtime flow
- orchestration and monitoring now recover persisted device records through `AppRuntime.get_db_device_by_name(...)` instead of relying on a manager-held `device_service`, which keeps user-control-mode and recovery checks working as the manager facade gets thinner
- runtime AirPlay casting now also routes through `AppRuntime.process_airplay_casting(...)`; the manager method is only a compatibility wrapper, and the old broken status-update call shape on that path has been removed
- `RuntimePlaybackService` now recognizes remote `http(s)` URLs and plays them directly on the renderer instead of incorrectly forcing them through the local-file streaming fallback, which makes the runtime-owned AirPlay / overlay URL path actually functional
- disconnect evaluation in `DiscoveryCoordinator` now looks up persisted DB state through runtime DB helpers instead of referencing a nonexistent `manager.device_service` attribute
- streaming-issue recovery now also routes through `AppRuntime.handle_streaming_issue(...)`; `DeviceManager._handle_streaming_issue(...)` has been reduced to a delegating compatibility wrapper
- the remaining playback-monitoring helper wrappers (`start/stop health check`, `track playback result`, `get playback stats`) are now exposed on `AppRuntime` as well, which further reduces manager-owned monitoring behavior
- `StreamingSessionRegistry` now supports explicit health-handler unregistration, and runtime construction rebinds the stalled-session callback from `DeviceManager` to `AppRuntime`, so the runtime is now the registered owner of that recovery path as well as its implementation owner
- the shared `StreamingService` singleton no longer carries a dead `device_manager` fallback path; runtime lookup is now its only recovery/control surface
- `DLNADevice` no longer snapshots `runtime.device_manager` just to resolve assigned-video intent; that fallback now reads straight from `AppRuntime.get_assigned_video(...)`
- `BrightnessControlService` and `OverlayCastService` have had dead manager-shaped fields removed as well, so those services now reflect the actual runtime/discovery dependency graph instead of keeping stale legacy references
- `main.py` now publishes the runtime bundle itself as the startup-time `device_manager` global compatibility surface, backed by small discovery-control wrappers on `AppRuntime`, so the app entrypoint now exposes the real control surface instead of the raw legacy manager singleton
- `DeviceService` constructor normalization is now runtime-first as well: unknown manager-shaped inputs no longer become ad hoc runtimes, and legacy manager call shapes are normalized back to `AppRuntime`
- `AppRuntime`’s lock/timeout/controller property layer is now less dependent on implicit manager fallbacks too; it can safely provide those values from explicit runtime fields or local defaults even in partial compatibility call shapes
- `StreamingService`
  - stalled-session recovery now resolves devices through `AppRuntime` first, with the legacy manager reference retained only as a fallback
  - the shared streaming singleton can now lazily recover its runtime facade through `AppRuntime` as well, so startup no longer needs to inject a direct `DeviceManager` reference into it

What has not changed yet:

- `DeviceManager` still owns the compatibility facade and remains the legacy runtime anchor for many callers
- the discovery thread is still started through the legacy `DeviceManager` interface even though the loop body now delegates
- discovery-v2 is still non-authoritative
- routers and frontend contracts are still intentionally unchanged

## Problem Summary

The main problem is not discovery itself. The problem is that discovery, runtime state, desired state, playback orchestration, health recovery, and overlay auto-cast are currently mixed together.

That creates five concrete risks:

1. one slow side effect can stall discovery
2. device availability is derived from a mix of raw sightings and unrelated DB timestamps
3. frontend read models depend on blended legacy state instead of a clean runtime model
4. persisted DB intent and in-memory runtime state are not clearly separated
5. discovery-v2 cannot cleanly take over because legacy and v2 both still participate in control flow

## Code-Trace Audit

## Startup And Runtime Ownership

At startup, the app:

1. creates the singleton `DeviceManager`
2. injects a `DeviceService`
3. loads persisted devices/config
4. starts the legacy discovery thread
5. then starts the migration bridge into discovery-v2

Code path:

- `web/backend/main.py`

Implication:

- the legacy manager is still the runtime source of truth
- discovery-v2 is additive, not primary

## Current Systems

### 1. `DeviceManager`

Primary file:

- `web/backend/core/device_manager.py`

Current responsibilities:

- raw DLNA discovery polling
- in-memory renderer registry
- availability/status tracking
- autoplay decision logic
- scheduled assignment / retry logic
- playback health thread management
- stalled streaming recovery callback handling
- overlay auto-cast trigger logic
- disconnect cleanup

Key methods:

- `start_discovery()`
- `_discovery_loop()`
- `_discover_dlna_devices()`
- `_process_device_video_assignment()`
- `_process_device_overlay_cast()`
- `assign_video_to_device()`
- `_schedule_retry()`
- `_playback_health_check_loop()`
- `_handle_streaming_issue()`
- `_check_disconnected_devices()`
- `update_device_status()`

### 2. `DeviceService`

Primary file:

- `web/backend/services/device_service.py`

Current responsibilities:

- DB CRUD for persisted devices
- manual playback API actions
- stream creation / reuse for device playback
- status updates back into DB
- ad hoc on-demand discovery endpoint
- API read-model assembly for frontend device pages

Key methods:

- `get_devices()`
- `get_device_by_id()`
- `play_video()`
- `stop_video()`
- `pause_video()`
- `seek_video()`
- `discover_devices()`
- `_device_to_dict()`

### 3. `DLNADevice`

Primary file:

- `web/backend/core/dlna_device.py`

Current responsibilities:

- SOAP transport actions
- polling transport state
- playback progress updates
- loop / restart behavior

Issue:

- transport and policy are mixed

### 4. `StreamingSessionRegistry`

Primary file:

- `web/backend/core/streaming_registry.py`

Current responsibilities:

- track streaming sessions
- detect stalled sessions
- notify registered health handlers

Current coupling:

- `DeviceManager` registers `_handle_streaming_issue()` as a health handler

### 5. `DiscoveryManager` (discovery-v2)

Primary file:

- `web/backend/discovery/discovery_manager.py`

Current responsibilities:

- backend registration
- unified discovered-device inventory
- backend-native cast/session routing

Current status:

- real subsystem
- not yet authoritative
- partially drifted from router expectations

### 6. `OverlayCastService`

Primary file:

- `web/backend/services/overlay_cast_service.py`

Current responsibilities:

- launch overlay render pipeline
- create relay stream
- hand off to DLNA target via discovery-v2
- retain fallback dependency on the legacy manager path

## Current Loops And Control Paths

### Legacy Discovery Loop

Entry:

- `main.py` -> `device_manager.start_discovery()`

Loop:

- `DeviceManager._discovery_loop()`

What it does each cycle:

1. calls `_discover_dlna_devices()`
2. registers or updates devices
3. updates `last_seen` and `device_status`
4. calls `_process_device_video_assignment()` for each discovered device
5. calls `_check_disconnected_devices()`
6. sleeps for `discovery_interval`

Data it produces:

- `self.devices`
- `self.device_status`
- `self.last_seen`
- `self.device_connected_at`
- side effects like autoplay and overlay cast starts

Why this is a problem:

- discovery is not observation-only
- the loop executes business actions directly

### Playback Health Loop

Entry:

- started by `_start_playback_health_check()`

Loop:

- `DeviceManager._playback_health_check_loop()`

What it does:

- checks if playback unexpectedly stopped
- checks streaming sessions
- attempts recovery
- updates in-memory device diagnostics

Data it produces:

- `streaming_issues`
- `streaming_bytes`
- `streaming_bandwidth_bps`
- recovery side effects

### Streaming Health Callback Loop

Entry:

- `StreamingSessionRegistry.register_health_check_handler(self._handle_streaming_issue)`

Callback:

- `DeviceManager._handle_streaming_issue()`

What it does:

- tries to recover missing runtime devices from DB
- marks devices degraded
- restarts playback if needed

This is a second orchestration path into the same legacy manager.

### Discovery Migration Loop

Entry:

- `main.py` -> `start_discovery_migration(device_manager)`

Loop:

- `DiscoveryMigrationAdapter._run_migration_loop()`

What it does:

1. migrates old devices/config into discovery-v2
2. starts discovery-v2 backends
3. syncs old -> new
4. syncs new -> old
5. repeats every 5 seconds

Implication:

- there is no single authoritative device registry today

## Frontend Use Cases Dependent On This Runtime

## Frontend Polling And Control Trace

This section traces the frontend loops explicitly.

### `Devices.js`

Primary file:

- `web/frontend/src/pages/Devices.js`

Loops:

- polls `GET /api/devices/` every 15 seconds
- polls `GET /api/devices/discovery/status` every 15 seconds
- local 1-second timer for playback clock display only

Control actions:

- `POST /api/devices/discovery/pause`
- `POST /api/devices/discovery/resume`
- `POST /api/devices/discover`
- manual device CRUD and playback navigation

Current backend owners:

- read model: `DeviceService.get_devices()` + `DeviceService._device_to_dict()`
- discovery loop state: `DeviceManager.get_discovery_status()`
- manual discovery: `DeviceService.discover_devices()` -> `DeviceManager._discover_dlna_devices()`

Future owners:

- device list read model: `DeviceViewService`
- discovery summary/control: `DiscoveryCoordinator` + `RendererRegistry`

### `DeviceDetail.js`

Primary file:

- `web/frontend/src/pages/DeviceDetail.js`

Loops:

- polls `GET /api/devices/{id}` every 15 seconds
- local 1-second timer for playback position display only

Control actions:

- `pause`
- `stop`

Current backend owners:

- detail read model: `DeviceService.get_device_by_id()` + `DeviceService._device_to_dict()`
- control actions: `DeviceService.pause_video()` / `stop_video()`

Future owners:

- detail read model: `DeviceViewService`
- control intent: `PlaybackIntentService` / `PlaybackOrchestrator`

### `PlayVideoOnDevice.js`

Primary file:

- `web/frontend/src/pages/PlayVideoOnDevice.js`

Load behavior:

- one-shot fetch of:
  - `GET /api/videos/{id}`
  - `GET /api/devices/`

Control action:

- `POST /api/devices/{id}/play`

Current backend owners:

- device list source: `DeviceService.get_devices()`
- play action: `DeviceService.play_video()`

Future owners:

- selectable renderer list: `DeviceViewService`
- play action: `PlaybackIntentService` / `PlaybackOrchestrator`

### `OverlayProjection.js`

Primary file:

- `web/frontend/src/pages/OverlayProjection.js`

Loops:

- one-shot load of overlay configs, videos, mapping scenes, brightness, cast devices, cast sessions
- polls overlay cast sessions every 1.5 seconds while cast is active/loading

Endpoints:

- `GET /api/v2/discovery/devices?casting_method=dlna`
- overlay config endpoints
- overlay brightness endpoints
- overlay cast session endpoints

Current backend owners:

- castable renderer inventory: discovery-v2 `DiscoveryManager`
- overlay runtime: `OverlayCastService`

Important note:

- this page already prefers discovery-v2 inventory rather than the legacy `/api/devices` list

Future owners:

- castable renderer inventory: `DiscoveryCoordinator` + `RendererRegistry`
- overlay session state: `OverlayCastService`
- read composition for device selection: `DeviceViewService` or a dedicated `ProjectionViewService`

### `StreamingDiagnostics.js`

Primary file:

- `web/frontend/src/pages/StreamingDiagnostics.js`

Loops:

- polls every 15 seconds

Endpoints:

- streaming stats
- streaming analytics
- streaming health
- streaming sessions
- overlay cast sessions

Current backend owners:

- `StreamingSessionRegistry` and associated streaming services
- `OverlayCastService`

Future owners:

- a dedicated diagnostics read service composing:
  - stream registry state
  - overlay session state
  - renderer linkage data

### `Renderer.js`

Primary file:

- `web/frontend/src/pages/Renderer.js`

Loops:

- one-shot load of projectors/scenes/renderers
- polls active renderers every 15 seconds

Endpoints:

- renderer service endpoints, not the legacy device stack

Current backend owners:

- renderer service subsystem

Future owners:

- unchanged in principle, but should reconcile renderer identity with the shared `RendererRegistry`

### `StructuredLighting.js`

Primary file:

- `web/frontend/src/pages/StructuredLighting.js`

Loops:

- one-shot load of:
  - structured-lighting capabilities
  - structured-lighting status
  - discovery-v2 DLNA devices
- selected-session detail polling every 3 seconds for:
  - runtime
  - captures
  - artifact review
  - status

Current backend owners:

- structured-lighting services
- discovery-v2 device inventory for projector selection

Future owners:

- structured-lighting service remains separate
- projector inventory should come from the same canonical registry used elsewhere

## Devices Page

Primary file:

- `web/frontend/src/pages/Devices.js`

Depends on:

- `GET /api/devices/`
- `GET /api/devices/discovery/status`

What it expects:

- stable `availability`
- stable `derived_status`
- `seconds_since_seen`
- reconnect/degraded/offline counters
- playback state
- manual override state
- overlay cast state

Current backend assembler:

- `DeviceService._device_to_dict()`

### Device Detail Page

Primary file:

- `web/frontend/src/pages/DeviceDetail.js`

Depends on:

- `GET /api/devices/{id}`
- `pause`
- `stop`

What it expects:

- current playback status
- timestamps
- progress / duration
- availability and overlay status

### Overlay Projection

Primary frontend surface:

- `web/frontend/src/pages/OverlayProjection.js`

Depends on:

- discovery-v2 device inventory
- overlay cast session lifecycle

Implication:

- discovery-v2 already matters to operator workflows

### Structured Lighting

Primary frontend surface:

- `web/frontend/src/pages/StructuredLighting.js`

Depends on:

- discovery-v2 device inventory for projector selection
- dedicated structured-lighting backend services

This is a useful reference because it is already closer to a session/service-oriented model than the legacy device runtime.

### Streaming Diagnostics

Primary frontend surface:

- `web/frontend/src/pages/StreamingDiagnostics.js`

Depends on:

- streaming session registry and overlay cast session diagnostics

Implication:

- the UI already expects separate visibility into:
  - device state
  - stream state
  - overlay state

## Frontend Connection Findings

1. The frontend is already split across two inventory sources:
   - legacy `/api/devices`
   - discovery-v2 `/api/v2/discovery/devices`

2. The `Devices` and `DeviceDetail` pages depend on a blended read model assembled in `DeviceService._device_to_dict()`, not on a single runtime state service.

3. `OverlayProjection` and `StructuredLighting` already lean toward discovery-v2 for renderer selection, which means the UI is ahead of the runtime architecture in some places.

4. Polling cadences are not extreme now, but the frontend still assumes:
   - a stable device list summary endpoint
   - a stable device detail endpoint
   - explicit diagnostics endpoints for streaming and overlay

5. Any refactor that changes runtime internals without introducing a replacement read-model layer will break the frontend contract.

## Persisted DB Use Cases

Primary model:

- `web/backend/models/device.py`

Current persisted fields include:

- renderer metadata:
  - `name`
  - `type`
  - `hostname`
  - `action_url`
  - `friendly_name`
  - `manufacturer`
  - `location`
- coarse runtime fields:
  - `status`
  - `is_playing`
  - `current_video`
  - `playback_position`
  - `playback_duration`
  - `playback_progress`
  - `streaming_url`
  - `streaming_port`
  - `playback_started_at`
- configuration / intent:
  - `config`
- operator override:
  - `user_control_mode`
  - `user_control_expires_at`
  - `user_control_reason`

Current problem:

- DB fields blend identity, intent, cached runtime state, and operator policy
- in-memory state duplicates part of the same truth

## Current Data Boundaries

### In-Memory Runtime Data

Owned mainly by `DeviceManager`:

- `devices`
- `device_status`
- `last_seen`
- `device_connected_at`
- `assigned_videos`
- retry/scheduling structures
- health-thread tracking

### Persisted Data

Owned mainly by `DeviceModel`:

- renderer metadata
- manual override state
- coarse playback state
- config blob

### Derived Frontend Read Model

Assembled in:

- `DeviceService._device_to_dict()`

It merges:

- DB fields
- legacy manager in-memory status
- overlay cast session info
- derived availability heuristics

This is the actual contract the frontend depends on.

## Main Audit Findings

1. `DeviceManager` is the effective runtime business engine.
2. Discovery is overloaded with orchestration responsibilities.
3. There are two discovery systems and a sync adapter, not one clean control plane.
4. Device identity still leans too hard on friendly name matching.
5. Persisted state and runtime state are not clearly separated.
6. Frontend read models are assembled ad hoc from multiple sources.
7. Discovery-v2 is not safe to declare authoritative until its router/manager API surface is reconciled.

## Proposal

## Design Goals

1. discovery produces sightings only
2. renderer state is canonical and stable
3. desired behavior is persisted separately from observed behavior
4. orchestration runs outside discovery polling
5. transport code is protocol-only
6. frontend reads from explicit view models, not blended internal structures

## Proposed Services

### 1. `DiscoveryCoordinator`

Responsibility:

- run backend discovery
- normalize raw sightings
- emit observation events

Inputs:

- discovery backend results
- probe responses

Outputs:

- `RendererSighting` events

Should not do:

- autoplay
- retries
- overlay start
- disconnect policy

### 2. `RendererRegistry`

Responsibility:

- canonical renderer identity
- current runtime state
- availability state machine

Owns:

- `renderer_id`
- stable metadata
- `last_seen_at`
- `last_control_success_at`
- `availability`
- recent observation history

Inputs:

- `RendererSighting`
- transport success/failure events
- operator override changes

Outputs:

- canonical runtime renderer state

### 3. `RendererStateStore`

Responsibility:

- persist renderer metadata and operator policy

Owns persisted fields:

- renderer identity binding
- user-facing label
- manual override state
- persisted preferences/config

Should stop persisting:

- transient discovery-loop state as if it were truth

### 4. `PlaybackIntentService`

Responsibility:

- desired media assignment state
- autoplay settings
- overlay auto-cast intent
- scheduling
- retry/backoff bookkeeping

Inputs:

- config changes
- frontend manual actions
- schedule rules

Outputs:

- desired renderer intent

### 5. `PlaybackOrchestrator`

Responsibility:

- compare desired state vs actual state
- decide start / stop / recover
- invoke streams and transport

Inputs:

- `RendererRegistry`
- `PlaybackIntentService`
- `StreamingHealthEvent`
- operator commands

Outputs:

- transport actions
- stream provisioning requests
- overlay cast session requests

### 6. `DLNATransport`

Responsibility:

- protocol actions only

Functions:

- `set_uri(...)`
- `play(...)`
- `pause(...)`
- `stop(...)`
- `seek(...)`
- `get_transport_info(...)`
- `get_position_info(...)`

Should not do:

- looping policy
- retry policy
- autoplay policy

### 7. `DeviceViewService`

Responsibility:

- assemble frontend-facing read models

Inputs:

- `RendererRegistry`
- `RendererStateStore`
- `PlaybackIntentService`
- overlay cast session service
- streaming diagnostics service

Outputs:

- device list DTO
- device detail DTO
- discovery summary DTO
- projection-target selection DTO
- diagnostics-friendly renderer summary DTO

This replaces the current ad hoc `DeviceService._device_to_dict()` pattern.

### 8. `DiagnosticsViewService`

Responsibility:

- compose streaming, overlay, and renderer health views for operator pages

Inputs:

- `StreamingSessionRegistry`
- `OverlayCastService`
- `RendererRegistry`

Outputs:

- streaming diagnostics DTOs
- overlay diagnostics DTOs

This keeps diagnostic pages from depending on raw internal registry/session structures directly.

## Pros And Cons

### Pros

- discovery no longer stalls on autoplay or overlay startup
- renderer availability becomes explainable and testable
- frontend gets clean stable DTOs
- DB intent survives restart without pretending to be live truth
- discovery-v2 can become authoritative cleanly
- overlay, playback, and stream health become composable instead of tangled

### Cons

- more explicit services and contracts
- migration will temporarily increase indirection
- some existing legacy convenience methods will become wrappers or shims
- identity migration away from friendly-name matching will require care

## High-Level Architecture

```text
Discovery Backends
    -> DiscoveryCoordinator
    -> RendererRegistry

RendererStateStore <-> PlaybackIntentService

RendererRegistry + PlaybackIntentService + StreamingHealth
    -> PlaybackOrchestrator
        -> StreamProvisioner
        -> DLNATransport
        -> OverlayCastService

RendererRegistry + RendererStateStore + Overlay/Streaming summaries
    -> DeviceViewService
        -> Frontend APIs
```

## Low-Level Design

## Proposed Core Data Structures

### `RendererSighting`

Inputs:

- backend name
- stable discovered identity
- hostname
- location
- action URL
- friendly name
- manufacturer
- seen timestamp
- capabilities

Output use:

- registry reconciliation only

### `RendererRuntimeState`

Fields:

- `renderer_id`
- `availability`
- `last_seen_at`
- `last_control_success_at`
- `last_control_error`
- `current_session_type`
- `is_playing`
- `current_media_ref`
- `overlay_cast_status`

### `RendererIntent`

Fields:

- `renderer_id`
- `desired_media_ref`
- `autoplay_enabled`
- `overlay_cast_enabled`
- `overlay_config_id`
- `schedule`
- `priority`
- `retry_policy`

### `DeviceListView`

Fields:

- persisted renderer metadata
- runtime availability summary
- manual override summary
- playback summary
- overlay summary
- streaming summary

## Proposed Class Structure

```text
runtime/
  discovery/
    coordinator.py
    sightings.py
  renderers/
    registry.py
    state_store.py
    availability.py
  playback/
    intent_service.py
    orchestrator.py
    stream_provisioner.py
  transport/
    dlna_transport.py
  views/
    device_view_service.py
```

## Function-Level Migration Map

### Move From `DeviceManager`

To `DiscoveryCoordinator`:

- `start_discovery()`
- `stop_discovery()`
- `_discovery_loop()`
- `_discover_dlna_devices()`

To `RendererRegistry`:

- `devices`
- `device_status`
- `last_seen`
- `device_connected_at`
- most of `update_device_status()`
- most of `_check_disconnected_devices()`

To `PlaybackIntentService`:

- `assigned_videos`
- `scheduled_assignments`
- `video_assignment_priority`
- `video_assignment_retries`
- overlay auto-cast intent lookup

To `PlaybackOrchestrator`:

- `_process_device_video_assignment()`
- `assign_video_to_device()`
- `_schedule_retry()`
- `_process_device_overlay_cast()`
- recovery decisions from `_handle_streaming_issue()`
- health-recovery decisions from `_playback_health_check_loop()`

To `DLNATransport`:

- transport-only pieces currently embedded in `DLNADevice`

To `DeviceViewService`:

- DTO assembly now living in `DeviceService._device_to_dict()`

## API Implications

### Keep

- existing device APIs for compatibility
- existing diagnostics endpoints during migration

### Change Behind The API

- routers should call `DeviceViewService` for reads
- routers should call `PlaybackIntentService` / `PlaybackOrchestrator` for actions
- discovery control should call `DiscoveryCoordinator`
- diagnostics routers should call `DiagnosticsViewService`

### discovery-v2

Before migration completes:

- reconcile router/manager API drift
- ensure one authoritative inventory path

## Migration Plan

### Phase 1. Freeze Legacy Scope

- do not add new behavior to `DeviceManager`
- fix discovery-v2 router/manager drift

### Phase 2. Introduce Registry And View Layer

- add `RendererRegistry`
- add `DeviceViewService`
- add `DiagnosticsViewService`
- make device list/detail APIs read from the new view layer
- leave frontend polling unchanged initially; swap backend owners behind existing endpoints

Current status:

- `DeviceViewService` is implemented
- `RendererRegistry` and `DiagnosticsViewService` are not implemented yet
- `RuntimeRegistryService` is implemented as the first live-state extraction, but `DeviceManager` still exposes compatibility properties

### Phase 3. Introduce Intent Layer

- add `PlaybackIntentService`
- move persisted autoplay / overlay intent ownership there

Current status:

- `PlaybackIntentService` is implemented for in-memory assignment/scheduling/retry ownership
- persisted intent ownership is not moved yet

### Phase 4. Introduce Orchestrator

- move autoplay and overlay start decisions out of the discovery loop
- emit intent-eligible events instead of executing actions inline

Current status:

- discovery now delegates decision logic through `PlaybackOrchestrator`
- execution still routes through existing `DeviceManager` methods
- the discovery loop still invokes orchestration inline; queue/event decoupling is not implemented yet
- discovery lifecycle and raw DLNA scan/reconciliation now route through `DiscoveryCoordinator`
- `DevicePlaybackService` is implemented for manual play/stop/pause/seek and playback-progress update flows that previously lived inline in `DeviceService`
- `DeviceDiscoveryService` is implemented for on-demand discovery, config-file load/save, and DB/runtime discovery reconciliation that previously lived inline in `DeviceService`
- `AppRuntime` now fronts discovery pause/resume/status as well as background service lifecycle
- `AppRuntime` now also fronts `DeviceService` construction and device inventory access for router/service call sites that previously reached directly into `DeviceManager`
- `AppRuntime` now exposes a small compatibility facade for common legacy runtime operations such as autoplay, device cleanup, and assigned-video lookup, which is allowing non-core consumers like brightness control and overlay cast fallback to stop depending on `DeviceManager` as their direct API
- that runtime facade now handles basic lifecycle/status/progress operations directly through extracted lifecycle and registry services rather than tunneling those calls back into the manager facade
- `DeviceViewService` has been narrowed to read-side dependencies only: runtime status map, device-state lock, connectivity timeout, and live-device lookup
- `DeviceRuntimeSyncService` now targets the runtime facade in production rather than `DeviceManager` directly, which further shrinks manager coupling on DB-to-runtime synchronization flows
- `DevicePlaybackService` and `DeviceDiscoveryService` now also target the runtime facade for the remaining runtime operations they need, which keeps the `DeviceService` subservices on a narrower compatibility surface
- production `DeviceService` construction now runs through `AppRuntime` rather than using `DeviceManager` as the primary constructor dependency, which makes the runtime bundle a more explicit composition root
- `DeviceService` itself no longer needs to retain a direct `DeviceManager` handle internally; it resolves runtime behavior through the runtime facade and uses a passed manager only to recover that bundle in compatibility cases
- `AppRuntime` now owns raw discovery invocation, config export, and LAN serve-IP resolution directly, removing another set of helper calls that previously just tunneled back into `DeviceManager`
- `AppRuntime` now also owns the discovery-v2 manager reference, and key consumers such as the discovery router, overlay cast service, and legacy discovery-ID resolution path now obtain unified discovery state from the runtime bundle rather than reaching straight for the singleton
- discovery-v2 `DiscoveryManager` now has compatibility methods for the checked router surface: `get_device(...)`, one-shot `discover_devices(...)`, `_register_enabled_backends()`, and `is_running`
- discovery-v2 session control compatibility is also tighter now: manager stop/pause/resume/seek/status lookups accept either a session ID or a device ID, which matches the existing router shape more safely
- backend registration is no longer duplicated between migration and v2 manager bootstrap paths: `DiscoveryMigrationAdapter` now uses the manager’s `register_enabled_backends()` path and can also consume the runtime-owned discovery manager directly
- `AppRuntime.start_background_services()` now primes unified-discovery backend registration before starting legacy discovery and the migration bridge, and the migration adapter only starts/stops unified discovery if it actually took ownership of that lifecycle
- unified discovery now has its own runtime-owned lifecycle service, so v2 backend discovery runs under an explicit `AppRuntime` boundary instead of implicitly piggybacking on the migration thread
- unified discovery lifecycle now also exposes pause/resume/status through that runtime-owned service, and `AppRuntime` dispatches the legacy `/api/devices/discovery/*` control surface to either the legacy coordinator or the unified lifecycle based on the configured discovery authority while preserving the existing frontend status payload shape
- the migration adapter is now sync-only with respect to unified discovery lifecycle; it no longer starts or stops discovery-v2 backends itself
- the old startup-time `DeviceManager.set_device_service(...)` injection path has been removed because runtime recovery/playback helpers now own that DB-backed behavior directly
- `AppRuntime` now exposes an explicit discovery authority mode (`legacy` vs `unified` via `NANODLNA_DISCOVERY_AUTHORITY`), and in unified mode the legacy discovery loop is not started while manual DLNA discovery requests are served through the unified discovery backend path
- in unified-authority mode the migration bridge no longer seeds discovery-v2 from legacy runtime devices or pushes legacy runtime status back into discovery-v2; it becomes a one-way compatibility feed from unified discovery into the old runtime surface
- the migration bridge now also subscribes to unified discovery events directly, so legacy compatibility state can be updated immediately from discovery-v2 callbacks instead of relying only on the periodic sync loop
- in unified-authority mode the bridge now does a one-time backfill from currently discovered v2 devices into the legacy runtime at startup and then relies on callbacks instead of the periodic sync loop
- in practice that means the migration thread is now one-shot in unified mode: it performs initial migration/backfill work and exits, leaving ongoing compatibility updates to unified discovery callbacks
- runtime playback, AirPlay handling, stalled-stream recovery, and the registered streaming health callback now live on `AppRuntime` rather than on `DeviceManager`
- startup now exports `AppRuntime` itself as the process-global compatibility surface, so callers that still refer to `device_manager` are actually hitting the runtime bundle first
- runtime autoplay now supports direct remote `http(s)` URL playback without tripping the local-file existence guard, which fixes the old AirPlay / overlay direct-URL failure mode
- runtime-owned device registration now binds newly registered core devices back to `AppRuntime` instead of the legacy manager object
- the discovery migration adapter now consumes the runtime contract directly for inventory, registration, status updates, and counts, instead of carrying a second fallback layer for a raw manager object
- `DeviceService` runtime normalization has been simplified so legacy call sites no longer preserve arbitrary manager identity; they either pass the runtime surface explicitly or resolve `get_app_runtime()`
- `AppRuntime` now captures its own steady-state lock/timeout values and legacy health-handler reference during composition, instead of reaching back into `DeviceManager` for those values during normal runtime operation
- renderer-service DLNA code paths that previously instantiated `DeviceService()` without dependencies and performed the wrong style of device lookup have been corrected to resolve runtime devices through the runtime composition root
- lower-level adapter paths such as `dlna_device` progress tracking and `twisted_streaming` device activity refresh are now also leaning on runtime helpers rather than reaching into `DeviceManager` directly

### Phase 5. Shrink Transport

- reduce `DLNADevice` to protocol concerns
- move loop/restart policy to orchestration/session monitoring

### Phase 6. Retire Legacy Discovery

- stop calling `DeviceManager.start_discovery()`
- feed registry only from discovery-v2
- remove `DiscoveryMigrationAdapter`

## Happy Case Workflow Diagram

### Happy Path: Auto-Play / Overlay-Cast Eligible Renderer Comes Online

```text
1. Discovery backend sees renderer
   -> DiscoveryCoordinator emits RendererSighting

2. RendererRegistry reconciles sighting
   -> renderer becomes ONLINE

3. PlaybackIntentService already has desired intent
   -> autoplay media or overlay auto-cast configured

4. PlaybackOrchestrator receives:
   - renderer ONLINE
   - desired intent present

5. PlaybackOrchestrator decides:
   - start media playback
   or
   - start overlay cast

6. Orchestrator calls:
   - StreamProvisioner
   - DLNATransport
   - OverlayCastService

7. Result events flow back:
   - control success/failure
   - stream session state
   - overlay session state

8. RendererRegistry updates actual runtime state

9. DeviceViewService assembles frontend DTOs

10. Frontend pages render:
    - device online
    - playing / casting
    - overlay status
    - stable availability summary
```

## Final Recommendation

The immediate design priority is not “replace all discovery code” in one shot.

It is:

1. stop executing autoplay and overlay actions inside the discovery loop
2. make renderer runtime state canonical and explicit
3. separate persisted intent from observed state
4. introduce a proper view service for frontend DTOs
5. only then retire the legacy loop and migration bridge

That sequence reduces risk while preserving current product behavior.
