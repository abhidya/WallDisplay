# Overlay, Discovery, Streaming, and Mapping UX Worklog

## Purpose

This document is the working brief for the next cleanup pass across backend and frontend. It captures:

- current product problems
- observed system behavior
- technical diagnosis
- target architecture
- phased implementation plan
- logging cleanup guidance
- a copy-paste prompt for continued work

## Lowest-Hanging Fruit

These are the cheapest fixes with immediate product value and low architectural risk.

### Completed in this pass

- `Mappings` readability cleanup:
  - moved to a softer, higher-contrast neutral palette
  - made editor sections explicitly collapsible
  - kept the stage-first layout intact
- stopped internal `overlay-mapping` stalled sessions from entering normal device-recovery logic
- fixed stream serving so mapping media-list items requested as `/uploads/<slug>` resolve correctly
- reduced `Renderer` page active-renderer polling from 5 seconds to 15 seconds and fixed interval cleanup
- reduced `Devices` and `DeviceDetail` polling from 5 seconds to 15 seconds
- added explicit streaming session metadata for `projection_stream` and `overlay_mapping_stream`
- added derived device availability fields (`online / degraded / offline`) in backend device serialization
- updated `Devices` and `DeviceDetail` to display derived availability, manager status, and last-seen/uptime signals instead of relying only on raw `device.status`
- updated `Devices` `Discovery Control` to summarize `online / degraded / offline`, active playback, and manual-override counts instead of showing only raw discovery counters
- added mapping-group support for `Saved Media Folder` bindings, including multi-folder selection, backed by `media_directories` and `videos.source_directory_id`
- collapsed stalled-session monitoring logs into per-pass summaries and reduced internal overlay cleanup chatter
- extended streaming diagnostics API to expose session ownership breakdowns by `stream_type` and `consumer_id` prefix
- added a frontend `Streaming Diagnostics` page to surface ownership, bandwidth, and stream-type health breakdowns
- added backend-managed overlay cast sessions using headless Chromium capture, FFmpeg MPEG-TS relay, and the existing DLNA discovery cast path
- added discovery-driven overlay auto-cast support keyed off persisted device config (`auto_overlay_cast_enabled` + `auto_overlay_config_id`)
- added device-detail projection health by joining active overlay cast session state with device seen/lost and transition counters
- split `Discovery Control` into an always-visible operator summary plus expandable diagnostics instead of mixing raw counters into the primary row
- surfaced projection session state and transition counters on device cards so operators can triage projector health from the list view
- reduced legacy `device_service` log noise by removing stray `print(...)` debugging and downgrading per-poll manager/discovery chatter to debug
- reduced repetitive legacy `device_manager` discovery/playback info logs so only actionable state changes remain at info level
- added actionable streaming diagnostics controls by allowing active registry sessions to be terminated from the diagnostics view
- expanded `Streaming Diagnostics` so it now explicitly shows overlay capture sessions and their FFmpeg speed/client metrics instead of implying the generic streaming registry is the whole picture
- added `Reset` controls in `Streaming Diagnostics` alongside `Terminate` for cheaper live-session cleanup
- added the first structured-lighting module scaffold:
  - backend session store
  - session CRUD routes
  - generated graycode capture-plan API
  - frontend page and nav entry for DLNA step-by-step calibration planning
- added structured-lighting status/summary surfacing:
  - backend `/api/structured-lighting/status`
  - worker-state placeholder
  - session/frame/time summary cards in the frontend
- added the first structured-lighting runtime/control path:
  - backend session start/runtime endpoints
  - worker heartbeat and next-step claim endpoints
  - capture upload endpoint
  - local worker script scaffold for host-side polling/heartbeat
- added real structured-lighting pattern asset generation:
  - backend step-image endpoint for reference and GrayCode frames
  - frontend current-step pattern preview
  - worker download path for current pattern image assets
- added direct polygon mask authoring in `Mappings`, allowing operators to click points on the stage and save new blackout masks as white-on-black scene PNGs without leaving the site
- worklog expanded into a more opinionated design brief

### Next low-risk wins

