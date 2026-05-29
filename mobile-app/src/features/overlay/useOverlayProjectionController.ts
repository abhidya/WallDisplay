import { useCallback, useEffect, useMemo, useState } from 'react';

import { createControlPlaneClient } from '../../control-plane/client.ts';
import type { AppMode } from '../../control-plane/localState.ts';
import {
  createHttpClient,
  normalizeApiBaseUrl,
  type QueryRecord,
} from '../../services/httpClient.ts';
import type { JsonRecord } from '../../types/api.ts';

function asArray(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) as JsonRecord[]
    : [];
}

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function createDefaultConfig(
  name: string,
  videoId?: number | string | null,
  mappingSceneId?: number | string | null,
): JsonRecord {
  return {
    name,
    background_type: videoId ? 'video' : 'mapping',
    video_id: videoId ?? null,
    mapping_scene_id: mappingSceneId ?? null,
    video_transform: { x: 0, y: 0, scale: 1, rotation: 0 },
    widgets: [],
    api_configs: {
      weather_api_key: '',
      transit_stop_id: '13915',
      timezone: 'America/Los_Angeles',
    },
  };
}

function getIdValue(value: unknown): string | number | null {
  return typeof value === 'string' || typeof value === 'number' ? value : null;
}

export interface OverlayRemoteClient {
  readonly rootBaseUrl: string;
  createConfig: (payload: JsonRecord) => Promise<JsonRecord>;
  deleteConfig: (configId: number | string) => Promise<JsonRecord>;
  exportMp4: (payload: JsonRecord) => Promise<Blob>;
  getBrightness: () => Promise<JsonRecord>;
  listCastDevices: (params?: QueryRecord) => Promise<JsonRecord[]>;
  listCastSessions: () => Promise<JsonRecord[]>;
  listConfigs: () => Promise<JsonRecord[]>;
  listMappings: () => Promise<JsonRecord[]>;
  listVideos: () => Promise<JsonRecord[]>;
  startCast: (payload: JsonRecord) => Promise<JsonRecord>;
  stopCastSession: (sessionId: string) => Promise<JsonRecord>;
  triggerOverlaySync: (options?: { triggeredBy?: string; videoName?: string }) => Promise<JsonRecord>;
}

export function createOverlayRemoteClient(
  apiBaseUrl: string,
  fetchImpl: typeof fetch = globalThis.fetch,
): OverlayRemoteClient {
  const normalizedApiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const api = createHttpClient({
    baseURL: normalizedApiBaseUrl,
    normalizeApiBase: false,
    fetchImpl,
  });

  return {
    rootBaseUrl: normalizedApiBaseUrl.replace(/\/api$/, ''),
    createConfig: (payload: JsonRecord) => api.post<JsonRecord>('/overlay/configs', { body: payload }),
    deleteConfig: (configId: number | string) => api.delete<JsonRecord>(`/overlay/configs/${configId}`),
    exportMp4: (payload: JsonRecord) =>
      api.post<Blob>('/overlay/export', { body: payload, parseAs: 'blob', timeout: 0 }),
    getBrightness: () => api.get<JsonRecord>('/overlay/brightness'),
    listCastDevices: (params: QueryRecord = { casting_method: 'dlna' }) =>
      api.get<JsonRecord[]>('/v2/discovery/devices', { query: params }),
    listCastSessions: () => api.get<JsonRecord[]>('/overlay/cast/sessions'),
    listConfigs: () => api.get<JsonRecord[]>('/overlay/configs'),
    listMappings: () => api.get<JsonRecord[]>('/mappings/scenes'),
    listVideos: () => api.get<JsonRecord[]>('/videos'),
    startCast: (payload: JsonRecord) => api.post<JsonRecord>('/overlay/cast', { body: payload }),
    stopCastSession: (sessionId: string) => api.delete<JsonRecord>(`/overlay/cast/sessions/${sessionId}`),
    triggerOverlaySync: (options?: { triggeredBy?: string; videoName?: string }) =>
      api.post<JsonRecord>('/overlay/sync', {
        query: {
          triggered_by: options?.triggeredBy ?? 'mobile_app',
          video_name: options?.videoName,
        },
      }),
  };
}

