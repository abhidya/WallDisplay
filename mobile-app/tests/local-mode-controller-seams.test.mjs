/* global FormData */

import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';

import { resetLocalControlPlaneState } from '../src/control-plane/localState.ts';
import { createStructuredLightingClient } from '../src/features/lighting/useStructuredLightingController.ts';
import { createLogsClient } from '../src/features/logs/useLogsController.ts';
import { createOverlayClient } from '../src/features/overlay/useOverlayProjectionController.ts';
import { createProjectionClient } from '../src/features/projection/useProjectionAnimationController.ts';

const REMOTE_URL = 'http://controller.local:8000';

function rejectingFetch(input) {
  throw new Error(`Local mode should not fetch ${String(input)}`);
}

afterEach(async () => {
  await resetLocalControlPlaneState();
});

test('local mode log controller seam reads on-device action history without backend fetches', async () => {
  await resetLocalControlPlaneState();
  const logsClient = createLogsClient('local', REMOTE_URL, rejectingFetch);

  const [sources, levels, stats, logs, tail] = await Promise.all([
    logsClient.getSources(),
    logsClient.getLevels(),
    logsClient.getStats(),
    logsClient.getLogs({ sources: ['local-control-plane'], search: 'ready', limit: 5 }),
    logsClient.tailSource('local-control-plane', 3),
  ]);

  assert.deepEqual(sources.sources, ['local-control-plane']);
  assert.deepEqual(levels.levels, ['INFO']);
  assert.equal(stats.total_logs, 1);
  assert.equal(logs.total, 1);
  assert.match(logs.logs[0].message, /Local mode ready/);
  assert.equal(tail.logs.length, 1);
});

test('local mode advanced controller seams use safe local/deferred control-plane methods', async () => {
  await resetLocalControlPlaneState();

  const overlayClient = createOverlayClient('local', REMOTE_URL, rejectingFetch);
  const projectionClient = createProjectionClient('local', REMOTE_URL, rejectingFetch);
  const lightingClient = createStructuredLightingClient('local', REMOTE_URL);

  assert.ok((await overlayClient.listVideos()).length >= 1);
  assert.ok((await overlayClient.listCastDevices()).length >= 1);
  const createdOverlay = await overlayClient.createConfig({ name: 'Local-only overlay' });
  assert.equal(createdOverlay.name, 'Local-only overlay');
  assert.equal((await overlayClient.startCast({ config_id: createdOverlay.id })).status, 'deferred');
  assert.equal((await projectionClient.listAnimations()).animations.length, 0);
  assert.deepEqual(await projectionClient.listAnimationLists(), []);
  assert.equal((await projectionClient.createAnimationList({ name: 'Ambient local list' })).status, 'deferred');

  assert.equal((await lightingClient.getCapabilities()).status, 'deferred');
  assert.ok((await lightingClient.listProjectors()).length >= 1);
  assert.equal((await lightingClient.createSession({ name: 'Local calibration' })).status, 'deferred');
});
