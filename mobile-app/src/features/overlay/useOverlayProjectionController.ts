import { useCallback, useEffect, useMemo, useState } from 'react';

import { createServiceModules } from '../../services/api.ts';
import type { AppMode } from '../../control-plane/localState.ts';
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

function createDefaultConfig(name: string, videoId?: number | string | null, mappingSceneId?: number | string | null): JsonRecord {
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
  const services = useMemo(() => createServiceModules(options.apiBaseUrl), [options.apiBaseUrl]);
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
    if (options.appMode !== 'remote') {
      setVideos([]);
      setMappings([]);
      setConfigs([]);
      setCastDevices([]);
      setCastSessions([]);
      return;
    }

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
        services.videoApi.getVideos(),
        services.mappingsApi.listScenes(),
        services.overlayApi.listConfigs(),
        services.discoveryV2Api.getDevices({ casting_method: 'dlna' }),
        services.overlayApi.listCastSessions(),
        services.overlayApi.getBrightness(),
      ]);

      const nextVideos = asArray((asRecord(videosPayload)?.videos ?? videosPayload));
      const nextMappings = asArray(mappingsPayload);
      const nextConfigs = asArray(configsPayload);
      const nextCastDevices = asArray(castDevicesPayload);
      const nextCastSessions = asArray(castSessionsPayload);

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
  }, [options.appMode, services]);

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
        services.overlayApi.createConfig(
          createDefaultConfig(
            `Mobile overlay ${configs.length + 1}`,
            getIdValue(selectedVideo?.id),
            selectedVideo ? null : getIdValue(selectedMapping?.id),
          ),
        ),
      'Overlay config created.',
    );
  }, [configs.length, mappings, runAction, selectedMappingId, selectedVideoId, services, videos]);

  const deleteConfig = useCallback(
    async (configId: number | string) => {
      await runAction(
        () => services.overlayApi.deleteConfig(configId),
        `Deleted overlay config ${String(configId)}.`,
      );
    },
    [runAction, services],
  );

  const startCast = useCallback(async () => {
    if (!selectedConfigId || !selectedCastDeviceId) {
      setError('Select both an overlay config and a cast device first.');
      return;
    }
    await runAction(
      () =>
        services.overlayApi.startCast({
          device_id: selectedCastDeviceId,
          config_id: Number(selectedConfigId),
          overlay_base_url: services.client.rootBaseUrl,
          controls_hidden: true,
          frame_rate: 15,
        }),
      'Overlay cast started.',
      true,
    );
  }, [runAction, selectedCastDeviceId, selectedConfigId, services]);

  const stopCast = useCallback(
    async (sessionId: string) => {
      await runAction(
        () => services.overlayApi.stopCastSession(sessionId),
        `Overlay cast ${sessionId} stopped.`,
        true,
      );
    },
    [runAction, services],
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
      const blob = await services.overlayApi.exportMp4({
        config_id: Number(selectedConfigId),
        overlay_base_url: services.client.rootBaseUrl,
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
  }, [exportDurationSeconds, selectedConfigId, services]);

  const syncOverlays = useCallback(async () => {
    await runAction(
      () =>
        services.client.triggerOverlaySync({
          triggeredBy: 'mobile_overlay_console',
          videoName:
            videos.find((video) => String(video.id) === selectedVideoId)?.name as string | undefined,
        }),
      'Overlay sync triggered.',
    );
  }, [runAction, selectedVideoId, services, videos]);

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
