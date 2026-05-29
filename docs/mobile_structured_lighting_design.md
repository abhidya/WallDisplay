# Mobile Structured Lighting Design

## Purpose

Build structured-lighting capture into the Expo mobile app without losing the existing FastAPI backend workflow. Today the mobile app exposes structured lighting only as a remote operator console. This design defines a staged path for making mobile a first-class capture client, then optionally moving heavier decode/calibration work on-device.

## Current State

### Mobile app

Evidence:

- `mobile-app/App.tsx` renders `StructuredLightingScreen` on the `lighting` tab.
- `mobile-app/src/screens/StructuredLightingScreen.tsx` provides a remote structured-lighting operator UI.
- `mobile-app/src/features/lighting/useStructuredLightingController.ts` creates/list/starts/deletes sessions through remote backend APIs.
- `mobile-app/src/services/api.ts` already wraps many `/api/structured-lighting/...` endpoints.
- `mobile-app/src/control-plane/client.ts` marks local structured-lighting methods as deferred.
- `mobile-app/src/data/features.ts` describes structured lighting as remote-only.

Conclusion: mobile has remote control-plane coverage, not native capture/decode execution.

### Backend

Evidence:

- `web/backend/routers/structured_lighting_router.py` exposes session, capture-plan, runtime, capture upload, decode, tuning, review, publish, worker, and artifact endpoints.
- `web/backend/services/structured_lighting_service.py` owns session persistence, pattern/capture artifacts, decode/tuning/review/export/publish workflow.
- `web/backend/structured_lighting_worker.py` is an OpenCV host-side worker that opens a camera, polls backend worker steps, presents/captures patterns, and uploads frames.

Conclusion: backend already owns the core workflow. The mobile feature should reuse this contract first.

## Goals

1. Add mobile-native structured-lighting capture orchestration.
2. Let phone camera capture projected pattern frames.
3. Reuse existing backend endpoints for session management, pattern plan, upload, decode, tuning, review, export, and publish.
4. Preserve local/remote mode semantics:
   - remote mode: talk to FastAPI backend.
   - local mode: store explicit deferred capability until local decode is intentionally built.
5. Keep mobile UX safe and guided: permissions, camera framing, exposure lock, progress, retry, resume.

## Non-goals for MVP

- Full projector/camera calibration decode on device.
- Replacing backend `StructuredLightingService`.
- Building full OpenCV native decode inside Expo managed app.
- Guaranteeing automatic projector control for every TV/cast target.
- Shipping production-grade multi-device sync in first pass.

## Product Scope

### MVP: mobile capture client, backend decode

Mobile should:

1. Connect to backend in remote mode.
2. Create/select structured-lighting session.
3. Fetch capture plan from `/api/structured-lighting/sessions/{session_id}/capture-plan`.
4. Guide operator through camera permission and framing.
5. For each step:
   - request backend/projector to present pattern, or show operator prompt if manual presentation is required.
   - wait configured settle time.
   - capture image from phone camera.
   - upload image to `/api/structured-lighting/sessions/{session_id}/captures` with `step_index`.
   - mark local progress.
6. Show session runtime and capture count.
7. Trigger backend decode/tuning/review/publish using existing API methods.
8. Resume interrupted sessions by comparing capture plan with existing captures.

### Phase 2: mobile-assisted projector presentation

Add pattern presentation options:

- Backend DLNA step presentation remains preferred for TV/projector targets.
- Mobile displays pattern full-screen if the phone itself is the projector/screen source.
- Optional WebView/cast target mode if backend exposes a browser-accessible pattern presenter.

### Phase 3: on-device decode experiment

Only after MVP works:

- Add custom native module or development build.
- Evaluate `react-native-vision-camera` frame processors + OpenCV/native libraries.
- Port only the smallest decode path first.
- Keep backend decode as canonical fallback.

## Architecture

```text
Mobile Structured Lighting Screen
  ├─ useStructuredLightingController (existing remote session control)
  ├─ useStructuredLightingCaptureController (new capture flow)
  │   ├─ permissions/camera state
  │   ├─ capture plan state
  │   ├─ capture progress/resume state
  │   ├─ step runner state machine
  │   └─ upload/retry queue
  ├─ CameraCaptureView (new)
  ├─ CaptureStepProgressPanel (new)
  └─ DecodeReviewPanel (new or existing service calls)

FastAPI backend
  ├─ /api/structured-lighting/sessions
  ├─ /api/structured-lighting/sessions/{id}/capture-plan
  ├─ /api/structured-lighting/sessions/{id}/captures
  ├─ /api/structured-lighting/sessions/{id}/decode
  ├─ /api/structured-lighting/sessions/{id}/preview-tuning
  ├─ /api/structured-lighting/sessions/{id}/tuning-search
  ├─ /api/structured-lighting/sessions/{id}/review
  └─ /api/structured-lighting/sessions/{id}/publish-mapping-scene
```

