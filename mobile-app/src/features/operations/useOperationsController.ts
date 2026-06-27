import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { OperationsModule } from '../../control-plane/modules';
import type {
  ActionHistoryEntry,
  DeferredFeatureSummary,
  JsonRecord,
  LocalCapabilitySummary,
  MappingSceneSummary,
  OverlayConfigSummary,
  OverlayCastSessionSummary,
  OverlayStatusResponse,
  ProjectionConfigSummary,
  ProjectionSessionSummary,
  RendererInstanceSummary,
  RendererProjectorSummary,
  RendererSceneSummary,
  SceneControlPresetSummary,
  SceneRankSummary,
  StreamingAnalytics,
  StreamingHealthResponse,
  StreamingSessionSummary,
} from '../../types/api';

export interface OperationsController {
  actionLoadingKey: string | null;
  actionMessage: string | null;
  actionHistory: ActionHistoryEntry[];
  analytics: StreamingAnalytics | null;
  airplayDevices: JsonRecord[];
  streamingHealth: StreamingHealthResponse | null;
  capabilities: LocalCapabilitySummary[];
  deferredFeatures: DeferredFeatureSummary[];
  error: string | null;
  loading: boolean;
  mode: 'local' | 'remote';
  mappingScenes: MappingSceneSummary[];
  overlayConfigs: OverlayConfigSummary[];
  overlayStatus: OverlayStatusResponse | null;
  overlayCastSessions: OverlayCastSessionSummary[];
  rendererStatus: JsonRecord | null;
  projectors: RendererProjectorSummary[];
  projectionConfigs: ProjectionConfigSummary[];
  recentProjectionSession: ProjectionSessionSummary | null;
  rendererScenes: RendererSceneSummary[];
  renderers: RendererInstanceSummary[];
  sceneControlPresets: SceneControlPresetSummary[];
  sceneRanks: SceneRankSummary[];
  selectedProjectionConfigId: number | string | null;
  selectedProjectorId: string | null;
  selectedSceneId: string | null;
  sessions: StreamingSessionSummary[];
  selectProjectionConfig: (configId: number | string | null) => void;
  selectProjector: (projectorId: string | null) => void;
  selectScene: (sceneId: string | null) => void;
  load: () => Promise<void>;
  launchSelectedProjection: () => Promise<void>;
  runOverlaySync: () => Promise<void>;
  runOverlayCastStop: (sessionId: string) => Promise<void>;
  refreshRendererStatus: () => Promise<void>;
  runRendererPause: () => Promise<void>;
  runRendererResume: () => Promise<void>;
  runRendererStartDefault: () => Promise<void>;
  runRendererStartWithScene: () => Promise<void>;
  runRendererStop: () => Promise<void>;
  runStreamingSessionComplete: (sessionId: string) => Promise<void>;
  runStreamingSessionReset: (sessionId: string) => Promise<void>;
  runStreamingSessionStop: (sessionId: string) => Promise<void>;
}

function ensureCurrentSelection(
  current: string | number | null,
  candidates: Array<string | number>,
): string | number | null {
  if (current !== null && candidates.some((candidate) => String(candidate) === String(current))) {
    return current;
  }
  return candidates[0] ?? null;
}

