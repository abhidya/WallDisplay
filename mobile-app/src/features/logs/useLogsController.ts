import { useCallback, useEffect, useMemo, useState } from 'react';

import { createControlPlaneClient } from '../../control-plane/client.ts';
import type { AppMode } from '../../control-plane/localState.ts';
import {
  createHttpClient,
  normalizeApiBaseUrl,
  type QueryRecord,
} from '../../services/httpClient.ts';
import type { JsonRecord } from '../../types/api.ts';

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function asRecordArray(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) as JsonRecord[]
    : [];
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.length > 0)
    : [];
}

function readRecordArray(payload: unknown, key: string): JsonRecord[] {
  const record = asRecord(payload);
  return asRecordArray(record?.[key] ?? payload);
}

function readStringArray(payload: unknown, key: string): string[] {
  const record = asRecord(payload);
  return asStringArray(record?.[key] ?? payload);
}

export interface LogsRemoteClient {
  getLevels: () => Promise<JsonRecord>;
  getLogs: (params?: QueryRecord) => Promise<JsonRecord>;
  getSources: () => Promise<JsonRecord>;
  getStats: () => Promise<JsonRecord>;
  tailSource: (source: string, lines?: number) => Promise<JsonRecord>;
}

export function createLogsRemoteClient(
  apiBaseUrl: string,
  fetchImpl: typeof fetch = globalThis.fetch,
): LogsRemoteClient {
  const api = createHttpClient({
    baseURL: normalizeApiBaseUrl(apiBaseUrl),
    normalizeApiBase: false,
    fetchImpl,
  });

  return {
    getLevels: () => api.get<JsonRecord>('/logs/levels'),
    getLogs: (params: QueryRecord = {}) => api.get<JsonRecord>('/logs', { query: params }),
    getSources: () => api.get<JsonRecord>('/logs/sources'),
    getStats: () => api.get<JsonRecord>('/logs/stats'),
    tailSource: (source: string, lines = 50) =>
      api.get<JsonRecord>(`/logs/tail/${encodeURIComponent(source)}`, {
        query: { lines },
      }),
  };
}

export function createLogsClient(
  appMode: AppMode,
  apiBaseUrl: string,
  fetchImpl: typeof fetch = globalThis.fetch,
): LogsRemoteClient {
  if (appMode === 'local') {
    const seamClient = createControlPlaneClient('local', apiBaseUrl);
    return {
      getLevels: () => seamClient.getLogLevels(),
      getLogs: (params: QueryRecord = {}) => seamClient.getLogs(params),
      getSources: () => seamClient.getLogSources(),
      getStats: () => seamClient.getLogStats(),
      tailSource: (source: string, lines = DEFAULT_TAIL_LINES) =>
        seamClient.tailLogSource(source, lines),
    };
  }

  return createLogsRemoteClient(apiBaseUrl, fetchImpl);
}

export interface LogsController {
  error: string | null;
  levels: string[];
  loading: boolean;
  logs: JsonRecord[];
  refresh: () => Promise<void>;
  search: string;
  selectedSource: string;
  setSearch: (value: string) => void;
  setSelectedSource: (value: string) => void;
  sources: string[];
  stats: JsonRecord | null;
  tail: JsonRecord[];
}

interface UseLogsControllerOptions {
  apiBaseUrl: string;
  appMode: AppMode;
}

const DEFAULT_LOG_LIMIT = 100;
const DEFAULT_LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
const DEFAULT_TAIL_LINES = 50;

export function useLogsController(options: UseLogsControllerOptions): LogsController {
  const client = useMemo(
    () => createLogsClient(options.appMode, options.apiBaseUrl),
    [options.apiBaseUrl, options.appMode],
  );
  const [search, setSearch] = useState('');
  const [selectedSource, setSelectedSource] = useState('');
  const [sources, setSources] = useState<string[]>([]);
  const [levels, setLevels] = useState<string[]>(DEFAULT_LOG_LEVELS);
  const [stats, setStats] = useState<JsonRecord | null>(null);
  const [logs, setLogs] = useState<JsonRecord[]>([]);
  const [tail, setTail] = useState<JsonRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sourcesPayload, levelsPayload, statsPayload] = await Promise.all([
        client.getSources(),
        client.getLevels(),
        client.getStats(),
      ]);

      const nextSources = readStringArray(sourcesPayload, 'sources');
      const nextLevels = readStringArray(levelsPayload, 'levels');
      const nextSelectedSource =
        nextSources.find((source) => source === selectedSource) ?? nextSources[0] ?? '';

      const [logsPayload, tailPayload] = await Promise.all([
        client.getLogs({
          limit: DEFAULT_LOG_LIMIT,
          search: search || undefined,
          sources: nextSelectedSource ? [nextSelectedSource] : undefined,
        }),
        nextSelectedSource
          ? client.tailSource(nextSelectedSource, DEFAULT_TAIL_LINES)
          : Promise.resolve({ logs: [] }),
      ]);

      setSources(nextSources);
      setLevels(nextLevels.length > 0 ? nextLevels : DEFAULT_LOG_LEVELS);
      setStats(asRecord(statsPayload));
      setSelectedSource(nextSelectedSource);
      setLogs(readRecordArray(logsPayload, 'logs'));
      setTail(readRecordArray(tailPayload, 'logs'));
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : 'Failed to load logs.');
    } finally {
      setLoading(false);
    }
  }, [client, options.appMode, search, selectedSource]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    error,
    levels,
    loading,
    logs,
    refresh,
    search,
    selectedSource,
    setSearch,
    setSelectedSource,
    sources,
    stats,
    tail,
  };
}