export function createOverlayClient(
  appMode: AppMode,
  apiBaseUrl: string,
  fetchImpl: typeof fetch = globalThis.fetch,
): OverlayRemoteClient {
  if (appMode === 'local') {
    const seamClient = createControlPlaneClient('local', apiBaseUrl);
    return {
      rootBaseUrl: seamClient.rootBaseUrl,
      createConfig: (payload: JsonRecord) => seamClient.createOverlayConfig(payload),
      deleteConfig: (configId: number | string) => seamClient.deleteOverlayConfig(configId),
      exportMp4: (payload: JsonRecord) => seamClient.exportOverlayMp4(payload),
      getBrightness: () => seamClient.getOverlayBrightness(),
      listCastDevices: async () => seamClient.listDevices() as Promise<JsonRecord[]>,
      listCastSessions: () => seamClient.listOverlayCastSessions() as Promise<JsonRecord[]>,
      listConfigs: () => seamClient.listOverlayConfigs() as Promise<JsonRecord[]>,
      listMappings: () => seamClient.listMappingScenes() as Promise<JsonRecord[]>,
      listVideos: () => seamClient.listVideos() as Promise<JsonRecord[]>,
      startCast: (payload: JsonRecord) => seamClient.startOverlayCast(payload),
      stopCastSession: (sessionId: string) => seamClient.stopOverlayCastSession(sessionId),
      triggerOverlaySync: (options?: { triggeredBy?: string; videoName?: string }) =>
        seamClient.triggerOverlaySync(options),
    };
  }

  return createOverlayRemoteClient(apiBaseUrl, fetchImpl);
}

export interface OverlayProjectionController {
  actionLoading: boolean;
  actionMessage: string | null;
  brightness: number;
  castDevices: JsonRecord[];
  castLoading: boolean;
  castSessions: JsonRecord[];
  configs: JsonRecord[];
  createConfig: () => Promise<void>;
  deleteConfig: (configId: number | string) => Promise<void>;
  error: string | null;
  exportDurationSeconds: string;
  exportProjection: () => Promise<void>;
  loading: boolean;
  mappings: JsonRecord[];
  refresh: () => Promise<void>;
  selectedCastDeviceId: string;
  selectedConfigId: string;
  selectedMappingId: string;
  selectedVideoId: string;
  setBrightnessValue: (value: string) => void;
  setExportDurationSeconds: (value: string) => void;
  setSelectedCastDeviceId: (value: string) => void;
  setSelectedConfigId: (value: string) => void;
  setSelectedMappingId: (value: string) => void;
  setSelectedVideoId: (value: string) => void;
  startCast: () => Promise<void>;
  stopCast: (sessionId: string) => Promise<void>;
  syncOverlays: () => Promise<void>;
  videos: JsonRecord[];
}

interface UseOverlayProjectionControllerOptions {
  apiBaseUrl: string;
  appMode: AppMode;
}