## Recommended Dependencies

Prefer Expo-compatible dependencies for MVP:

- `expo-camera` for camera permission and still capture.
- `expo-file-system` for local capture staging and resume cache.
- Existing app HTTP client for upload calls.

Avoid for MVP:

- OpenCV native bindings.
- Vision-camera frame processors.
- New cast SDKs.

Reason: current app appears Expo-oriented; full native CV forces custom dev client/native build and increases implementation risk.

## API Contract Needed in Mobile

Existing `mobile-app/src/services/api.ts` already has many methods. The MVP needs to ensure these are exposed through `ControlPlaneClient` and used by the capture controller:

- `getStructuredLightingCapabilities()`
- `getStructuredLightingStatus()`
- `listStructuredLightingSessions()`
- `createStructuredLightingSession(payload)`
- `getStructuredLightingRuntime(sessionId)`
- `listStructuredLightingCaptures(sessionId)`
- `getStructuredLightingCapturePlan(sessionId)` if not already exposed by high-level client
- `getStructuredLightingStepImageUrl(sessionId, stepIndex)`
- `uploadStructuredLightingCapture(sessionId, formData)`
- `decodeStructuredLightingSession(sessionId, payload)`
- `runStructuredLightingPreviewTuning(sessionId, payload)`
- `runStructuredLightingTuningSearch(sessionId, payload)`
- `getStructuredLightingArtifactReview(sessionId)`
- `updateStructuredLightingReview(sessionId, payload)`
- `publishStructuredLightingMappingScene(sessionId, payload)`

If `getCapturePlan` only exists under `structuredLightingApi`, add a `ControlPlaneClient` method for consistency.

## Capture State Machine

```text
idle
  -> loadingPlan
  -> requestingCameraPermission
  -> framing
  -> ready
  -> presentingStep
  -> settling
  -> capturing
  -> uploading
  -> stepComplete
  -> presentingStep ... until done
  -> readyToDecode
  -> decoding
  -> review
  -> published
```

Failure states:

- `permissionDenied`
- `backendUnavailable`
- `projectorUnavailable`
- `captureFailed`
- `uploadFailed`
- `decodeFailed`
- `cancelled`

Each failure should support retry where safe.

## Mobile UX Detail

### Session panel

- Show sessions, selected session, worker/backend status, capture count.
- Add actions:
  - Create session
  - Load capture plan
  - Start mobile capture
  - Resume capture
  - Decode session
  - Review artifacts
  - Publish mapping scene

### Camera/framing screen

- Request camera permission.
- Show live camera preview.
- Show target instructions:
  - “Place projected area fully in frame.”
  - “Avoid motion.”
  - “Dim room lights if possible.”
  - “Lock exposure if supported.”
- Confirm framing before first capture.

### Step runner

- Progress: `current / total`.
- Current step image preview if helpful.
- Countdown for settle time.
- Capture/upload status.
- Retry current step.
- Skip not recommended; require warning if exposed.

### Review screen

- Show decode status.
- Show backend artifact preview URLs.
- Let user mark `accepted` or `needs_recapture`.
- Offer publish action after accepted review.

## Implementation Plan

### Step 1: API surface cleanup

Files:

- `mobile-app/src/control-plane/client.ts`
- `mobile-app/src/services/api.ts`
- `mobile-app/tests/api-client.test.mjs`
- `mobile-app/tests/control-plane.test.mjs`

Tasks:

1. Add/confirm `getStructuredLightingCapturePlan(sessionId)` on `ControlPlaneClient`.
2. Confirm upload method accepts mobile `FormData` with:
   - `step_index`
   - `capture` image file/blob
3. Add tests for route strings and payload shapes.
4. Keep local-mode methods deferred with explicit messages.

### Step 2: capture controller

Files:

- new: `mobile-app/src/features/lighting/useStructuredLightingCaptureController.ts`
- update: `mobile-app/src/features/lighting/useStructuredLightingController.ts`
- new tests under `mobile-app/tests/`

Tasks:

1. Add state machine and reducer.
2. Load capture plan.
3. Compare existing captures with plan for resume.
4. Build `start`, `pause/cancel`, `retryStep`, `resume` actions.
5. Stage captures locally before upload.
6. Add upload retry with bounded attempts.
7. Expose progress and errors to screen.

### Step 3: camera capture component

Files:

- new: `mobile-app/src/components/StructuredLightingCamera.tsx`
- update: `mobile-app/src/screens/StructuredLightingScreen.tsx`