1. Push derived availability into more backend endpoints so it becomes the default status language.
2. Add device-scoped cleanup actions in streaming diagnostics rather than only per-session controls.
3. Replace the structured-lighting placeholder worker behavior with real camera capture, projector pattern presentation, and image validation before upload.

## Current Problems

### Discovery and device state

- Discovery loop is noisy and not trustworthy.
- Device `status`, `playing`, `uptime`, `downtime`, and `offline` behavior is inconsistent.
- A projector is not guaranteed to appear in every DLNA discovery pass, so "not seen once" must not mean "gone".
- `Discovery Control` UI is not usable.
- Device recovery logs show repeated attempts for synthetic device names like `overlay-mapping`, which should not be treated like a persistent real renderer.

### Stream management

- Streaming sessions for overlay mapping accumulate and get marked stalled repeatedly.
- Stream lifecycle is not cleanly tied to actual consumers.
- Stream recovery is too eager and too noisy.
- Overlay mapping streams appear as if they belong to a device, but `overlay-mapping` is not a real discovered device and should not go through normal renderer recovery logic.

### Overlay projection

- Overlay projection needs an automated cast path to DLNA projectors once discovered.
- This must tolerate projectors disappearing and reappearing from the discovery list.
- Projection launch should not assume the target projector is continuously discoverable.
- Projection automation should track availability and retry appropriately.

### Structured lighting / calibration

- The GrayCode capture and decode workflow has been validated in notebooks but is not yet productized.
- Pattern presentation over DLNA should advance one pattern at a time after the previous capture is complete.
- Camera capture remains host-side, but the website should own the session model, capture plan, and operator workflow.
- The first scaffold now exists, but it still lacks the host worker, actual pattern generation assets, capture upload flow, and decode/export pipeline.

### Mapping UI

- `Mappings` page color scheme is hard to read.
- Navigation areas are not collapsible enough for large scenes.
- The page still needs UX cleanup relative to the POC/editor expectations.

## Key Learnings From Recent Work

### Overlay window boot

- `overlay_window.html` can now bootstrap from `config_id`.
- Direct URL launch is valid and should remain supported.
- Save now persists to backend and should not depend on `window.opener`.

### Mapping rendering

- Mapping backgrounds are canvas-based and use luminance masks.
- Mapping groups now support media-list playback by sending `media_urls` and advancing client-side.
- Single resolved group media should loop indefinitely.
- Mapping groups can now also expand one or more saved media folders into a playlist by resolving all scanned videos linked to those folders.

### Media and streaming

- Stream URL normalization was not enough; stream serving had to resolve back to the original source file path.
- Mapping groups can use the same streaming infrastructure, but overlay-mapping streams should be treated as projection-session resources, not as device-owned streams.

### Validated projector casting prototype

The user has already validated a practical workaround for "DLNA cannot natively render arbitrary web overlays":

1. launch `overlay_window.html?config_id=<id>&controls=hidden`
2. open it in headless Chromium via Playwright
3. use CDP screencast frames
4. pipe frames into FFmpeg
5. encode to MPEG-TS / H.264
6. serve the TS stream locally over HTTP
7. send DLNA `SetAVTransportURI`
8. send DLNA `Play`

That means the product does not need to rely on the projector understanding browser content directly. Instead, it can treat overlay projection as a live rendered video feed and cast that feed over DLNA.

The validated prototype also includes an important operational cleanup step:

```bash
lsof -i tcp:8080 | awk 'NR!=1 {print $2}' | xargs kill -9 2>/dev/null
```

This is currently being used to clear stale local stream-server processes before starting a new cast session.

That cleanup behavior should be built into the eventual backend cast-session manager rather than left as a manual shell pre-step.

### Implemented overlay cast session manager

The first backend implementation is now in place:

- `POST /api/overlay/cast`
- `GET /api/overlay/cast/sessions`
- `DELETE /api/overlay/cast/sessions/{session_id}`

It currently:

1. builds `overlay_window.html?config_id=<id>&controls=hidden`
2. launches headless Chromium through Playwright
3. captures frames through CDP screencast
4. pipes them into FFmpeg
5. serves the encoded MPEG-TS output at `http://<local-ip>:<port>/live.ts`
6. reuses `DiscoveryManager.cast_content(...)` to hand that relay URL to the existing DLNA backend