export function useOperationsController(client: OperationsModule): OperationsController {
  const mode = client.mode;
  const [capabilities, setCapabilities] = useState<LocalCapabilitySummary[]>([]);
  const [actionHistory, setActionHistory] = useState<ActionHistoryEntry[]>([]);
  const [deferredFeatures, setDeferredFeatures] = useState<DeferredFeatureSummary[]>([]);
  const [analytics, setAnalytics] = useState<StreamingAnalytics | null>(null);
  const [airplayDevices, setAirplayDevices] = useState<JsonRecord[]>([]);
  const [streamingHealth, setStreamingHealth] = useState<StreamingHealthResponse | null>(null);
  const [sessions, setSessions] = useState<StreamingSessionSummary[]>([]);
  const [renderers, setRenderers] = useState<RendererInstanceSummary[]>([]);
  const [projectors, setProjectors] = useState<RendererProjectorSummary[]>([]);
  const [rendererScenes, setRendererScenes] = useState<RendererSceneSummary[]>([]);
  const [overlayConfigs, setOverlayConfigs] = useState<OverlayConfigSummary[]>([]);
  const [overlayStatus, setOverlayStatus] = useState<OverlayStatusResponse | null>(null);
  const [overlayCastSessions, setOverlayCastSessions] = useState<OverlayCastSessionSummary[]>([]);
  const [rendererStatus, setRendererStatus] = useState<JsonRecord | null>(null);
  const [mappingScenes, setMappingScenes] = useState<MappingSceneSummary[]>([]);
  const [sceneRanks, setSceneRanks] = useState<SceneRankSummary[]>([]);
  const [sceneControlPresets, setSceneControlPresets] = useState<SceneControlPresetSummary[]>([]);
  const [projectionConfigs, setProjectionConfigs] = useState<ProjectionConfigSummary[]>([]);
  const [recentProjectionSession, setRecentProjectionSession] =
    useState<ProjectionSessionSummary | null>(null);
  const [selectedProjectorId, setSelectedProjectorId] = useState<string | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [selectedProjectionConfigId, setSelectedProjectionConfigId] = useState<
    number | string | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionLoadingKey, setActionLoadingKey] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const describeActionMessage = useCallback((payload: JsonRecord, fallback: string): string => {
    if (typeof payload.message === 'string' && payload.message) {
      return payload.message;
    }
    if (typeof payload.status === 'string' && payload.status) {
      return payload.status;
    }
    if (typeof payload.detail === 'string' && payload.detail) {
      return payload.detail;
    }
    return fallback;
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (client.mode === 'local') {
        const [
          analyticsPayload,
          streamingHealthPayload,
          sessionsPayload,
          capabilityPayload,
          actionHistoryPayload,
          deferredPayload,
        ] = await Promise.all([
          client.getStreamingAnalytics(),
          client.getStreamingHealth(),
          client.listStreamingSessions(),
          client.listCapabilities(),
          client.listActionHistory(),
          client.listDeferredFeatures(),
        ]);

        if (!mountedRef.current) {
          return;
        }

        setAnalytics(analyticsPayload);
        setStreamingHealth(streamingHealthPayload);
        setSessions(sessionsPayload);
        setCapabilities(capabilityPayload);
        setActionHistory(actionHistoryPayload);
        setDeferredFeatures(deferredPayload);
        setAirplayDevices([]);
        setRenderers([]);
        setProjectors([]);
        setRendererScenes([]);
        setOverlayConfigs([]);
        setOverlayStatus(null);
        setOverlayCastSessions([]);
        setRendererStatus(null);
        setMappingScenes([]);
        setSceneRanks([]);
        setSceneControlPresets([]);
        setProjectionConfigs([]);
        setSelectedProjectorId(null);
        setSelectedSceneId(null);
        setSelectedProjectionConfigId(null);
        return;
      }

      const [
        analyticsPayload,
        streamingHealthPayload,
        sessionsPayload,
        renderersPayload,
        projectorsPayload,
        rendererScenesPayload,
        overlayPayload,
        overlayStatusPayload,
        overlayCastSessionsPayload,
        airplayDevicesPayload,
        mappingScenesPayload,
        sceneRanksPayload,
        sceneControlPresetsPayload,
        projectionConfigsPayload,
      ] = await Promise.all([
        client.getStreamingAnalytics(),
        client.getStreamingHealth(),
        client.listStreamingSessions(),
        client.listRenderers(),
        client.listProjectors(),
        client.listRendererScenes(),
        client.listOverlayConfigs(),
        client.getOverlayStatus(),
        client.listOverlayCastSessions(),
        client.getAllAirPlayDevices(),
        client.listMappingScenes(),
        client.listSceneRanks(),
        client.listSceneControlPresets(),
        client.listProjectionConfigs(),
      ]);

      if (!mountedRef.current) {
        return;
      }

      setAnalytics(analyticsPayload);
      setStreamingHealth(streamingHealthPayload);
      setSessions(sessionsPayload);
      setRenderers(renderersPayload);
      setProjectors(projectorsPayload);
      setRendererScenes(rendererScenesPayload);
      setOverlayConfigs(overlayPayload);
      setOverlayStatus(overlayStatusPayload);
      setOverlayCastSessions(overlayCastSessionsPayload);
      setAirplayDevices(
        Array.isArray(airplayDevicesPayload?.devices)
          ? (airplayDevicesPayload.devices as JsonRecord[])
          : [],
      );
      setMappingScenes(mappingScenesPayload);
      setSceneRanks(sceneRanksPayload);
      setSceneControlPresets(sceneControlPresetsPayload);
      setProjectionConfigs(projectionConfigsPayload);
      setCapabilities(
        await client.listCapabilities()
      );
      setActionHistory(
        await client.listActionHistory()
      );
      setDeferredFeatures(
        await client.listDeferredFeatures()
      );
      setSelectedProjectorId((current) => {
        const next = ensureCurrentSelection(
          current,
          projectorsPayload
            .map((projector) => projector.id ?? null)
            .filter((value): value is string => typeof value === 'string' && value.length > 0),
        );
        return typeof next === 'string' ? next : null;
      });
      setSelectedSceneId((current) => {
        const next = ensureCurrentSelection(
          current,
          rendererScenesPayload
            .map((scene) => scene.id ?? null)
            .filter((value): value is string => typeof value === 'string' && value.length > 0),
        );
        return typeof next === 'string' ? next : null;
      });
      setSelectedProjectionConfigId((current) =>
        ensureCurrentSelection(
          current,
          projectionConfigsPayload
            .map((config) => config.id ?? null)
            .filter(
              (value): value is number | string =>
                (typeof value === 'string' && value.length > 0) || typeof value === 'number',
            ),
        ),
      );
    } catch (loadError) {
      if (mountedRef.current) {
        setError(
          loadError instanceof Error ? loadError.message : 'Failed to load operations data.',
        );
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const runAction = useCallback(
    async (
      actionKey: string,
      handler: () => Promise<{ message?: string; status?: string }>,
      options?: { reload?: boolean; successMessage?: string },
    ) => {
      setActionLoadingKey(actionKey);
      setActionMessage(null);
      setError(null);
      try {
        const response = await handler();
        if (!mountedRef.current) {
          return;
        }
        setActionMessage(
          response.message ?? response.status ?? options?.successMessage ?? 'Action completed.',
        );
        if (options?.reload ?? true) {
          await load();
        }
      } catch (actionError) {
        if (mountedRef.current) {
          setError(actionError instanceof Error ? actionError.message : 'Action failed.');
        }
      } finally {
        if (mountedRef.current) {
          setActionLoadingKey(null);
        }
      }
    },
    [load],
  );

  const runRendererStartWithScene = useCallback(async () => {
    if (!selectedProjectorId || !selectedSceneId) {
      setError('Select both a projector and a scene before starting a renderer.');
      return;
    }
    await runAction('start-renderer-scene', () =>
      client.startRenderer(selectedProjectorId, selectedSceneId),
    );
  }, [client, runAction, selectedProjectorId, selectedSceneId]);

  const runRendererStartDefault = useCallback(async () => {
    if (!selectedProjectorId) {
      setError('Select a projector first.');
      return;
    }
    await runAction('start-projector-default', () => client.startProjector(selectedProjectorId));
  }, [client, runAction, selectedProjectorId]);

  const runRendererPause = useCallback(async () => {
    if (!selectedProjectorId) {
      setError('Select a projector first.');
      return;
    }
    await runAction('pause-renderer', () => client.pauseRenderer(selectedProjectorId));
  }, [client, runAction, selectedProjectorId]);

  const runRendererResume = useCallback(async () => {
    if (!selectedProjectorId) {
      setError('Select a projector first.');
      return;
    }
    await runAction('resume-renderer', () => client.resumeRenderer(selectedProjectorId));
  }, [client, runAction, selectedProjectorId]);

  const runRendererStop = useCallback(async () => {
    if (!selectedProjectorId) {
      setError('Select a projector first.');
      return;
    }
    await runAction('stop-renderer', () => client.stopRenderer(selectedProjectorId));
  }, [client, runAction, selectedProjectorId]);

  const runOverlaySync = useCallback(async () => {
    await runAction(
      'overlay-sync',
      () => client.triggerOverlaySync({ triggeredBy: 'mobile_operator_console' }),
      { successMessage: 'Overlay sync triggered.' },
    );
  }, [client, runAction]);

  const runOverlayCastStop = useCallback(
    async (sessionId: string) => {
      await runAction(
        `stop-overlay-cast-${sessionId}`,
        async () => ({
          message: describeActionMessage(
            await client.stopOverlayCastSession(sessionId),
            `Overlay cast session ${sessionId} stopped.`,
          ),
        }),
        { successMessage: `Overlay cast session ${sessionId} stopped.` },
      );
    },
    [client, describeActionMessage, runAction],
  );

  const refreshRendererStatus = useCallback(async () => {
    if (!selectedProjectorId) {
      setError('Select a projector first.');
      return;
    }

    setActionLoadingKey('refresh-renderer-status');
    setError(null);
    try {
      const payload = await client.getRendererStatus(selectedProjectorId);
      if (!mountedRef.current) {
        return;
      }
      setRendererStatus(payload);
      setActionMessage('Renderer status refreshed.');
    } catch (statusError) {
      if (mountedRef.current) {
        setError(
          statusError instanceof Error ? statusError.message : 'Failed to load renderer status.',
        );
      }
    } finally {
      if (mountedRef.current) {
        setActionLoadingKey(null);
      }
    }
  }, [client, selectedProjectorId]);

  const runStreamingSessionComplete = useCallback(
    async (sessionId: string) => {
      await runAction(
        `complete-streaming-session-${sessionId}`,
        async () => ({
          message: describeActionMessage(
            await client.completeStreamingSession(sessionId),
            `Session ${sessionId} marked complete.`,
          ),
        }),
        { successMessage: `Session ${sessionId} marked complete.` },
      );
    },
    [client, describeActionMessage, runAction],
  );

  const runStreamingSessionReset = useCallback(
    async (sessionId: string) => {
      await runAction(
        `reset-streaming-session-${sessionId}`,
        async () => ({
          message: describeActionMessage(
            await client.resetStreamingSession(sessionId),
            `Session ${sessionId} reset.`,
          ),
        }),
        { successMessage: `Session ${sessionId} reset.` },
      );
    },
    [client, describeActionMessage, runAction],
  );

  const runStreamingSessionStop = useCallback(
    async (sessionId: string) => {
      await runAction(
        `stop-streaming-session-${sessionId}`,
        async () => ({
          message: describeActionMessage(
            await client.stopStreamingSession(sessionId),
            `Session ${sessionId} stopped.`,
          ),
        }),
        { successMessage: `Session ${sessionId} stopped.` },
      );
    },
    [client, describeActionMessage, runAction],
  );

  const launchSelectedProjection = useCallback(async () => {
    if (selectedProjectionConfigId === null || selectedProjectionConfigId === undefined) {
      setError('Select a projection config first.');
      return;
    }

    setActionLoadingKey('launch-projection');
    setActionMessage(null);
    setError(null);
    try {
      const launchResponse = await client.launchProjectionConfig(selectedProjectionConfigId);
      const sessionId = launchResponse.id;
      const sessionPayload =
        typeof sessionId === 'string' && sessionId.length > 0
          ? await client.getProjectionSession(sessionId)
          : launchResponse;

      if (!mountedRef.current) {
        return;
      }

      setRecentProjectionSession(sessionPayload);
      setActionMessage(
        launchResponse.status ? `Projection ${launchResponse.status}.` : 'Projection launched.',
      );
      await load();
    } catch (actionError) {
      if (mountedRef.current) {
        setError(actionError instanceof Error ? actionError.message : 'Projection launch failed.');
      }
    } finally {
      if (mountedRef.current) {
        setActionLoadingKey(null);
      }
    }
  }, [client, load, selectedProjectionConfigId]);

  const selectProjector = useCallback((projectorId: string | null) => {
    setSelectedProjectorId(projectorId);
  }, []);

  const selectScene = useCallback((sceneId: string | null) => {
    setSelectedSceneId(sceneId);
  }, []);

  const selectProjectionConfig = useCallback((configId: number | string | null) => {
    setSelectedProjectionConfigId(configId);
  }, []);

  return useMemo(
    () => ({
      actionLoadingKey,
      actionMessage,
      actionHistory,
      analytics,
      airplayDevices,
      streamingHealth,
      capabilities,
      deferredFeatures,
      error,
      loading,
      mode,
      load,
      launchSelectedProjection,
      mappingScenes,
      overlayConfigs,
      overlayCastSessions,
      overlayStatus,
      rendererStatus,
      projectors,
      projectionConfigs,
      recentProjectionSession,
      rendererScenes,
      renderers,
      runOverlaySync,
      runOverlayCastStop,
      refreshRendererStatus,
      runRendererPause,
      runRendererResume,
      runRendererStartDefault,
      runRendererStartWithScene,
      runRendererStop,
      runStreamingSessionComplete,
      runStreamingSessionReset,
      runStreamingSessionStop,
      sceneControlPresets,
      sceneRanks,
      selectProjectionConfig,
      selectProjector,
      selectScene,
      selectedProjectionConfigId,
      selectedProjectorId,
      selectedSceneId,
      sessions,
    }),
    [
      actionLoadingKey,
      actionMessage,
      actionHistory,
      analytics,
      airplayDevices,
      streamingHealth,
      capabilities,
      deferredFeatures,
      error,
      launchSelectedProjection,
      load,
      loading,
      mode,
      mappingScenes,
      overlayConfigs,
      overlayCastSessions,
      overlayStatus,
      rendererStatus,
      projectors,
      projectionConfigs,
      recentProjectionSession,
      rendererScenes,
      renderers,
      runOverlaySync,
      runOverlayCastStop,
      refreshRendererStatus,
      runRendererPause,
      runRendererResume,
      runRendererStartDefault,
      runRendererStartWithScene,
      runRendererStop,
      runStreamingSessionComplete,
      runStreamingSessionReset,
      runStreamingSessionStop,
      sceneControlPresets,
      sceneRanks,
      selectProjectionConfig,
      selectProjector,
      selectScene,
      selectedProjectionConfigId,
      selectedProjectorId,
      selectedSceneId,
      sessions,
    ],
  );
}
