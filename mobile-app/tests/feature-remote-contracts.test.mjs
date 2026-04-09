/* global Response */

import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';

import {
  createHttpClient,
  normalizeApiBaseUrl,
} from '../src/services/httpClient.ts';

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

function blobResponse(body, init = {}) {
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'application/octet-stream' },
    ...init,
  });
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

function createLogsRemoteClient(apiBaseUrl, fetchImpl = globalThis.fetch) {
  const api = createHttpClient({
    baseURL: normalizeApiBaseUrl(apiBaseUrl),
    normalizeApiBase: false,
    fetchImpl,
  });

  return {
    getLevels: () => api.get('/logs/levels'),
    getLogs: (params = {}) => api.get('/logs', { query: params }),
    getSources: () => api.get('/logs/sources'),
    getStats: () => api.get('/logs/stats'),
    tailSource: (source, lines = 50) =>
      api.get(`/logs/tail/${encodeURIComponent(source)}`, { query: { lines } }),
  };
}

function createProjectionRemoteClient(apiBaseUrl, fetchImpl = globalThis.fetch) {
  const api = createHttpClient({
    baseURL: normalizeApiBaseUrl(apiBaseUrl),
    normalizeApiBase: false,
    fetchImpl,
  });

  return {
    createAnimationList: (payload) => api.post('/projection/animation-lists', { body: payload }),
    deleteAnimationList: (animationListId) =>
      api.delete(`/projection/animation-lists/${animationListId}`),
    listAnimationLists: () => api.get('/projection/animation-lists'),
    listAnimations: () => api.get('/projection/animations'),
    updateAnimationList: (animationListId, payload) =>
      api.put(`/projection/animation-lists/${animationListId}`, { body: payload }),
  };
}

function createOverlayRemoteClient(apiBaseUrl, fetchImpl = globalThis.fetch) {
  const normalizedApiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const api = createHttpClient({
    baseURL: normalizedApiBaseUrl,
    normalizeApiBase: false,
    fetchImpl,
  });

  return {
    rootBaseUrl: normalizedApiBaseUrl.replace(/\/api$/, ''),
    createConfig: (payload) => api.post('/overlay/configs', { body: payload }),
    deleteConfig: (configId) => api.delete(`/overlay/configs/${configId}`),
    exportMp4: (payload) =>
      api.post('/overlay/export', { body: payload, parseAs: 'blob', timeout: 0 }),
    getBrightness: () => api.get('/overlay/brightness'),
    listCastDevices: (params = { casting_method: 'dlna' }) =>
      api.get('/v2/discovery/devices', { query: params }),
    listCastSessions: () => api.get('/overlay/cast/sessions'),
    listConfigs: () => api.get('/overlay/configs'),
    listMappings: () => api.get('/mappings/scenes'),
    listVideos: () => api.get('/videos'),
    startCast: (payload) => api.post('/overlay/cast', { body: payload }),
    stopCastSession: (sessionId) => api.delete(`/overlay/cast/sessions/${sessionId}`),
    triggerOverlaySync: (options = {}) =>
      api.post('/overlay/sync', {
        query: {
          triggered_by: options.triggeredBy ?? 'mobile_app',
          video_name: options.videoName,
        },
      }),
  };
}

test('logs remote client uses explicit log endpoints without createServiceModules', async () => {
  activeMock = installFetchMock([
    jsonResponse({ logs: [{ message: 'boot' }] }),
    jsonResponse({ sources: ['frontend', 'backend'] }),
    jsonResponse({ levels: ['INFO', 'ERROR'] }),
    jsonResponse({ total_logs: 2 }),
    jsonResponse({ logs: [{ message: 'tail line' }] }),
  ]);

  const client = createLogsRemoteClient('http://controller.local:8000');

  assert.deepEqual(await client.getLogs({ search: 'boot', sources: ['frontend'], limit: 25 }), {
    logs: [{ message: 'boot' }],
  });
  assert.deepEqual(await client.getSources(), { sources: ['frontend', 'backend'] });
  assert.deepEqual(await client.getLevels(), { levels: ['INFO', 'ERROR'] });
  assert.deepEqual(await client.getStats(), { total_logs: 2 });
  assert.deepEqual(await client.tailSource('frontend', 10), { logs: [{ message: 'tail line' }] });

  assert.deepEqual(
    activeMock.calls.map((call) => ({
      input: call.input,
      method: call.init?.method ?? 'GET',
    })),
    [
      {
        input: 'http://controller.local:8000/api/logs?search=boot&sources=frontend&limit=25',
        method: 'GET',
      },
      { input: 'http://controller.local:8000/api/logs/sources', method: 'GET' },
      { input: 'http://controller.local:8000/api/logs/levels', method: 'GET' },
      { input: 'http://controller.local:8000/api/logs/stats', method: 'GET' },
      { input: 'http://controller.local:8000/api/logs/tail/frontend?lines=10', method: 'GET' },
    ],
  );
});

