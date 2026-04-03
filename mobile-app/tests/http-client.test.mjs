/* global Response */

import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';

import { createHttpClient } from '../src/services/httpClient.ts';

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

test('createHttpClient builds absolute API URLs and serializes JSON payloads', async () => {
  activeMock = installFetchMock([jsonResponse({ ok: true })]);

  const client = createHttpClient({ baseURL: 'http://controller.local:8000' });
  await client.post('/devices/discovery/interval', {
    query: { seconds: 15, scopes: ['devices', 'media'] },
    body: { enabled: true },
  });

  assert.deepEqual(activeMock.calls, [
    {
      input: 'http://controller.local:8000/api/devices/discovery/interval?seconds=15&scopes=devices&scopes=media',
      init: {
        method: 'POST',
        headers: new Headers({
          Accept: 'application/json',
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({ enabled: true }),
        signal: activeMock.calls[0]?.init?.signal,
      },
    },
  ]);
});

test('createHttpClient enriches backend failures with status and URL evidence', async () => {
  activeMock = installFetchMock([
    textResponse('backend unavailable', {
      status: 503,
      statusText: 'Service Unavailable',
    }),
  ]);

  const client = createHttpClient({ baseURL: 'http://controller.local:8000/api' });

  await assert.rejects(
    client.get('/streaming/health'),
    (error) => {
      assert.match(error.message, /503 Service Unavailable - backend unavailable/);
      assert.equal(error.status, 503);
      assert.equal(error.url, 'http://controller.local:8000/api/streaming/health');
      assert.equal(error.method, 'GET');
      return true;
    },
  );
});