This is intentionally integrated with the current discovery system instead of bypassing it with direct curl calls, so cast sessions remain visible through the same session model used by the rest of the discovery API.

### Implemented projector auto-cast hook

The first automatic rediscovery behavior is now in place in the legacy discovery loop:

- if a persisted device record has:
  - `config.auto_overlay_cast_enabled = true`
  - `config.auto_overlay_config_id = <overlay config id>`
- and the device is in `auto` control mode
- and discovery can match that renderer to a discovery-v2 DLNA device

then rediscovery will ensure that the configured overlay cast is started.

Current scope:

- it is device-config driven
- it restarts/replaces any existing overlay cast on the same target renderer
- it does not yet implement delayed retry intent after discovery loss
- it intentionally takes precedence over legacy auto-play for that device

### Current overlay cast limitations

- It is backend-only for now; there is no dedicated frontend control flow yet.
- It assumes Playwright is installed in the backend Python environment.
- It currently manages one cast session per target device and replaces any existing overlay cast on that device.
- It does not yet implement projector rediscovery retry or persistent cast intent after a device disappears.

## Diagnosis

### Discovery loop issue

The current discovery system appears to mix three separate concerns:

1. raw discovery events
2. persistent device state
3. operator-facing availability/status

That leads to unstable state transitions and log spam.

A projector that misses one or more discovery passes should move through a grace-period state model:

- `online`
- `degraded`
- `offline`

not directly from:

- `seen`
- `gone`

### Stream recovery issue

The repeated logs suggest the streaming registry is trying to recover sessions based on a `device_name` that does not map to a persistent registered device:

- `overlay-mapping`

That should likely be modeled separately:

- renderer/device-bound streams
- projection-session streams

Only renderer/device-bound streams should involve device recovery.

### Discovery Control issue

The current UI likely reflects raw polling results instead of a stable state model with:

- last seen
- last successful control action
- online/offline confidence
- current cast session
- retry/backoff state

Without those abstractions the UI will remain confusing.

## Completed Implementation Notes

### Frontend status model adoption

The frontend device views now consume the new derived backend fields:

- `availability`
- `derived_status`
- `manager_status`
- `seconds_since_seen`
- `uptime_seconds`
- `downtime_seconds`

This is intentionally an additive adoption step:

- backend discovery/device internals are unchanged
- frontend no longer presents raw connection state as if it were the only truth
- operator-facing screens now better reflect intermittent projector discovery behavior

This should be treated as the bridge state before a deeper Discovery Control redesign.

## Target Technical Design

### 1. Separate device state from discovery events

Introduce or enforce a device-state model that tracks:

- `device_id`
- `discovery_backend`
- `last_seen_at`
- `last_successful_control_at`
- `consecutive_missed_polls`
- `status`: `online | degraded | offline`
- `availability_confidence`
- `uptime_started_at`
- `downtime_started_at`
- `manual_override_state`

Rules:

- a single missed scan does not mark device offline
- status transitions should be threshold-based
- `uptime` and `downtime` should be derived from state transitions, not from noisy polling output

### 2. Split projector automation from generic discovery

Create a projector automation service that consumes stable device state rather than raw discovery output.

Suggested backend components:

- `ProjectorPresenceService`
- `ProjectorCastService`
- `ProjectionSessionManager`

Responsibilities:

- select target projector(s)
- maintain cast intent
- retry cast on rediscovery
- stop retrying when disabled by user
- expose stable session state to UI

### 2a. Discovery Control redesign proposal

`Discovery Control` should become an operations panel, not just a loop toggle with counters.

Status:

- initial summary-row conversion is now implemented in `Devices`
- raw discovery counters are still present, but demoted below derived health signals
- detailed diagnostics and retry controls are still pending

Recommended summary row:

- discovery loop state: `running | paused`
- healthy devices: count
- degraded devices: count
- offline devices: count
- active projection sessions: count
- active cast retries: count

Recommended details panel:

