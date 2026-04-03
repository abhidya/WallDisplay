import { beforeEach, test } from 'node:test';
import assert from 'node:assert/strict';

import { createControlPlaneClient } from '../src/control-plane/client.ts';
import {
  loadLocalControlPlaneState,
  resetLocalControlPlaneState,
} from '../src/control-plane/localState.ts';

beforeEach(async () => {
  await resetLocalControlPlaneState();
});

test('local control plane boots without a backend and exposes local-safe capabilities', async () => {
  const client = createControlPlaneClient('local', 'http://unused.local:8000/api');

  const [health, devices, capabilities, deferredFeatures] = await Promise.all([
    client.getHealth(),
    client.listDevices(),
    client.listCapabilities(),
    client.listDeferredFeatures(),
  ]);

  assert.equal(client.mode, 'local');
  assert.equal(health.status, 'local-ready');
  assert.ok(devices.length >= 1, 'expected seeded local devices');
  assert.ok(
    capabilities.some((item) => item.key === 'local-mode' && item.status === 'ready'),
    'expected local control plane capability',
  );
  assert.ok(
    deferredFeatures.some((item) => item.id === 'deferred-receiver'),
    'expected explicit deferred receiver card',
  );
});

test('local control plane persists playback and action history updates', async () => {
  const client = createControlPlaneClient('local', 'http://unused.local:8000/api');

  const discoverResult = await client.discoverDevices(3);
  assert.equal(discoverResult.success, true);

  const playResult = await client.playVideoOnDevice('local-sim-1', 'video-1', {
    syncOverlays: true,
  });
  assert.equal(playResult.success, true);

  const [sessions, history, state] = await Promise.all([
    client.listStreamingSessions(),
    client.listActionHistory(),
    loadLocalControlPlaneState(),
  ]);

  assert.equal(sessions.length, 1);
  assert.equal(sessions[0]?.status, 'playing');
  assert.equal(state.devices[0]?.current_video, 'video-1');
  assert.ok(
    history.some((entry) => entry.title === 'Started local playback'),
    'expected playback action to be recorded',
  );
});

test('remote control plane still uses the existing API adapter contract', async () => {
  const client = createControlPlaneClient('remote', 'http://controller.local:8000');

  assert.equal(client.mode, 'remote');
  assert.equal(client.apiBaseUrl, 'http://controller.local:8000/api');
  assert.equal(client.rootBaseUrl, 'http://controller.local:8000');

  const history = await client.listActionHistory();
  assert.match(history[0]?.detail ?? '', /controller\.local:8000\/api/);
});
