/* global Response */

import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_API_BASE_URL,
  NanoDlnaApiClient,
  normalizeApiBaseUrl,
} from '../src/services/api.ts';

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

function textResponse(body, init = {}) {
  return new Response(body, init);
}

function installFetchMock(responses) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  let index = 0;

  globalThis.fetch = async (input, init) => {
    calls.push({ input: String(input), init });
    const next = responses[index];
    index += 1;
    if (!next) {
      throw new Error(`Unexpected fetch call for ${String(input)}`);
    }
    return typeof next === 'function' ? next(input, init) : next;
  };

  return {
    calls,
    restore() {
      globalThis.fetch = originalFetch;
    },
  };
}

let activeMock = null;

afterEach(() => {
  activeMock?.restore();
  activeMock = null;
});

test('normalizeApiBaseUrl keeps the mobile client pinned to the shared /api base', () => {
  assert.equal(normalizeApiBaseUrl('http://127.0.0.1:8000'), 'http://127.0.0.1:8000/api');
  assert.equal(
    normalizeApiBaseUrl('https://demo.local/api/?foo=bar#hash'),
    'https://demo.local/api',
  );
  assert.equal(normalizeApiBaseUrl('/control-plane/'), '/control-plane/api');
  assert.equal(normalizeApiBaseUrl('backend.local:9000/base'), 'http://backend.local:9000/base/api');
  assert.equal(normalizeApiBaseUrl('   '), DEFAULT_API_BASE_URL);
});

test('NanoDlnaApiClient uses the shared FastAPI control-plane routes for operator actions', async () => {
  activeMock = installFetchMock([
    jsonResponse({ status: 'ok' }),
    jsonResponse([{ id: 1, friendly_name: 'Living Room' }]),
    jsonResponse({ success: true, message: 'Discovery queued' }),
    jsonResponse({ success: true, message: 'Manual mode enabled' }),
    jsonResponse({ success: true, message: 'Playback started' }),
    jsonResponse({ status: 'ok', affected_overlays: '1' }),
    jsonResponse({ session_id: 'projection-1' }),
  ]);

  const client = new NanoDlnaApiClient('http://controller.local:8000');

  await client.getHealth();
  await client.listDevices();
  await client.discoverDevices(9);
  await client.enableManualMode(7, { reason: 'operator override', expiresIn: 30 });
  await client.playVideoOnDevice(7, '12', { loop: true, syncOverlays: true });
  await client.triggerOverlaySync({ triggeredBy: 'mobile-smoke', videoName: 'demo.mp4' });
  await client.launchProjectionConfig(4);

  assert.deepEqual(
    activeMock.calls.map((call) => ({
      input: call.input,
      method: call.init?.method ?? 'GET',
      body: call.init?.body ?? null,
    })),
    [
      {
        input: 'http://controller.local:8000/health',
        method: 'GET',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/devices',
        method: 'GET',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/devices/discover?timeout=9',
        method: 'POST',
        body: null,
      },
      {
        input:
          'http://controller.local:8000/api/devices/7/control/manual?reason=operator%20override&expires_in=30',
        method: 'POST',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/devices/7/play?sync_overlays=true',
        method: 'POST',
        body: JSON.stringify({ video_id: 12, loop: true }),
      },
      {
        input:
          'http://controller.local:8000/api/overlay/sync?triggered_by=mobile-smoke&video_name=demo.mp4',
        method: 'POST',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/projection/configs/4/launch',
        method: 'POST',
        body: null,
      },
    ],
  );
});

