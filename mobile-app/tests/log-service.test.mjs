/* global Response */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { FrontendLogService } from '../src/services/logService.ts';

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

function createFakeConsole() {
  const captured = [];
  return {
    captured,
    consoleRef: {
      log: (...args) => captured.push(['log', args]),
      warn: (...args) => captured.push(['warn', args]),
      error: (...args) => captured.push(['error', args]),
      info: (...args) => captured.push(['info', args]),
      debug: (...args) => captured.push(['debug', args]),
    },
  };
}

test('FrontendLogService flushes queued logs to the backend transport', async () => {
  const calls = [];
  const fakeConsole = createFakeConsole();
  const logger = new FrontendLogService({
    backendUrl: 'http://controller.local:8000',
    autoStart: false,
    captureConsole: false,
    consoleRef: fakeConsole.consoleRef,
    fetchImpl: async (input, init) => {
      calls.push({ input: String(input), init });
      return jsonResponse({ ok: true });
    },
  });

  logger.logInfo('Booted mobile shell', { component: 'app-shell' });
  assert.equal(logger.getQueueSize(), 1);

  const flushed = await logger.flushLogs();
  assert.equal(flushed, true);
  assert.equal(logger.getQueueSize(), 0);
  assert.equal(calls[0]?.input, 'http://controller.local:8000/api/logs/frontend');

  logger.destroy();
});

test('FrontendLogService restores queued logs when the backend rejects a batch', async () => {
  const fakeConsole = createFakeConsole();
  const logger = new FrontendLogService({
    backendUrl: 'http://controller.local:8000',
    autoStart: false,
    captureConsole: false,
    consoleRef: fakeConsole.consoleRef,
    fetchImpl: async () =>
      new Response('nope', {
        status: 500,
        statusText: 'Internal Server Error',
      }),
  });

  logger.logError('Failed to hydrate renderer', { component: 'renderer' });
  const flushed = await logger.flushLogs();

  assert.equal(flushed, false);
  assert.equal(logger.getQueueSize(), 1);
  assert.equal(fakeConsole.captured.length, 1);
  assert.equal(fakeConsole.captured[0][0], 'error');

  logger.setOnline(false);
  logger.destroy();
});

test('FrontendLogService can capture console calls without mutating the global console', async () => {
  const fakeConsole = createFakeConsole();

  const logger = new FrontendLogService({
    autoStart: false,
    captureConsole: false,
    consoleRef: fakeConsole.consoleRef,
  });

  logger.setupConsoleCapture();
  fakeConsole.consoleRef.warn('captured warning', { scope: 'test' });

  assert.equal(logger.getQueueSize(), 1);
  assert.equal(fakeConsole.captured.length, 1);

  logger.destroy();
});
