import { useCallback, useMemo, useState } from 'react';
import { Platform } from 'react-native';

import { createControlPlaneClient } from '../../control-plane/client.ts';
import type { AppMode } from '../../control-plane/localState.ts';
import { createHttpClient, normalizeApiBaseUrl } from '../../services/httpClient.ts';
import type { JsonRecord } from '../../types/api.ts';
import { buildSegmentationPayload } from './utils.ts';

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

async function pickWebFile(): Promise<File | null> {
  if (Platform.OS !== 'web' || typeof document === 'undefined') {
    return null;
  }

  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.png,.jpg,.jpeg,.tif,.tiff,.exr';
    input.onchange = () => resolve(input.files?.[0] ?? null);
    input.click();
  });
}

export interface DepthProcessingController {
  actionMessage: string | null;
  createProjection: () => Promise<void>;
  currentDepthId: string | null;
  deleteDepthMap: () => Promise<void>;
  depthPreviewUrl: string | null;
  error: string | null;
  exportMasks: () => void;
  loading: boolean;
  overlayAlpha: string;
  projectionConfigId: string | null;
  projectionDeviceId: string;
  projectionPageUrl: string | null;
  segmentDepthMap: () => Promise<void>;
  segmentationMethod: string;
  segmentationPreviewUrl: string | null;
  segmentationResult: JsonRecord | null;
  selectedSegments: number[];
  setOverlayAlpha: (value: string) => void;
  setProjectionDeviceId: (value: string) => void;
  setSegmentationMethod: (value: string) => void;
  setThresholds: (value: string) => void;
  setNumBands: (value: string) => void;
  setNumClusters: (value: string) => void;
  thresholds: string;
  numBands: string;
  numClusters: string;
  toggleSegment: (segmentId: number) => void;
  uploadDepthMap: () => Promise<void>;
}

interface UseDepthProcessingControllerOptions {
  apiBaseUrl: string;
  appMode: AppMode;
}

export interface DepthRemoteClient {
  createProjection: (payload: JsonRecord) => Promise<JsonRecord>;
  deleteDepthMap: (depthId: string) => Promise<JsonRecord>;
  exportMasks: (depthId: string, segmentIds: number[]) => Promise<Blob>;
  previewDepthMap: (depthId: string) => string;
  previewSegmentation: (depthId: string, alpha?: number) => string;
  segmentDepthMap: (depthId: string, payload: JsonRecord) => Promise<JsonRecord>;
  uploadDepthMap: (formData: FormData) => Promise<JsonRecord>;
}

export function createDepthRemoteClient(apiBaseUrl: string): DepthRemoteClient {
  const seamClient = createControlPlaneClient('remote', apiBaseUrl);
  const api = createHttpClient({
    baseURL: normalizeApiBaseUrl(apiBaseUrl),
    normalizeApiBase: false,
  });

  return {
    createProjection: (payload: JsonRecord) => seamClient.createDepthProjection(payload),
    deleteDepthMap: (depthId: string) => seamClient.deleteDepthMap(depthId),
    exportMasks: (depthId: string, segmentIds: number[]) =>
      api.post<Blob>(`/depth/export_masks/${depthId}`, {
        body: {
          segment_ids: segmentIds,
          clean_mask: true,
          min_area: 100,
          kernel_size: 3,
        },
        parseAs: 'blob',
      }),
    previewDepthMap: (depthId: string) => seamClient.getDepthPreviewUrl(depthId),
    previewSegmentation: (depthId: string, alpha = 0.5) =>
      seamClient.getDepthSegmentationPreviewUrl(depthId, alpha),
    segmentDepthMap: (depthId: string, payload: JsonRecord) =>
      seamClient.segmentDepthMap(depthId, payload),
    uploadDepthMap: (formData: FormData) => seamClient.uploadDepthMap(formData),
  };
}