- last discovery pass timestamp
- last successful DLNA discovery timestamp
- last successful cast command timestamp
- devices currently in grace period
- devices offline beyond threshold
- retry queue / backoff state for projector automation

Recommended interactions:

- `Pause Discovery`
- `Resume Discovery`
- `Scan Now`
- `Retry Offline Projectors`
- `Expand Diagnostics`

Recommended UX rules:

- do not show raw discovery count as the primary signal
- prioritize device availability and cast readiness
- show degraded/offline states as grouped summaries first
- collapse verbose diagnostics by default

### 3. Distinguish stream types

Streams should be classified as:

- `device_stream`
- `projection_stream`
- `overlay_mapping_stream`

Projection and mapping streams should not trigger renderer/device recovery workflows.

Each stream/session should track:

- `stream_id`
- `stream_type`
- `source_path`
- `consumer_type`
- `consumer_id`
- `created_at`
- `last_read_at`
- `stalled_at`
- `status`

Cleanup policy:

- projection-window close should release projection streams
- stale mapping streams should expire without trying to recover a fake device

### 4. Automated DLNA casting for Overlay Projection

The system should support:

1. user selects overlay config
2. system resolves target projector
3. system launches overlay window URL with `controls=hidden`
4. system captures that URL into a castable transport stream
5. system sends `SetAVTransportURI` and `Play`
6. system monitors projector presence and cast health
7. on projector loss:
   - mark session degraded
   - keep intent active
   - retry on rediscovery

The Playwright + FFmpeg + lightweight HTTP server approach is a valid prototype direction for this.

Validated prototype shape:

- local overlay URL:
  - `http://127.0.0.1:3000/backend-static/overlay_window.html?config_id=2&controls=hidden`
- headless browser viewport:
  - `1920x1080`
- CDP screencast output:
  - JPEG frames
  - capped to `1280x720`
- FFmpeg output:
  - `mpegts`
  - H.264 baseline
- local relay URL:
  - `http://<local-ip>:8080/live.ts`
- DLNA control:
  - `SetAVTransportURI`
  - `Play`

Important production caveats:

- one cast session needs explicit port/session isolation
- subprocess lifecycle must be owned by a real service object
- retries need bounded backoff
- projector control actions need timeouts and structured result logging
- stale relay ports/processes must be cleaned up automatically
- the cast pipeline should expose health state:
  - browser alive
  - ffmpeg alive
  - stream server alive
  - projector transport command success/failure

### 4A. Proposed backend cast-service design

Convert the validated script into a managed backend service.

Suggested components:

- `OverlayCastSession`
  - in-memory/session record
  - owns browser, ffmpeg, HTTP relay, target projector metadata
- `OverlayCastService`
  - create/stop/restart cast sessions
  - allocate relay ports
  - generate overlay URL with `config_id` and `controls=hidden`
- `DlnaTransportClient`
  - send `SetAVTransportURI`
  - send `Play`
  - later: `Stop`, `Pause`, transport status polling

Suggested session state:

- `starting_browser`
- `starting_encoder`
- `starting_relay`
- `priming`
- `registering_transport`
- `playing`
- `degraded`
- `restarting`
- `stopped`
- `failed`

Suggested automatic cleanup behavior:

- if a new cast session needs a port that is already owned by a dead process, reclaim it
- do not rely on `kill -9` shell cleanup in production
- tie process cleanup to cast session teardown

### 4B. Prototype reference

This exact prototype shape has been demonstrated to work and should be treated as a first-class input to the implementation design:

