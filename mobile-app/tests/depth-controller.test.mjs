import test from 'node:test';
import assert from 'node:assert/strict';

import { buildSegmentationPayload } from '../src/features/depth/utils.ts';

test('buildSegmentationPayload converts comma-separated thresholds into numeric arrays', () => {
  const payload = buildSegmentationPayload('threshold', '7', '0.25, 0.5, nope, 1', '4');

  assert.deepEqual(payload, {
    method: 'threshold',
    n_clusters: 7,
    thresholds: [0.25, 0.5, 1],
    n_bands: 4,
  });
});
