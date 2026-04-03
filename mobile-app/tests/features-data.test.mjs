import test from 'node:test';
import assert from 'node:assert/strict';

import {
  currentProductAreas,
  mobileModules,
  mobileRewritePrinciples,
} from '../src/data/features.ts';

test('mobile rewrite principles keep the Expo app isolated and local-first', () => {
  assert.ok(
    mobileRewritePrinciples.some((principle) => principle.includes('mobile-app/')),
    'expected an isolation rule for mobile-app/',
  );
  assert.ok(
    mobileRewritePrinciples.some((principle) => principle.includes('on-device control plane')),
    'expected an explicit local-first control-plane rule',
  );
  assert.ok(
    mobileRewritePrinciples.some((principle) => principle.includes('operator-first')),
    'expected an operator-first prioritization rule',
  );
});

test('mobile modules cover local-first overview, devices, media, and operations flows', () => {
  const overview = mobileModules.find((module) => module.title === 'Overview');
  const devices = mobileModules.find((module) => module.title === 'Devices');
  const media = mobileModules.find((module) => module.title === 'Media');
  const operations = mobileModules.find((module) => module.title === 'Operations');

  assert.deepEqual(overview?.endpoints, ['local://health', 'local://capabilities', '/health']);
  assert.deepEqual(devices?.endpoints, ['local://devices', 'local://discovery', '/api/devices']);
  assert.deepEqual(media?.endpoints, ['local://media', 'local://media/channels', '/api/videos']);
  assert.deepEqual(operations?.endpoints, ['local://history', 'local://capabilities', '/api/streaming/analytics']);
});

test('product area inventory still acknowledges diagnostics and deferred advanced workflows', () => {
  assert.ok(
    currentProductAreas.some((area) => area.endpoints.includes('local://health')),
    'expected diagnostics coverage via local health',
  );
  assert.ok(
    currentProductAreas.some((area) => area.endpoints.includes('/api/renderer')),
    'expected deferred renderer workflow visibility',
  );
  assert.ok(
    currentProductAreas.some((area) => area.endpoints.includes('local://media')),
    'expected local media workflow coverage',
  );
});