```python
# Clean up
lsof -i tcp:8080 | awk 'NR!=1 {print $2}' | xargs kill -9 2>/dev/null

python3 -c "
import asyncio, subprocess, socket, threading, html, sys, time, base64
from playwright.async_api import async_playwright
from http.server import HTTPServer, BaseHTTPRequestHandler

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(('10.255.255.255', 1)); ip = s.getsockname()[0]
    except: ip = '127.0.0.1'
    finally: s.close()
    return ip

MY_IP = get_ip()
CONTROL_URL = 'http://10.0.0.154:49595/upnp/control/rendertransport1'
STREAM_URL = f'http://{MY_IP}:8080/live.ts'

class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'video/mpeg')
        self.end_headers()
        try:
            while True:
                data = self.server.ffmpeg_proc.stdout.read(65536)
                if not data: break
                self.wfile.write(data)
        except: pass

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width':1920,'height':1080})
        await page.goto('http://127.0.0.1:3000/backend-static/overlay_window.html?config_id=2&controls=hidden')

        ffmpeg_cmd = (
            'ffmpeg -y -f image2pipe -vcodec mjpeg -r 15 -i - '
            '-c:v h264_videotoolbox -b:v 2000k -pix_fmt yuv420p -color_range 2 '
            '-realtime 1 -profile:v baseline -level 4.1 '
            '-r 15 -g 30 -f mpegts -muxrate 2500k pipe:1'
        )
        proc = subprocess.Popen(ffmpeg_cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)

        server = HTTPServer(('0.0.0.0', 8080), StreamHandler)
        server.ffmpeg_proc = proc
        threading.Thread(target=server.serve_forever, daemon=True).start()

        cdp = await page.context.new_cdp_session(page)
        async def on_frame(event):
            try:
                proc.stdin.write(base64.b64decode(event['data']))
                proc.stdin.flush()
                await cdp.send('Page.screencastFrameAck', {'sessionId': event['sessionId']})
            except: pass

        cdp.on('Page.screencastFrame', lambda e: asyncio.create_task(on_frame(e)))

        await cdp.send('Page.startScreencast', {
            'format': 'jpeg',
            'quality': 30,
            'maxWidth': 1280,
            'maxHeight': 720,
            'everyNthFrame': 1
        })

        print('⏳ Priming...')
        await asyncio.sleep(5)

        print('🚀 REGISTERING...')
        meta = f'<DIDL-Lite xmlns=\"urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:upnp=\"urn:schemas-upnp-org:metadata-1-0/upnp/\"><item id=\"0\" parentID=\"-1\" restricted=\"1\"><dc:title>WallMapper</dc:title><upnp:class>object.item.videoItem</upnp:class><res protocolInfo=\"http-get:*:video/mpeg:DLNA.ORG_PN=MPEG_PS_PAL\">{STREAM_URL}</res></item></DIDL-Lite>'
        e_meta = html.escape(meta)
        s_uri = f'''<?xml version=\"1.0\" encoding=\"utf-8\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\"><s:Body><u:SetAVTransportURI xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\"><InstanceID>0</InstanceID><CurrentURI>{STREAM_URL}</CurrentURI><CurrentURIMetaData>{e_meta}</CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>'''
        subprocess.run(['curl', '-s', '-X', 'POST', '-H', 'SOAPACTION: \"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI\"', '-H', 'Content-Type: text/xml', '-d', s_uri, CONTROL_URL])

        await asyncio.sleep(2)
        print('🚀 PLAY...')
        s_play = '<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\"><s:Body><u:Play xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play></s:Body></s:Envelope>'
        subprocess.run(['curl', '-s', '-X', 'POST', '-H', 'SOAPACTION: \"urn:schemas-upnp-org:service:AVTransport:1#Play\"', '-H', 'Content-Type: text/xml', '-d', s_play, CONTROL_URL])

        print('✨ Hybrid Scale Mode: Check that speed stays >= 1.0x')
        while True:
            if proc.poll() is not None: break
            await asyncio.sleep(1)

asyncio.run(main())"
```

This should not remain as the final integration method, but it is now a proven path and should inform the real cast-service implementation directly.

### 5. Mapping UI cleanup

The `Mappings` page should be adjusted to:

- use a neutral, higher-contrast dark/light palette
- reduce saturated accent overload
- support explicit collapse/expand for:
  - scenes
  - mask library
  - groups
  - inspector sections
- preserve stage-first layout
- optimize for many masks/groups

## Design Proposals

### Proposal A: Device State Aggregator

Add one backend service whose only job is to convert discovery events into stable device state.

Suggested contract:

- input:
  - per-backend discovery sightings
  - control/action success/failure events
- output:
  - stable device state records used by UI and automation

