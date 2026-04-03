import test from 'node:test';
import assert from 'node:assert/strict';

import {
  currentProductAreas,
  mobileModules,
  mobileRewritePrinciples,
} from '../src/data/features.ts';

test('mobile rewrite principles keep the Expo app isolated and backend-backed', () => {
  assert.ok(
    mobileRewritePrinciples.some((principle) => principle.includes('mobile-app/')),
    'expected an isolation rule for mobile-app/',
  );
  assert.ok(
    mobileRewritePrinciples.some((principle) => principle.includes('FastAPI')),
    'expected an explicit FastAPI control-plane rule',
  );
  assert.ok(
    mobileRewritePrinciples.some((principle) => principle.includes('operator-first')),
    'expected an operator-first prioritization rule',
  );
});

test('mobile modules cover the shared device, media, and operations endpoint groups', () => {
  const overview = mobileModules.find((module) => module.title === 'Overview');
  const devices = mobileModules.find((module) => module.title === 'Devices');
  const media = mobileModules.find((module) => module.title === 'Media');
  const operations = mobileModules.find((module) => module.title === 'Operations');

  assert.deepEqual(overview?.endpoints, ['/api/devices', '/api/videos', '/api/streaming']);
  assert.deepEqual(devices?.endpoints, ['/api/devices', '/api/devices/discover']);
  assert.deepEqual(media?.endpoints, ['/api/videos', '/api/media-library']);
  assert.deepEqual(operations?.endpoints, [
    '/api/streaming/analytics',
    '/api/overlay',
    '/api/renderer',
    '/api/mappings',
    '/api/projection',
  ]);
});

test('product area inventory still includes runtime diagnostics and renderer workflows', () => {
  assert.ok(
    currentProductAreas.some((area) => area.endpoints.includes('/health')),
    'expected diagnostics coverage via /health',
  );
  assert.ok(
    currentProductAreas.some((area) => area.endpoints.includes('/api/renderer')),
    'expected renderer workflow coverage',
  );
  assert.ok(
    currentProductAreas.some((area) => area.endpoints.includes('/api/media-library')),
    'expected media library coverage',
  );
});
