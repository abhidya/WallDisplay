import { useCallback, useEffect, useRef, useState } from 'react';
import type { ControlPlaneClient } from '../../control-plane/client.ts';
import type { JsonRecord, OverlayConfigSummary, OverlayCastSessionSummary, OverlayStatusResponse } from '../../types/api.ts';

export interface OverlayController {
  loading: boolean;
  actionLoadingKey: string | null;
  error: string | null;
  configs: OverlayConfigSummary[];
  castSessions: OverlayCastSessionSummary[];
  status: OverlayStatusResponse | null;
  brightnessStatus: JsonRecord | null;
  load: () => Promise<void>;
  runAction: <T>(actionKey: string, handler: () => Promise<T>) => Promise<T | undefined>;
}

export function useOverlayController(client: ControlPlaneClient): OverlayController {
  const [configs, setConfigs] = useState<OverlayConfigSummary[]>([]);
  const [castSessions, setCastSessions] = useState<OverlayCastSessionSummary[]>([]);
  const [status, setStatus] = useState<OverlayStatusResponse | null>(null);
  const [brightnessStatus, setBrightnessStatus] = useState<JsonRecord | null>(null);
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
      const [configsRes, sessionsRes, statusRes, brightnessRes] = await Promise.all([
        client.listOverlayConfigs(),
        client.listOverlayCastSessions(),
        client.getOverlayStatus(),
        client.getBrightnessStatus(),
      ]);
      if (!mountedRef.current) return;
      setConfigs(configsRes);
      setCastSessions(sessionsRes);
      setStatus(statusRes);
      setBrightnessStatus(brightnessRes);
    } catch (e) {
      if (mountedRef.current) setError(e instanceof Error ? e.message : 'Failed to load overlay data');
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
    castSessions,
    status,
    brightnessStatus,
    load,
    runAction,
  };
}