Suggested rules:

- `online` after a successful recent sighting
- `degraded` after `N` missed polls or recent control failures
- `offline` after a longer threshold
- `playing` should come from confirmed cast/control state, not inferred from discovery presence

Why:

- this removes status logic from routers, discovery backends, and streaming recovery paths
- it makes `Discovery Control` and projector automation consume one source of truth

### Proposal B: Projection Session vs Device Stream Split

Introduce explicit stream ownership semantics.

Current anti-pattern:

- mapping/overlay helper streams are given pseudo-device identities
- stalled-stream recovery then tries to recover a physical device that does not exist

Proposed split:

- `device_stream`
  - owned by a discovered or registered renderer
  - eligible for device-recovery logic
- `projection_session_stream`
  - owned by an overlay/casting session
  - eligible for expiry/restart logic only

Why:

- this should eliminate a large amount of `overlay-mapping` recovery spam
- it clarifies cleanup responsibilities

### Proposal C: Projector Cast Intent Model

Persist cast intent separately from momentary projector availability.

Suggested fields:

- `session_id`
- `overlay_config_id`
- `target_device_fingerprint`
- `desired_state`: `active | paused | stopped`
- `actual_state`: `starting | casting | degraded | offline | failed`
- `last_cast_attempt_at`
- `last_cast_success_at`
- `retry_count`
- `failure_reason`

Why:

- the projector may disappear temporarily
- the system still needs to remember "keep trying to cast this overlay to that projector"

### Proposal D: Discovery Control UI Redesign

Replace raw renderer rows with stable cards.

Each card should show:

- display name
- backend/type
- online/degraded/offline
- last seen
- uptime or downtime
- current cast session
- manual/auto mode
- retry/backoff state

Actions:

- enable/disable automation
- target this projector for overlay cast
- clear stale session
- inspect logs

Why:

- current raw discovery output is too volatile to be useful operationally

### Proposal E: Logging Simplification

Move away from poll-by-poll logs and toward transition-based logs.

Implementation rules:

- do not log every successful `renderer/list` poll at `INFO`
- do not log every "0 devices found" pass at `INFO`
- summarize repeated stalled-stream recoveries into one event per cycle
- log state transitions once, with timestamps and reason

Example desired log lines:

- `Projector state changed: Hccast online -> degraded (missed_polls=3)`
- `Projection session started: session=abc config=2 device=Hccast`
- `Projection session retrying: session=abc backoff=15s reason=device_offline`
- `Projection session ended: session=abc duration=00:34:12`

## Immediate Backend Tasks

### Discovery and state

- audit discovery polling intervals and event fanout
- define stable device state transitions
- stop using raw discovery count as user-facing truth
- record `last_seen_at` and transition thresholds
- add projector uptime/downtime tracking

### Stream lifecycle

- audit `streaming_registry` stalled-session logic
- prevent device recovery attempts for synthetic names like `overlay-mapping`
- separate projection-session streams from device-owned streams
- add stream ownership and expiration rules
- reduce duplicate stream creation and stale-session churn

### Overlay automation

- add a projector cast orchestrator service
- persist desired target projector and cast intent
- trigger relaunch/recast when projector reappears
- expose cast session state via API

### Logging

- reduce repeated `renderer/list` and repetitive discovery spam
- collapse repeated stalled-session recovery logs into summarized events
- log state transitions instead of every poll
- move noisy per-poll detail to `DEBUG`

## Immediate Frontend Tasks

### Discovery Control

- redesign around stable device state, not raw scan output
- show:
  - online/degraded/offline
  - last seen
  - uptime/downtime
  - current cast target
  - retry state

### Overlay Projection

- add projector targeting and automated cast controls
- show whether a projector is:
  - discovered now
  - remembered but currently offline
  - being retried
  - actively casting

### Mappings

- revise palette for readability
- make nav/library/inspector sections explicitly collapsible
- keep the stage-primary interaction model

## Proposed Implementation Order

1. UI-only wins
   - finish Mappings readability/collapse cleanup
   - reduce frontend polling noise where trivial