test('NanoDlnaApiClient normalizes nested backend payloads into mobile-friendly arrays', async () => {
  activeMock = installFetchMock([
    jsonResponse({ devices: [{ id: 11, name: 'Kitchen' }] }),
    jsonResponse({
      chromecast: { active: true, enabled: true },
      airplay: { active: false, enabled: false },
    }),
    jsonResponse({ data: { renderers: [{ projector: 'alpha' }] } }),
    jsonResponse({ data: { projectors: [{ id: 'p-1', name: 'Front wall' }] } }),
    jsonResponse({ data: { scenes: [{ id: 'scene-1', name: 'Grid' }] } }),
    jsonResponse({ data: { projector_id: 'p-1', status: 'running' } }),
    jsonResponse({ data: { devices: [{ id: 'air-1', name: 'Apple TV' }] } }),
    jsonResponse({ data: { devices: [{ id: 'air-2', name: 'Living Room' }] } }),
    jsonResponse({ data: { devices: [{ id: 'air-3', name: 'Combined' }] } }),
    jsonResponse({ photos: [{ id: 3, name: 'Poster' }] }),
    jsonResponse([{ id: 8, name: 'Main list' }]),
    jsonResponse({ status: 'healthy', health_score: 100 }),
    jsonResponse([{ session_id: 'cast-1', active_clients: 2 }]),
  ]);

  const client = new NanoDlnaApiClient('http://controller.local:8000/api');

  assert.deepEqual(await client.listDevices(), [{ id: 11, name: 'Kitchen' }]);
  assert.deepEqual(await client.listDiscoveryBackends(), [
    { name: 'chromecast', active: true, enabled: true },
    { name: 'airplay', active: false, enabled: false },
  ]);
  assert.deepEqual(await client.listRenderers(), [{ projector: 'alpha' }]);
  assert.deepEqual(await client.listProjectors(), [{ id: 'p-1', name: 'Front wall' }]);
  assert.deepEqual(await client.listRendererScenes(), [{ id: 'scene-1', name: 'Grid' }]);
  assert.deepEqual(await client.getRendererStatus('p-1'), { projector_id: 'p-1', status: 'running' });
  assert.deepEqual(await client.discoverAirPlayDevices(), { devices: [{ id: 'air-1', name: 'Apple TV' }] });
  assert.deepEqual(await client.listAirPlayDevices(), { devices: [{ id: 'air-2', name: 'Living Room' }] });
  assert.deepEqual(await client.getAllAirPlayDevices(), { devices: [{ id: 'air-3', name: 'Combined' }] });
  assert.deepEqual(await client.listPhotos(), [{ id: 3, name: 'Poster' }]);
  assert.deepEqual(await client.listMediaLists(), [{ id: 8, name: 'Main list' }]);
  assert.deepEqual(await client.getStreamingHealth(), { status: 'healthy', health_score: 100 });
  assert.deepEqual(await client.listOverlayCastSessions(), [{ session_id: 'cast-1', active_clients: 2 }]);
});

test('NanoDlnaApiClient surfaces backend error payloads for operator diagnostics', async () => {
  activeMock = installFetchMock([
    textResponse('backend unavailable', {
      status: 503,
      statusText: 'Service Unavailable',
    }),
  ]);

  const client = new NanoDlnaApiClient('http://controller.local:8000/api');

  await assert.rejects(
    client.getStreamingAnalytics(),
    /503 Service Unavailable - backend unavailable/,
  );
});

test('NanoDlnaApiClient lifts logs and advanced feature routes onto the shared client', async () => {
  activeMock = installFetchMock([
    jsonResponse({ logs: [] }),
    jsonResponse({ id: 9, name: 'demo-overlay' }),
    jsonResponse({ animations: [] }),
    jsonResponse({ session_id: 'sess-1', status: 'idle' }),
    jsonResponse({ status: 'ok' }),
    jsonResponse({ config_id: 'proj-1' }),
  ]);

  const client = new NanoDlnaApiClient('http://controller.local:8000');

  await client.getLogs({ source: 'frontend', limit: 20 });
  await client.createOverlayConfig({ name: 'demo-overlay' });
  await client.listProjectionAnimations();
  await client.getStructuredLightingRuntime('sess-1');
  await client.segmentDepthMap('depth-1', { method: 'kmeans' });
  await client.createDepthProjection({ name: 'depth-projection' });

  assert.equal(
    client.getDepthPreviewUrl('depth-1'),
    'http://controller.local:8000/api/depth/preview/depth-1',
  );
  assert.equal(
    client.getDepthProjectionUrl('cfg-1'),
    'http://controller.local:8000/api/depth/projection/cfg-1',
  );

  assert.deepEqual(
    activeMock.calls.map((call) => ({
      input: call.input,
      method: call.init?.method ?? 'GET',
      body: call.init?.body ?? null,
    })),
    [
      {
        input: 'http://controller.local:8000/api/logs?source=frontend&limit=20',
        method: 'GET',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/overlay/configs',
        method: 'POST',
        body: JSON.stringify({ name: 'demo-overlay' }),
      },
      {
        input: 'http://controller.local:8000/api/projection/animations',
        method: 'GET',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/structured-lighting/sessions/sess-1/runtime',
        method: 'GET',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/depth/segment/depth-1',
        method: 'POST',
        body: JSON.stringify({ method: 'kmeans' }),
      },
      {
        input: 'http://controller.local:8000/api/depth/projection/create',
        method: 'POST',
        body: JSON.stringify({ name: 'depth-projection' }),
      },
    ],
  );
});