Tasks:

1. Add `expo-camera` integration.
2. Request permissions.
3. Render preview.
4. Capture still image for active step.
5. Return local URI/blob metadata to capture controller.
6. Add platform-safe fallback for web/test mode.

### Step 4: screen integration

Files:

- `mobile-app/src/screens/StructuredLightingScreen.tsx`

Tasks:

1. Keep current remote operator console.
2. Add “Mobile capture” panel in remote mode.
3. Add capture plan/progress UI.
4. Add camera preview/framing UI.
5. Add decode/review/publish actions.
6. Keep local mode explicit deferred message unless local implementation is chosen.

### Step 5: tests

Files:

- new/updated `mobile-app/tests/*structured-lighting*.test.mjs`

Test cases:

1. Remote client calls capture-plan endpoint.
2. Upload builds correct multipart request.
3. Capture controller loads plan and starts at first missing capture.
4. Resume skips already uploaded captures.
5. Capture failure leaves current step retryable.
6. Local mode returns deferred and does not start camera flow.
7. Decode/review/publish actions call expected endpoints.

### Step 6: manual verification

1. Start FastAPI backend.
2. Start mobile app in remote mode.
3. Create structured-lighting session.
4. Load capture plan.
5. Grant camera permission.
6. Capture first 2-3 steps against real projected patterns or test pattern source.
7. Verify captures appear in backend session artifacts.
8. Run decode on a full capture set.
9. Review/publish if decode output is valid.

## Pros

### Backend-decode MVP

- Reuses existing FastAPI and OpenCV code.
- Lowest native mobile risk.
- Faster delivery.
- Keeps current web/desktop worker workflow intact.
- Easier to test route contracts.
- Works on Expo with minimal native changes.
- Lets mobile become useful quickly as camera/capture operator.

### Mobile-native capture

- Phone camera is widely available.
- Operator can walk to projection area and frame manually.
- Reduces need for host machine webcam setup.
- Better UX for capture guidance and retry.

### Staged architecture

- Clear upgrade path to on-device decode.
- Backend remains canonical fallback.
- Each phase is independently shippable.

## Cons

### Backend-decode MVP

- Requires backend running on reachable LAN URL.
- Not fully offline/local.
- Uploading many images can be slow.
- Decode latency remains server-side.

### Mobile camera capture

- Camera exposure/focus/white balance can vary per frame.
- Phone movement can break capture alignment.
- Need careful UX for tripod/stability guidance.
- Different iOS/Android camera APIs may behave differently.

### Projector presentation

- Phone cannot universally control every TV/projector.
- DLNA/AirPlay/Cast availability varies.
- Manual presentation fallback can desync capture if operator advances incorrectly.

### On-device decode later

- Requires native modules/custom dev client.
- OpenCV packaging is heavy.
- Performance and memory risks on older devices.
- More test matrix complexity.

## Major Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Projector/camera desync | Bad decode | Backend-owned capture plan, explicit step progress, settle countdown, retry current step |
| Auto exposure changes | Inconsistent frames | Lock exposure/focus where possible; warn operator; add recapture flow |
| Backend unreachable | Feature unusable | Clear remote URL checks; show connectivity errors; keep local deferred copy explicit |
| Multipart upload mismatch | Captures rejected | Add route contract tests; test upload from mobile runtime |
| Large capture set storage | Disk/network overhead | Compress JPEG/PNG intentionally; clean local staged files after upload |
| Expo camera limitations | Feature blocked | Keep camera wrapper isolated; allow migration to custom native camera later |

## Data Model Notes

Mobile local state should store only transient/resume data:

```ts
interface MobileStructuredLightingCaptureState {
  sessionId: string;
  planVersion?: string;
  steps: Array<{
    index: number;
    imageUrl?: string;
    status: 'pending' | 'presenting' | 'captured' | 'uploaded' | 'failed';
    localUri?: string;
    uploadedAt?: string;
    error?: string;
  }>;
  currentStepIndex?: number;
  startedAt?: string;
  updatedAt?: string;
}
```

Backend remains source of truth for sessions, captures, decode artifacts, review, and published mapping scenes.

## Acceptance Criteria

MVP complete when:

1. Mobile remote mode can create/select structured-lighting sessions.
2. Mobile can load capture plan for selected session.
3. Mobile can request camera permission and capture frames per step.
4. Mobile uploads captures to backend with correct `step_index`.
5. Mobile can resume after interruption without duplicating completed captures.
6. Mobile can trigger backend decode and show result/error.
7. Mobile local mode remains explicit deferred, not silently broken.
8. Automated tests cover route contracts and capture controller state transitions.

