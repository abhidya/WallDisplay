import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';

import { createControlPlaneClient } from '../src/control-plane/client.ts';
import {
  defaultAppState,
  loadLocalControlPlaneState,
  resetLocalControlPlaneState,
  updateLocalControlPlaneState,
} from '../src/control-plane/localState.ts';

async function freshLocalClient() {
  await resetLocalControlPlaneState();
  return createControlPlaneClient('local', defaultAppState.apiBaseUrl);
}

afterEach(async () => {
  await resetLocalControlPlaneState();
});

test('local control plane boots with useful defaults and no backend dependency', async () => {
  const client = await freshLocalClient();

  const [health, devices, capabilities, deferred, streamingHealth, overlaySessions] = await Promise.all([
    client.getHealth(),
    client.listDevices(),
    client.listCapabilities(),
    client.listDeferredFeatures(),
    client.getStreamingHealth(),
    client.listOverlayCastSessions(),
  ]);

  assert.equal(client.mode, 'local');
  assert.equal(health.status, 'local-ready');
  assert.ok(devices.length >= 2, 'expected seeded local device profiles');
  assert.ok(capabilities.some((item) => item.key === 'local-mode' && item.status === 'ready'));
  assert.ok(deferred.some((item) => item.id === 'deferred-renderer'));
  assert.equal(streamingHealth.status, 'healthy');
  assert.deepEqual(overlaySessions, []);
});

test('local control plane persists playback and action history updates', async () => {
  const client = await freshLocalClient();

  await client.playVideoOnDevice('local-sim-1', 'video-1');
  await client.pauseDevicePlayback('local-sim-1');

  let state = await loadLocalControlPlaneState();
  let device = state.devices.find((item) => item.id === 'local-sim-1');
  assert.equal(device?.playback_state, 'paused');
  assert.equal(state.sessions.length, 1);
  assert.equal(state.actionHistory[0]?.title, 'Paused playback');

  await client.stopDevicePlayback('local-sim-1');

  state = await loadLocalControlPlaneState();
  device = state.devices.find((item) => item.id === 'local-sim-1');
  assert.equal(device?.playback_state, 'stopped');
  assert.equal(state.sessions.length, 0);
  assert.equal(state.actionHistory[0]?.title, 'Stopped playback');
});

test('local control plane persists shell preferences for mode and selected device', async () => {
  await resetLocalControlPlaneState();
  await updateLocalControlPlaneState((state) => ({
    ...state,
    app: {
      ...state.app,
      mode: 'remote',
      apiBaseUrl: 'http://controller.local:8000/api',
      selectedDeviceId: 'saved-dlna-target',
      selectedDeviceLabel: 'Saved DLNA target',
    },
  }));

  const state = await loadLocalControlPlaneState();
  assert.equal(state.app.mode, 'remote');
  assert.equal(state.app.apiBaseUrl, 'http://controller.local:8000/api');
  assert.equal(state.app.selectedDeviceId, 'saved-dlna-target');
  assert.equal(state.app.selectedDeviceLabel, 'Saved DLNA target');
});

test('remote control plane still uses the existing API adapter contract', async () => {
  const client = createControlPlaneClient('remote', 'http://controller.local:8000');

  assert.equal(client.mode, 'remote');
  assert.equal(client.apiBaseUrl, 'http://controller.local:8000/api');
  assert.equal(client.rootBaseUrl, 'http://controller.local:8000');

  const history = await client.listActionHistory();
  assert.match(history[0]?.detail ?? '', /controller\.local:8000\/api/);
});

test('native-discovered external devices stay discovery-only until sender transport exists', async () => {
  const client = await freshLocalClient();

  await updateLocalControlPlaneState((state) => {
    state.devices.unshift({
      id: 'native-sample',
      friendly_name: 'Office TV',
      device_name: 'Office TV',
      type: 'google-cast',
      status: 'discovered',
      derived_status: 'native discovery',
      playback_state: 'idle',
      is_playing: false,
      current_media_title: 'Ready',
      config: {
        transport: 'native-discovery',
        supports_manual_actions: false,
      },
      control_mode: {
        mode: 'native-discovery',
        reason: 'Resolved from native discovery.',
        expires_at: null,
      },
    });
    return state;
  });

  const response = await client.playVideoOnDevice('native-sample', 'video-1');
  assert.equal(response.success, false);
  assert.equal(response.status, 'deferred');
  assert.match(response.message ?? '', /discovery-only/i);
});
