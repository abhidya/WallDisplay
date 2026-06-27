import { useCallback, useEffect, useRef, useState } from 'react';
import type { ProjectionModule } from '../../control-plane/modules.ts';
import type { JsonRecord, ProjectionConfigSummary } from '../../types/api.ts';

export interface ProjectionController {
  loading: boolean;
  actionLoadingKey: string | null;
  error: string | null;
  configs: ProjectionConfigSummary[];
  animations: JsonRecord | null;
  animationLists: JsonRecord[];
  load: () => Promise<void>;
  runAction: <T>(actionKey: string, handler: () => Promise<T>) => Promise<T | undefined>;
}

export function useProjectionController(client: ProjectionModule): ProjectionController {
  const [configs, setConfigs] = useState<ProjectionConfigSummary[]>([]);
  const [animations, setAnimations] = useState<JsonRecord | null>(null);
  const [animationLists, setAnimationLists] = useState<JsonRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoadingKey, setActionLoadingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [configsPayload, animationsPayload, animationListsPayload] = await Promise.all([
        client.listProjectionConfigs(),
        client.listProjectionAnimations(),
        client.listProjectionAnimationLists(),
      ]);
      if (!mountedRef.current) return;
      setConfigs(configsPayload);
      setAnimations(animationsPayload);
      setAnimationLists(animationListsPayload);
    } catch (e) {
      if (mountedRef.current) setError(e instanceof Error ? e.message : 'Failed to load projection data');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [client]);

  const runAction = useCallback(async <T,>(actionKey: string, handler: () => Promise<T>) => {
    setActionLoadingKey(actionKey);
    setError(null);
    try {
      const res = await handler();
      if (mountedRef.current) {
        await load();
      }
      return res;
    } catch (e) {
      if (mountedRef.current) {
        setError(e instanceof Error ? e.message : 'Action failed');
      }
      return undefined;
    } finally {
      if (mountedRef.current) {
        setActionLoadingKey(null);
      }
    }
  }, [load]);

  useEffect(() => {
    void load();
  }, [load]);

  return {
    loading,
    actionLoadingKey,
    error,
    configs,
    animations,
    animationLists,
    load,
    runAction,
  };
}