## Suggested “New Context” Implementation Prompt

Use this prompt for a fresh coding context:

```text
Implement the MVP from docs/mobile_structured_lighting_design.md.

Scope:
- Build mobile structured-lighting capture client using backend decode.
- Keep local mode deferred.
- Do not add OpenCV/native decode.
- Prefer Expo-compatible camera/file APIs.

Primary files:
- mobile-app/src/control-plane/client.ts
- mobile-app/src/services/api.ts
- mobile-app/src/features/lighting/useStructuredLightingController.ts
- mobile-app/src/screens/StructuredLightingScreen.tsx
- new mobile-app/src/features/lighting/useStructuredLightingCaptureController.ts
- new mobile-app/src/components/StructuredLightingCamera.tsx
- mobile-app/tests/*.test.mjs

Requirements:
1. Add/verify getStructuredLightingCapturePlan(sessionId) in ControlPlaneClient.
2. Add capture state machine with load plan, start, retry, resume, upload.
3. Add camera capture UI with permission handling.
4. Upload each frame to /api/structured-lighting/sessions/{session_id}/captures as multipart form data with step_index.
5. Add decode/review/publish actions if missing from screen.
6. Add tests for API route contracts and capture state machine.
7. Run mobile tests and report evidence.

Constraints:
- No new heavy native CV dependency.
- Keep existing remote operator behavior working.
- Keep local mode explicitly deferred.
- Reuse existing API/http/client patterns.
```

## Open Questions for Implementation Context

These do not block the design, but implementation should decide/verify:

1. Is `expo-camera` already installed in `mobile-app/package.json`; if not, add only if acceptable for the project.
2. Does the backend capture upload endpoint accept `step_index` as multipart form field from React Native `FormData` exactly as sent?
3. Should captured images be PNG for fidelity or JPEG for speed?
4. Can backend present DLNA steps automatically for each capture, or should mobile only capture while backend/worker handles presentation?
5. Should mobile support manual “I see the pattern” confirmation before each capture?

## Implementation Slice Added In This Context

The first low-risk MVP slice now exists in the mobile app:

- API seam: `getStructuredLightingCapturePlan(sessionId)` is exposed through `NanoDlnaApiClient` and `ControlPlaneClient`.
- Capture state: `structuredLightingCapture.ts` normalizes backend plans, tracks captured/uploaded/failed steps, and builds multipart upload form data with `step_index`.
- Mobile UI: `StructuredLightingScreen` can load capture plans, upload a local image URI per step, trigger decode, and publish a mapping scene.
- Camera bridge: `StructuredLightingCamera` is dependency-free for now. It accepts a device/file URI and uploads it. A future `expo-camera` replacement can keep the same `onUploadStep(stepIndex, uri)` boundary.
- Tests: route contract and capture state-machine tests cover this slice.

### Follow-up For Full Camera UX

Add `expo-camera` only when the project accepts a new Expo dependency. Then replace the URI input in `StructuredLightingCamera` with permission handling and a native capture button while preserving the controller/state-machine boundary.

## Native Camera Dependency Slice

The mobile MVP now explicitly includes Expo camera support:

- `expo-camera` is installed for `CameraView`, `useCameraPermissions`, and `takePictureAsync`.
- `expo-file-system` is installed so captured cache files can be promoted or managed in a later persistence slice if needed.
- `app.json` declares iOS camera usage text, Android camera permission, and the `expo-camera` config plugin.
- `StructuredLightingCamera` now renders a live camera preview, requests permission, captures the selected plan step, and uploads the captured file URI through the existing capture controller.
- The manual URI fallback remains for simulator/web/no-camera cases.

Verification after this slice:

- `npm run typecheck` passes in `mobile-app`.
- `npm test` passes in `mobile-app` with 36 tests.

## Native Camera Hardening Slice

Follow-up hardening after adding `expo-camera`:

- The selected capture step now follows the controller's current step, so the UI advances after successful upload.
- Camera mount/capture errors render as errors instead of being copied into the URI fallback field.
- Capture upload filenames now preserve the camera cache basename when available and fall back to `structured-lighting-step-{index}.jpg`.
- Regression tests cover capture filename normalization.

## Capture File Persistence Slice

The camera capture path now uses both explicitly approved Expo dependencies:

- `expo-camera` captures the selected step.
- `expo-file-system` copies temporary camera cache files into `Paths.cache/structured-lighting/{sessionId}/` with stable sanitized names before upload.
- The upload still uses the same controller boundary, so backend API behavior did not change.
- Config/dependency tests now lock camera permissions and Expo dependency declarations.
- Web export was verified with `npx expo export --platform web --output-dir /tmp/nano-dlna-mobile-export`.
