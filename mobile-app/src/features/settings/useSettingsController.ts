import { useCallback, useEffect, useMemo, useState } from 'react';

import { NanoDlnaApiClient, normalizeApiBaseUrl } from '../../services/api';
import type { DiscoverySystemStatus, HealthResponse } from '../../types/api';

export interface SettingsController {
  actionMessage: string | null;
  draftValue: string;
  error: string | null;
  health: HealthResponse | null;
  loading: boolean;
  normalized: string;
  unifiedDiscovery: DiscoverySystemStatus | null;
  setDraftValue: (value: string) => void;
  refreshConnection: () => Promise<void>;
}

interface UseSettingsControllerOptions {
  apiBaseUrl: string;
}

export function useSettingsController(
  client: NanoDlnaApiClient,
  options: UseSettingsControllerOptions,
): SettingsController {
  const [draftValue, setDraftValue] = useState(options.apiBaseUrl);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [unifiedDiscovery, setUnifiedDiscovery] = useState<DiscoverySystemStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    setDraftValue(options.apiBaseUrl);
  }, [options.apiBaseUrl]);

  const refreshConnection = useCallback(async () => {
    setLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const [healthPayload, discoveryPayload] = await Promise.all([
        client.getHealth(),
        client.getUnifiedDiscoveryStatus(),
      ]);
      setHealth(healthPayload);
      setUnifiedDiscovery(discoveryPayload);
      setActionMessage('Connection check succeeded.');
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : 'Failed to reach the configured backend.',
      );
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void refreshConnection();
  }, [refreshConnection]);

  return useMemo(
    () => ({
      actionMessage,
      draftValue,
      error,
      health,
      loading,
      normalized: normalizeApiBaseUrl(draftValue),
      refreshConnection,
      setDraftValue,
      unifiedDiscovery,
    }),
    [
      actionMessage,
      draftValue,
      error,
      health,
      loading,
      refreshConnection,
      unifiedDiscovery,
    ],
  );
}
