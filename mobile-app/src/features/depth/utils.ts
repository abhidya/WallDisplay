import type { JsonRecord } from '../../types/api.ts';

export function buildSegmentationPayload(
  method: string,
  numClusters: string,
  thresholds: string,
  numBands: string,
): JsonRecord {
  const parsedThresholds = String(thresholds)
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item));

  return {
    method,
    n_clusters: Number(numClusters || 5),
    thresholds: parsedThresholds,
    n_bands: Number(numBands || 5),
  };
}