test('NanoDlnaApiClient preserves structured-lighting and depth route contracts for heavier workflows', async () => {
  activeMock = installFetchMock([
    jsonResponse({ worker: { status: 'idle' } }),
    jsonResponse([{ session_id: 'sess-1' }]),
    jsonResponse({ session: { session_id: 'sess-1' } }),
    jsonResponse([{ capture_id: 'cap-1' }]),
    jsonResponse({ session_id: 'sess-2' }),
    jsonResponse({ ok: true }),
    jsonResponse({ ok: true }),
    jsonResponse({ depth_id: 'depth-1' }),
    jsonResponse({ segments: [1, 2] }),
    jsonResponse({ config_id: 'cfg-1' }),
    jsonResponse({ ok: true }),
  ]);

  const client = new NanoDlnaApiClient('http://controller.local:8000');
  const formData = new FormData();
  formData.append('file', new Blob(['depth']), 'depth.png');

  assert.deepEqual(await client.getStructuredLightingStatus(), { worker: { status: 'idle' } });
  assert.deepEqual(await client.listStructuredLightingSessions(), [{ session_id: 'sess-1' }]);
  assert.deepEqual(await client.getStructuredLightingRuntime('sess-1'), {
    session: { session_id: 'sess-1' },
  });
  assert.deepEqual(await client.listStructuredLightingCaptures('sess-1'), [{ capture_id: 'cap-1' }]);
  assert.deepEqual(await client.createStructuredLightingSession({ name: 'Calibration' }), {
    session_id: 'sess-2',
  });
  assert.deepEqual(await client.startStructuredLightingSession('sess-2'), { ok: true });
  assert.deepEqual(await client.deleteStructuredLightingSession('sess-2'), { ok: true });
  assert.deepEqual(await client.uploadDepthMap(formData), { depth_id: 'depth-1' });
  assert.deepEqual(await client.segmentDepthMap('depth-1', { method: 'kmeans' }), {
    segments: [1, 2],
  });
  assert.deepEqual(await client.createDepthProjection({ name: 'Projection' }), {
    config_id: 'cfg-1',
  });
  assert.deepEqual(await client.deleteDepthMap('depth-1'), { ok: true });
  assert.equal(
    client.getDepthSegmentationPreviewUrl('depth-1', 0.75),
    'http://controller.local:8000/api/depth/segmentation_preview/depth-1?alpha=0.75',
  );

  assert.deepEqual(
    activeMock.calls.map((call) => ({
      input: call.input,
      method: call.init?.method ?? 'GET',
      bodyKind: call.init?.body instanceof FormData ? 'form-data' : call.init?.body ?? null,
    })),
    [
      {
        input: 'http://controller.local:8000/api/structured-lighting/status',
        method: 'GET',
        bodyKind: null,
      },
      {
        input: 'http://controller.local:8000/api/structured-lighting/sessions',
        method: 'GET',
        bodyKind: null,
      },
      {
        input: 'http://controller.local:8000/api/structured-lighting/sessions/sess-1/runtime',
        method: 'GET',
        bodyKind: null,
      },
      {
        input: 'http://controller.local:8000/api/structured-lighting/sessions/sess-1/captures',
        method: 'GET',
        bodyKind: null,
      },
      {
        input: 'http://controller.local:8000/api/structured-lighting/sessions',
        method: 'POST',
        bodyKind: JSON.stringify({ name: 'Calibration' }),
      },
      {
        input: 'http://controller.local:8000/api/structured-lighting/sessions/sess-2/start',
        method: 'POST',
        bodyKind: null,
      },
      {
        input: 'http://controller.local:8000/api/structured-lighting/sessions/sess-2',
        method: 'DELETE',
        bodyKind: null,
      },
      {
        input: 'http://controller.local:8000/api/depth/upload',
        method: 'POST',
        bodyKind: 'form-data',
      },
      {
        input: 'http://controller.local:8000/api/depth/segment/depth-1',
        method: 'POST',
        bodyKind: JSON.stringify({ method: 'kmeans' }),
      },
      {
        input: 'http://controller.local:8000/api/depth/projection/create',
        method: 'POST',
        bodyKind: JSON.stringify({ name: 'Projection' }),
      },
      {
        input: 'http://controller.local:8000/api/depth/depth-1',
        method: 'DELETE',
        bodyKind: null,
      },
    ],
  );
});