export function useOverlayProjectionController(
  options: UseOverlayProjectionControllerOptions,
): OverlayProjectionController {
  const client = useMemo(
    () => createOverlayClient(options.appMode, options.apiBaseUrl),
    [options.apiBaseUrl, options.appMode],
  );
  const [videos, setVideos] = useState<JsonRecord[]>([]);
  const [mappings, setMappings] = useState<JsonRecord[]>([]);
  const [configs, setConfigs] = useState<JsonRecord[]>([]);
  const [castDevices, setCastDevices] = useState<JsonRecord[]>([]);
  const [castSessions, setCastSessions] = useState<JsonRecord[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState('');
  const [selectedMappingId, setSelectedMappingId] = useState('');
  const [selectedConfigId, setSelectedConfigId] = useState('');
  const [selectedCastDeviceId, setSelectedCastDeviceId] = useState('');
  const [brightness, setBrightness] = useState(100);
  const [exportDurationSeconds, setExportDurationSeconds] = useState('30');
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [castLoading, setCastLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        videosPayload,
        mappingsPayload,
        configsPayload,
        castDevicesPayload,
        castSessionsPayload,
        brightnessPayload,
      ] = await Promise.all([
        client.listVideos(),
        client.listMappings(),
        client.listConfigs(),
        client.listCastDevices(),
        client.listCastSessions(),
        client.getBrightness(),
      ]);

      const nextVideos = asArray(asRecord(videosPayload)?.videos ?? videosPayload);
      const nextMappings = asArray(asRecord(mappingsPayload)?.scenes ?? mappingsPayload);
      const nextConfigs = asArray(asRecord(configsPayload)?.configs ?? configsPayload);
      const nextCastDevices = asArray(asRecord(castDevicesPayload)?.devices ?? castDevicesPayload);
      const nextCastSessions = asArray(asRecord(castSessionsPayload)?.sessions ?? castSessionsPayload);

      setVideos(nextVideos);
      setMappings(nextMappings);
      setConfigs(nextConfigs);
      setCastDevices(nextCastDevices);
      setCastSessions(nextCastSessions);
      setBrightness(Number(asRecord(brightnessPayload)?.brightness ?? 100));
      setSelectedVideoId((current) => current || String(nextVideos[0]?.id ?? ''));
      setSelectedMappingId((current) => current || String(nextMappings[0]?.id ?? ''));
      setSelectedConfigId((current) => current || String(nextConfigs[0]?.id ?? ''));
      setSelectedCastDeviceId((current) => current || String(nextCastDevices[0]?.id ?? ''));
    } catch (refreshError) {
      setError(
        refreshError instanceof Error ? refreshError.message : 'Failed to load overlay data.',
      );
    } finally {
      setLoading(false);
    }
  }, [client, options.appMode]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runAction = useCallback(
    async (handler: () => Promise<unknown>, successMessage: string, castAction = false) => {
      if (castAction) {
        setCastLoading(true);
      } else {
        setActionLoading(true);
      }
      setError(null);
      setActionMessage(null);
      try {
        await handler();
        setActionMessage(successMessage);
        await refresh();
      } catch (actionError) {
        setError(actionError instanceof Error ? actionError.message : 'Overlay action failed.');
      } finally {
        if (castAction) {
          setCastLoading(false);
        } else {
          setActionLoading(false);
        }
      }
    },
    [refresh],
  );

  const createConfig = useCallback(async () => {
    const selectedVideo = videos.find((video) => String(video.id) === selectedVideoId) ?? null;
    const selectedMapping = mappings.find((scene) => String(scene.id) === selectedMappingId) ?? null;
    await runAction(
      () =>
        client.createConfig(
          createDefaultConfig(
            `Mobile overlay ${configs.length + 1}`,
            getIdValue(selectedVideo?.id),
            selectedVideo ? null : getIdValue(selectedMapping?.id),
          ),
        ),
      'Overlay config created.',
    );
  }, [client, configs.length, mappings, runAction, selectedMappingId, selectedVideoId, videos]);

  const deleteConfig = useCallback(
    async (configId: number | string) => {
      await runAction(() => client.deleteConfig(configId), `Deleted overlay config ${String(configId)}.`);
    },
    [client, runAction],
  );

  const startCast = useCallback(async () => {
    if (!selectedConfigId || !selectedCastDeviceId) {
      setError('Select both an overlay config and a cast device first.');
      return;
    }
    await runAction(
      () =>
        client.startCast({
          device_id: selectedCastDeviceId,
          config_id: Number(selectedConfigId),
          overlay_base_url: client.rootBaseUrl,
          controls_hidden: true,
          frame_rate: 15,
        }),
      'Overlay cast started.',
      true,
    );
  }, [client, runAction, selectedCastDeviceId, selectedConfigId]);

  const stopCast = useCallback(
    async (sessionId: string) => {
      await runAction(
        () => client.stopCastSession(sessionId),
        `Overlay cast ${sessionId} stopped.`,
        true,
      );
    },
    [client, runAction],
  );

  const exportProjection = useCallback(async () => {
    if (!selectedConfigId) {
      setError('Select an overlay config first.');
      return;
    }
    setActionLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const blob = await client.exportMp4({
        config_id: Number(selectedConfigId),
        overlay_base_url: client.rootBaseUrl,
        controls_hidden: true,
        hide_widgets: true,
        viewport_width: 1280,
        viewport_height: 720,
        capture_width: 1280,
        capture_height: 720,
        quality: 80,
        frame_rate: 24,
        duration_seconds: Number(exportDurationSeconds || 30),
        bitrate_kbps: 2500,
      });

      if (typeof window !== 'undefined') {
        const objectUrl = URL.createObjectURL(blob);
        window.open(objectUrl, '_blank', 'noopener,noreferrer');
      }
      setActionMessage('Overlay export generated.');
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : 'Overlay export failed.');
    } finally {
      setActionLoading(false);
    }
  }, [client, exportDurationSeconds, selectedConfigId]);

  const syncOverlays = useCallback(async () => {
    await runAction(
      () =>
        client.triggerOverlaySync({
          triggeredBy: 'mobile_overlay_console',
          videoName:
            videos.find((video) => String(video.id) === selectedVideoId)?.name as string | undefined,
        }),
      'Overlay sync triggered.',
    );
  }, [client, runAction, selectedVideoId, videos]);

  const setBrightnessValue = useCallback((value: string) => {
    const next = Number(value || 100);
    setBrightness(Number.isFinite(next) ? next : 100);
  }, []);

  return {
    actionLoading,
    actionMessage,
    brightness,
    castDevices,
    castLoading,
    castSessions,
    configs,
    createConfig,
    deleteConfig,
    error,
    exportDurationSeconds,
    exportProjection,
    loading,
    mappings,
    refresh,
    selectedCastDeviceId,
    selectedConfigId,
    selectedMappingId,
    selectedVideoId,
    setBrightnessValue,
    setExportDurationSeconds,
    setSelectedCastDeviceId,
    setSelectedConfigId,
    setSelectedMappingId,
    setSelectedVideoId,
    startCast,
    stopCast,
    syncOverlays,
    videos,
  };
}
