import { useCallback, useEffect, useMemo, useState } from 'react';

import type { ControlPlaneClient } from '../../control-plane/client.ts';
import type { AppMode } from '../../control-plane/localState.ts';
import { normalizeApiBaseUrl } from '../../services/api.ts';
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
  appMode: AppMode;
}

export function useSettingsController(
  client: ControlPlaneClient,
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
      setActionMessage(
        options.appMode === 'local'
          ? 'Local control plane is ready.'
          : 'Remote adapter reached the configured backend.',
      );
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : options.appMode === 'local'
            ? 'Failed to initialize local control plane.'
            : 'Failed to reach the configured backend.',
      );
    } finally {
      setLoading(false);
    }
  }, [client, options.appMode]);

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
