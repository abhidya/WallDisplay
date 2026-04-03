import test from 'node:test';
import assert from 'node:assert/strict';

import { createControlPlaneClient } from '../src/control-plane/client.ts';

test('local control plane exposes on-device capabilities and deferred advanced operations', async () => {
  const client = createControlPlaneClient('local', 'http://unused.local/api');

  assert.equal(client.mode, 'local');

  const [health, capabilities, deferredFeatures, devices] = await Promise.all([
    client.getHealth(),
    client.listCapabilities(),
    client.listDeferredFeatures(),
    client.listDevices(),
  ]);

  assert.equal(health.status, 'local-ready');
  assert.ok(capabilities.some((capability) => capability.key === 'local-mode'));
  assert.ok(capabilities.some((capability) => capability.status === 'deferred'));
  assert.ok(deferredFeatures.some((feature) => feature.id === 'deferred-renderer'));
  assert.ok(devices.length >= 1);
});

test('local control plane can start playback and record a local session without a backend', async () => {
  const client = createControlPlaneClient('local', 'http://unused.local/api');
  const [device] = await client.listDevices();
  const [video] = await client.listVideos();

  assert.ok(device?.id);
  assert.ok(video?.id);

  const response = await client.playVideoOnDevice(device.id, video.id, { syncOverlays: false });
  assert.match(response.message ?? '', /local control plane/i);

  const sessions = await client.listStreamingSessions();
  assert.ok(
    sessions.some((session) => String(session.session_id) === `local-session-${String(device.id)}`),
  );

  const history = await client.listActionHistory();
  assert.ok(history.some((entry) => /Started local playback/i.test(entry.title)));
});