test('projection remote client uses direct animation-library endpoints', async () => {
  activeMock = installFetchMock([
    jsonResponse({ animations: [{ id: 'anim-1' }] }),
    jsonResponse([{ id: 'list-1' }]),
    jsonResponse({ id: 'list-2', name: 'Ambient' }),
    jsonResponse({ id: 'list-2', name: 'Ambient+' }),
    jsonResponse({ ok: true }),
  ]);

  const client = createProjectionRemoteClient('http://controller.local:8000/api');

  assert.deepEqual(await client.listAnimations(), { animations: [{ id: 'anim-1' }] });
  assert.deepEqual(await client.listAnimationLists(), [{ id: 'list-1' }]);
  assert.deepEqual(await client.createAnimationList({ name: 'Ambient' }), {
    id: 'list-2',
    name: 'Ambient',
  });
  assert.deepEqual(await client.updateAnimationList('list-2', { name: 'Ambient+' }), {
    id: 'list-2',
    name: 'Ambient+',
  });
  assert.deepEqual(await client.deleteAnimationList('list-2'), { ok: true });

  assert.deepEqual(
    activeMock.calls.map((call) => ({
      input: call.input,
      method: call.init?.method ?? 'GET',
      body: call.init?.body ?? null,
    })),
    [
      {
        input: 'http://controller.local:8000/api/projection/animations',
        method: 'GET',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/projection/animation-lists',
        method: 'GET',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/projection/animation-lists',
        method: 'POST',
        body: JSON.stringify({ name: 'Ambient' }),
      },
      {
        input: 'http://controller.local:8000/api/projection/animation-lists/list-2',
        method: 'PUT',
        body: JSON.stringify({ name: 'Ambient+' }),
      },
      {
        input: 'http://controller.local:8000/api/projection/animation-lists/list-2',
        method: 'DELETE',
        body: null,
      },
    ],
  );
});

test('overlay remote client uses explicit overlay and discovery endpoints', async () => {
  activeMock = installFetchMock([
    jsonResponse({ videos: [{ id: 7, name: 'Demo reel' }] }),
    jsonResponse([{ id: 'scene-1', name: 'North wall' }]),
    jsonResponse([{ id: 3, name: 'Overlay A' }]),
    jsonResponse([{ id: 'device-1', friendly_name: 'Projector' }]),
    jsonResponse([{ session_id: 'cast-1' }]),
    jsonResponse({ brightness: 88 }),
    jsonResponse({ id: 9 }),
    jsonResponse({ ok: true }),
    jsonResponse({ ok: true }),
    jsonResponse({ ok: true }),
    blobResponse('binary-overlay-export'),
    jsonResponse({ status: 'ok' }),
  ]);

  const client = createOverlayRemoteClient('http://controller.local:8000');

  assert.equal(client.rootBaseUrl, 'http://controller.local:8000');
  assert.deepEqual(await client.listVideos(), { videos: [{ id: 7, name: 'Demo reel' }] });
  assert.deepEqual(await client.listMappings(), [{ id: 'scene-1', name: 'North wall' }]);
  assert.deepEqual(await client.listConfigs(), [{ id: 3, name: 'Overlay A' }]);
  assert.deepEqual(await client.listCastDevices(), [{ id: 'device-1', friendly_name: 'Projector' }]);
  assert.deepEqual(await client.listCastSessions(), [{ session_id: 'cast-1' }]);
  assert.deepEqual(await client.getBrightness(), { brightness: 88 });
  assert.deepEqual(await client.createConfig({ name: 'Mobile overlay' }), { id: 9 });
  assert.deepEqual(await client.deleteConfig(9), { ok: true });
  assert.deepEqual(await client.startCast({ device_id: 'device-1', config_id: 9 }), { ok: true });
  assert.deepEqual(await client.stopCastSession('cast-1'), { ok: true });
  const exportBlob = await client.exportMp4({ config_id: 9 });
  assert.equal(await exportBlob.text(), 'binary-overlay-export');
  assert.deepEqual(
    await client.triggerOverlaySync({ triggeredBy: 'mobile_overlay_console', videoName: 'Demo reel' }),
    { status: 'ok' },
  );

  assert.deepEqual(
    activeMock.calls.map((call) => ({
      input: call.input,
      method: call.init?.method ?? 'GET',
      body: call.init?.body ?? null,
    })),
    [
      { input: 'http://controller.local:8000/api/videos', method: 'GET', body: null },
      { input: 'http://controller.local:8000/api/mappings/scenes', method: 'GET', body: null },
      { input: 'http://controller.local:8000/api/overlay/configs', method: 'GET', body: null },
      {
        input: 'http://controller.local:8000/api/v2/discovery/devices?casting_method=dlna',
        method: 'GET',
        body: null,
      },
      { input: 'http://controller.local:8000/api/overlay/cast/sessions', method: 'GET', body: null },
      { input: 'http://controller.local:8000/api/overlay/brightness', method: 'GET', body: null },
      {
        input: 'http://controller.local:8000/api/overlay/configs',
        method: 'POST',
        body: JSON.stringify({ name: 'Mobile overlay' }),
      },
      { input: 'http://controller.local:8000/api/overlay/configs/9', method: 'DELETE', body: null },
      {
        input: 'http://controller.local:8000/api/overlay/cast',
        method: 'POST',
        body: JSON.stringify({ device_id: 'device-1', config_id: 9 }),
      },
      {
        input: 'http://controller.local:8000/api/overlay/cast/sessions/cast-1',
        method: 'DELETE',
        body: null,
      },
      {
        input: 'http://controller.local:8000/api/overlay/export',
        method: 'POST',
        body: JSON.stringify({ config_id: 9 }),
      },
      {
        input: 'http://controller.local:8000/api/overlay/sync?triggered_by=mobile_overlay_console&video_name=Demo%20reel',
        method: 'POST',
        body: null,
      },
    ],
  );
});
