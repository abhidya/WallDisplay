import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildStructuredLightingCaptureFormData,
  getCaptureFileName,
  getPersistedCaptureFileName,
  getSafeCapturePathSegment,
  markStepCaptured,
  markStepUploaded,
  normalizeCapturePlan,
} from '../src/features/lighting/structuredLightingCapture.ts';

test('normalizeCapturePlan maps backend steps and existing captures into resumable state', () => {
  const state = normalizeCapturePlan(
    'sess-1',
    {
      plan_version: 'v1',
      steps: [
        { step_index: 0, label: 'black' },
        { step_index: 1, label: 'white', image_url: '/steps/1.png' },
      ],
    },
    [{ step_index: 0 }],
  );

  assert.equal(state.sessionId, 'sess-1');
  assert.equal(state.planVersion, 'v1');
  assert.equal(state.currentStepIndex, 1);
  assert.deepEqual(
    state.steps.map((step) => ({ index: step.index, label: step.label, status: step.status })),
    [
      { index: 0, label: 'black', status: 'uploaded' },
      { index: 1, label: 'white', status: 'pending' },
    ],
  );
});

test('capture state marks local capture then advances after upload', () => {
  const initial = normalizeCapturePlan('sess-1', { steps: [{ index: 0 }, { index: 1 }] });
  const captured = markStepCaptured(initial, 0, 'file:///capture-0.jpg');
  const uploaded = markStepUploaded(captured, 0);

  assert.equal(captured.steps[0].status, 'captured');
  assert.equal(captured.steps[0].localUri, 'file:///capture-0.jpg');
  assert.equal(uploaded.steps[0].status, 'uploaded');
  assert.equal(uploaded.currentStepIndex, 1);
});

test('buildStructuredLightingCaptureFormData sends step index and file payload', async () => {
  const formData = buildStructuredLightingCaptureFormData(3, {
    uri: 'file:///capture-3.jpg',
    blob: new Blob(['capture']),
    name: 'capture-3.jpg',
    type: 'image/jpeg',
  });

  assert.equal(formData.get('step_index'), '3');
  assert.equal(await formData.get('file').text(), 'capture');
});


test('getCaptureFileName preserves camera cache basename when available', () => {
  assert.equal(
    getCaptureFileName(4, 'file:///var/mobile/Containers/Data/capture-4.jpg?cache=1'),
    'capture-4.jpg',
  );
  assert.equal(getCaptureFileName(5, 'file:///tmp/no-extension'), 'structured-lighting-step-5.jpg');
});


test('capture persistence helpers build safe stable file names', () => {
  assert.equal(getSafeCapturePathSegment('Wall Calibration/session 1'), 'Wall-Calibration-session-1');
  assert.equal(
    getPersistedCaptureFileName('Wall Calibration/session 1', 2, 'file:///tmp/capture 2.jpg'),
    'Wall-Calibration-session-1-step-2-capture-2.jpg',
  );
});
