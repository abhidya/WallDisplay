import { useCallback, useEffect, useMemo, useState } from 'react';

import { type ControlPlaneClient } from '../../control-plane/client.ts';
import type {
  DiscoverySystemStatus,
  HealthResponse,
  ProjectionConfigSummary,
  RendererInstanceSummary,
  StreamingAnalytics,
  DeviceSummary,
} from '../../types/api';

export interface OverviewController {
  devices: DeviceSummary[];
  error: string | null;
  health: HealthResponse | null;
  loading: boolean;
  projections: ProjectionConfigSummary[];
  renderers: RendererInstanceSummary[];
  streaming: StreamingAnalytics | null;
  unifiedDiscovery: DiscoverySystemStatus | null;
  load: () => Promise<void>;
}

export function useOverviewController(client: ControlPlaneClient): OverviewController {
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [streaming, setStreaming] = useState<StreamingAnalytics | null>(null);
  const [renderers, setRenderers] = useState<RendererInstanceSummary[]>([]);
  const [projections, setProjections] = useState<ProjectionConfigSummary[]>([]);
  const [unifiedDiscovery, setUnifiedDiscovery] = useState<DiscoverySystemStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        healthPayload,
        devicesPayload,
        streamingPayload,
        renderersPayload,
        projectionsPayload,
        unifiedDiscoveryPayload,
      ] = await Promise.all([
        client.getHealth(),
        client.listDevices(),
        client.getStreamingAnalytics(),
        client.listRenderers(),
        client.listProjectionConfigs(),
        client.getUnifiedDiscoveryStatus(),
      ]);

      setHealth(healthPayload);
      setDevices(devicesPayload);
      setStreaming(streamingPayload);
      setRenderers(renderersPayload);
      setProjections(projectionsPayload);
      setUnifiedDiscovery(unifiedDiscoveryPayload);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load overview summary.');
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  return useMemo(
    () => ({
      devices,
      error,
      health,
      load,
      loading,
      projections,
      renderers,
      streaming,
      unifiedDiscovery,
    }),
    [devices, error, health, load, loading, projections, renderers, streaming, unifiedDiscovery],
  );
}
