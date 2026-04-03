import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { NanoDlnaApiClient } from '../../services/api';
import type {
  MappingSceneSummary,
  OverlayConfigSummary,
  OverlayStatusResponse,
  ProjectionConfigSummary,
  ProjectionSessionSummary,
  RendererInstanceSummary,
  RendererProjectorSummary,
  RendererSceneSummary,
  SceneControlPresetSummary,
  SceneRankSummary,
  StreamingAnalytics,
  StreamingSessionSummary,
} from '../../types/api';

export interface OperationsController {
  actionLoadingKey: string | null;
  actionMessage: string | null;
  analytics: StreamingAnalytics | null;
  error: string | null;
  loading: boolean;
  mappingScenes: MappingSceneSummary[];
  overlayConfigs: OverlayConfigSummary[];
  overlayStatus: OverlayStatusResponse | null;
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
  runRendererPause: () => Promise<void>;
  runRendererResume: () => Promise<void>;
  runRendererStartDefault: () => Promise<void>;
  runRendererStartWithScene: () => Promise<void>;
  runRendererStop: () => Promise<void>;
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

export function useOperationsController(client: NanoDlnaApiClient): OperationsController {
  const [analytics, setAnalytics] = useState<StreamingAnalytics | null>(null);
  const [sessions, setSessions] = useState<StreamingSessionSummary[]>([]);
  const [renderers, setRenderers] = useState<RendererInstanceSummary[]>([]);
  const [projectors, setProjectors] = useState<RendererProjectorSummary[]>([]);
  const [rendererScenes, setRendererScenes] = useState<RendererSceneSummary[]>([]);
  const [overlayConfigs, setOverlayConfigs] = useState<OverlayConfigSummary[]>([]);
  const [overlayStatus, setOverlayStatus] = useState<OverlayStatusResponse | null>(null);
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

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        analyticsPayload,
        sessionsPayload,
        renderersPayload,
        projectorsPayload,
        rendererScenesPayload,
        overlayPayload,
        overlayStatusPayload,
        mappingScenesPayload,
        sceneRanksPayload,
        sceneControlPresetsPayload,
        projectionConfigsPayload,
      ] = await Promise.all([
        client.getStreamingAnalytics(),
        client.listStreamingSessions(),
        client.listRenderers(),
        client.listProjectors(),
        client.listRendererScenes(),
        client.listOverlayConfigs(),
        client.getOverlayStatus(),
        client.listMappingScenes(),
        client.listSceneRanks(),
        client.listSceneControlPresets(),
        client.listProjectionConfigs(),
      ]);

      if (!mountedRef.current) {
        return;
      }

      setAnalytics(analyticsPayload);
      setSessions(sessionsPayload);
      setRenderers(renderersPayload);
      setProjectors(projectorsPayload);
      setRendererScenes(rendererScenesPayload);
      setOverlayConfigs(overlayPayload);
      setOverlayStatus(overlayStatusPayload);
      setMappingScenes(mappingScenesPayload);
      setSceneRanks(sceneRanksPayload);
      setSceneControlPresets(sceneControlPresetsPayload);
      setProjectionConfigs(projectionConfigsPayload);
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
      analytics,
      error,
      loading,
      load,
      launchSelectedProjection,
      mappingScenes,
      overlayConfigs,
      overlayStatus,
      projectors,
      projectionConfigs,
      recentProjectionSession,
      rendererScenes,
      renderers,
      runOverlaySync,
      runRendererPause,
      runRendererResume,
      runRendererStartDefault,
      runRendererStartWithScene,
      runRendererStop,
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
      analytics,
      error,
      launchSelectedProjection,
      load,
      loading,
      mappingScenes,
      overlayConfigs,
      overlayStatus,
      projectors,
      projectionConfigs,
      recentProjectionSession,
      rendererScenes,
      renderers,
      runOverlaySync,
      runRendererPause,
      runRendererResume,
      runRendererStartDefault,
      runRendererStartWithScene,
      runRendererStop,
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
