import { useCallback, useEffect, useRef, useState } from 'react';
import type { StructuredLightingModule } from '../../control-plane/modules.ts';
import type { JsonRecord } from '../../types/api.ts';

export interface StructuredLightingController {
  loading: boolean;
  actionLoadingKey: string | null;
  error: string | null;
  capabilities: JsonRecord | null;
  status: JsonRecord | null;
  sessions: JsonRecord[];
  load: () => Promise<void>;
  runAction: <T>(actionKey: string, handler: () => Promise<T>) => Promise<T | undefined>;
}

export function useStructuredLightingController(client: StructuredLightingModule): StructuredLightingController {
  const [capabilities, setCapabilities] = useState<JsonRecord | null>(null);
  const [status, setStatus] = useState<JsonRecord | null>(null);
  const [sessions, setSessions] = useState<JsonRecord[]>([]);
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
      const [capRes, statRes, sessRes] = await Promise.all([
        client.getStructuredLightingCapabilities(),
        client.getStructuredLightingStatus(),
        client.listStructuredLightingSessions(),
      ]);
      if (!mountedRef.current) return;
      setCapabilities(capRes);
      setStatus(statRes);
      setSessions(sessRes);
    } catch (e) {
      if (mountedRef.current) setError(e instanceof Error ? e.message : 'Failed to load structured lighting data');
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
    capabilities,
    status,
    sessions,
    load,
    runAction,
  };
}