export function useDepthProcessingController(
  options: UseDepthProcessingControllerOptions,
): DepthProcessingController {
  const client = useMemo(() => createDepthRemoteClient(options.apiBaseUrl), [options.apiBaseUrl]);
  const [currentDepthId, setCurrentDepthId] = useState<string | null>(null);
  const [segmentationMethod, setSegmentationMethod] = useState('kmeans');
  const [numClusters, setNumClusters] = useState('5');
  const [thresholds, setThresholds] = useState('0.25, 0.5, 0.75');
  const [numBands, setNumBands] = useState('5');
  const [overlayAlpha, setOverlayAlpha] = useState('0.5');
  const [projectionDeviceId, setProjectionDeviceId] = useState('1');
  const [segmentationResult, setSegmentationResult] = useState<JsonRecord | null>(null);
  const [selectedSegments, setSelectedSegments] = useState<number[]>([]);
  const [projectionConfigId, setProjectionConfigId] = useState<string | null>(null);
  const [projectionPageUrl, setProjectionPageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const depthPreviewUrl = currentDepthId ? client.previewDepthMap(currentDepthId) : null;
  const segmentationPreviewUrl =
    currentDepthId && segmentationResult
      ? client.previewSegmentation(currentDepthId, Number(overlayAlpha || 0.5))
      : null;

  const uploadDepthMap = useCallback(async () => {
    if (options.appMode !== 'remote') {
      setError('Depth processing is remote-only in this mobile slice.');
      return;
    }

    const file = await pickWebFile();
    if (!file) {
      setError(
        Platform.OS === 'web'
          ? 'No file selected.'
          : 'File upload is only available on web in this slice.',
      );
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('normalize', 'true');

    setLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await client.uploadDepthMap(formData);
      const record = asRecord(response);
      const depthId = record?.depth_id ? String(record.depth_id) : null;
      setCurrentDepthId(depthId);
      setSegmentationResult(null);
      setSelectedSegments([]);
      setProjectionConfigId(null);
      setProjectionPageUrl(null);
      setActionMessage(
        depthId
          ? `Depth map uploaded. ID: ${depthId}`
          : 'Depth map uploaded.',
      );
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Depth upload failed.');
    } finally {
      setLoading(false);
    }
  }, [client, options.appMode]);

  const segmentDepthMap = useCallback(async () => {
    if (!currentDepthId) {
      setError('Upload a depth map first.');
      return;
    }

    setLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await client.segmentDepthMap(
        currentDepthId,
        buildSegmentationPayload(segmentationMethod, numClusters, thresholds, numBands),
      );
      const record = asRecord(response);
      setSegmentationResult(record);
      const segments = Array.isArray(record?.segments)
        ? record.segments
            .map((item) => Number(item))
            .filter((item) => Number.isFinite(item))
        : [];
      setSelectedSegments(segments.slice(0, 1));
      setActionMessage(
        `Segmentation completed with ${String(record?.segment_count ?? segments.length)} segments.`,
      );
    } catch (segmentError) {
      setError(segmentError instanceof Error ? segmentError.message : 'Segmentation failed.');
    } finally {
      setLoading(false);
    }
  }, [client, currentDepthId, numBands, numClusters, segmentationMethod, thresholds]);

  const toggleSegment = useCallback((segmentId: number) => {
    setSelectedSegments((current) =>
      current.includes(segmentId)
        ? current.filter((item) => item !== segmentId)
        : [...current, segmentId],
    );
  }, []);

  const exportMasks = useCallback(() => {
    if (!currentDepthId || selectedSegments.length === 0) {
      setError('Select at least one segment to export masks.');
      return;
    }

    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const blob = await client.exportMasks(currentDepthId, selectedSegments);

        if (typeof window !== 'undefined') {
          const objectUrl = URL.createObjectURL(blob);
          window.open(objectUrl, '_blank', 'noopener,noreferrer');
          setActionMessage('Opened mask export in a new tab.');
        }
      } catch (exportError) {
        setError(exportError instanceof Error ? exportError.message : 'Mask export failed.');
      } finally {
        setLoading(false);
      }
    })();
  }, [client, currentDepthId, selectedSegments]);

  const deleteDepthMap = useCallback(async () => {
    if (!currentDepthId) {
      setError('No depth map loaded.');
      return;
    }

    setLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      await client.deleteDepthMap(currentDepthId);
      setCurrentDepthId(null);
      setSegmentationResult(null);
      setSelectedSegments([]);
      setProjectionConfigId(null);
      setProjectionPageUrl(null);
      setActionMessage('Depth map deleted.');
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Delete failed.');
    } finally {
      setLoading(false);
    }
  }, [client, currentDepthId]);

  const createProjection = useCallback(async () => {
    if (!currentDepthId || selectedSegments.length === 0) {
      setError('Upload and segment a depth map first.');
      return;
    }

    setLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await client.createProjection({
        device_id: Number(projectionDeviceId || 1),
        depth_id: currentDepthId,
        surfaces: [
          {
            name: 'Primary segment',
            segment_id: selectedSegments[0],
            position: { x: 0, y: 0 },
            scale: { width: 1, height: 1 },
            rotation: 0,
          },
        ],
      });
      const record = asRecord(response);
      setProjectionConfigId(record?.config_id ? String(record.config_id) : null);
      setProjectionPageUrl(record?.page_url ? String(record.page_url) : null);
      setActionMessage('Projection created.');
    } catch (projectionError) {
      setError(projectionError instanceof Error ? projectionError.message : 'Projection creation failed.');
    } finally {
      setLoading(false);
    }
  }, [client, currentDepthId, projectionDeviceId, selectedSegments]);

  return {
    actionMessage,
    createProjection,
    currentDepthId,
    deleteDepthMap,
    depthPreviewUrl,
    error,
    exportMasks,
    loading,
    overlayAlpha,
    projectionConfigId,
    projectionDeviceId,
    projectionPageUrl,
    segmentDepthMap,
    segmentationMethod,
    segmentationPreviewUrl,
    segmentationResult,
    selectedSegments,
    setOverlayAlpha,
    setProjectionDeviceId,
    setSegmentationMethod,
    setThresholds,
    setNumBands,
    setNumClusters,
    thresholds,
    numBands,
    numClusters,
    toggleSegment,
    uploadDepthMap,
  };
}