2. Stream classification cleanup
   - stop overlay mapping sessions entering device recovery
3. Stable device-state service
   - centralize uptime/downtime/status derivation
4. Discovery Control redesign
   - consume stable device-state API
5. Projector cast orchestration
   - add cast intent/session manager
   - integrate overlay projection targeting
6. Logging cleanup
   - convert repetitive poll logs to summaries and transitions

## Logging Cleanup Guidance

We should prefer stateful, aggregated logging over repetitive poll logging.

### Bad examples from current logs

- repeated `GET /api/renderer/list`
- repeated `Discovered 0 DLNA devices`
- repeated recovery logs for each stalled overlay-mapping session

### Better logging shape

- `DLNA discovery summary: 2 devices online, 1 degraded, 0 offline`
- `Projector state changed: SideProjector online -> degraded`
- `Projection session retry scheduled: session=abc backoff=15s reason=device_offline`
- `Overlay mapping stream expired: session=xyz idle_for=120s`

### Suggested log levels

- `DEBUG`: per-poll raw discovery details
- `INFO`: state transitions, session starts/stops
- `WARNING`: repeated failed control attempts, projector degraded
- `ERROR`: unrecoverable cast startup failure, stream pipeline crash

## Prompt For Continued Work

Use this prompt for the next engineering pass:

> You are working in the `nano-dlna` repo. Focus on backend and frontend cleanup for discovery reliability, stream lifecycle, projector automation, and mapping UX. Do not redesign the product from scratch; extend the current architecture.
>
> Current problems:
> - device status/playing state is unreliable
> - Discovery Control UI is not usable
> - discovery loop and logging are noisy
> - overlay mapping streams are treated like real devices and trigger bad recovery behavior
> - projector presence is intermittent and must tolerate rediscovery
> - overlay projection needs automated DLNA casting to a discovered projector
> - mappings UI color contrast is poor and nav sections need collapsible controls
>
> Requirements:
> - separate raw discovery events from stable device state
> - add online/degraded/offline state with uptime/downtime tracking
> - split device-owned streams from projection-session streams
> - prevent synthetic overlay mapping streams from entering device recovery logic
> - add a projector cast orchestration path for overlay projection
> - support remembered projectors that may temporarily disappear from discovery
> - clean up logging to emphasize state transitions instead of poll spam
> - improve Mappings page readability and collapsibility without removing the stage-first editor layout
>
> Casting direction:
> - use the existing overlay projection URL and support automated casting through a managed backend service
> - a Playwright + FFmpeg + internal HTTP TS stream + DLNA `SetAVTransportURI`/`Play` pipeline is an acceptable starting point
> - productionize it with supervised subprocesses, retry/backoff, projector presence tracking, and structured session state
>
> Deliverables:
> 1. a short architecture/design summary
> 2. backend changes for device state, stream types, and projector cast orchestration
> 3. frontend changes for Discovery Control, Overlay Projection projector targeting, and Mappings UI cleanup
> 4. logging cleanup plan and implementation
> 5. validation notes and remaining risks
>
> Important repo context:
> - overlay window supports `config_id` bootstrap and direct save to backend
> - mappings use canvas-based luminance-mask rendering
> - mapping media lists now need real playlist-style handling
> - preserve existing overlay/video workflows where possible

## Working Checklist

- [ ] Audit discovery backends and polling cadence
- [ ] Document current device-state transition bugs
- [ ] Split stream ownership semantics
- [ ] Stop overlay-mapping sessions from hitting device recovery
- [ ] Add projector cast session model/service
- [ ] Prototype automated DLNA overlay cast path
- [ ] Redesign Discovery Control UI
- [ ] Improve Overlay Projection projector automation UI
- [ ] Clean up Mappings color palette
- [ ] Add explicit collapsible nav sections in Mappings
- [ ] Reduce discovery and streaming log spam
- [ ] Add validation/testing notes

## Notes

- The projector cast pipeline should be treated as session orchestration, not as a one-off utility script.
- A projector not appearing in a discovery pass is not sufficient proof that it is unavailable.
- Synthetic internal consumers like `overlay-mapping` should not be modeled as physical render devices.
