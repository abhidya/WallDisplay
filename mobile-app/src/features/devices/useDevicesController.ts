import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { NanoDlnaApiClient } from '../../services/api';
import type {
  DiscoveryBackendSummary,
  DiscoveryCapabilities,
  DeviceActionResponse,
  DeviceControlMode,
  DeviceDetail,
  DeviceSummary,
  DiscoveryStatus,
  DiscoverySystemStatus,
  HealthResponse,
} from '../../types/api';

export interface DevicesController {
  actionLoadingKey: string | null;
  actionMessage: string | null;
  activeDeviceId: number | string | null;
  controlMode: DeviceControlMode | null;
  detailLoading: boolean;
  devices: DeviceSummary[];
  discovering: boolean;
  discoveryPaused: boolean;
  discoveryStatus: DiscoveryStatus | null;
  discoveryBackends: DiscoveryBackendSummary[];
  unifiedDiscoveryCapabilities: DiscoveryCapabilities | null;
  unifiedDiscoveryStatus: DiscoverySystemStatus | null;
  error: string | null;
  health: HealthResponse | null;
  loading: boolean;
  selectedDevice: DeviceDetail | null;
  selectedDeviceId: number | string | null;
  selectDevice: (deviceId: number | string | null) => void;
  load: () => Promise<void>;
  discover: () => Promise<void>;
  refreshSelectedDevice: () => Promise<void>;
  runDiscoveryBackendToggle: (
    backendName: string,
    enabled: boolean | null | undefined,
  ) => Promise<void>;
  runDiscoveryToggle: () => Promise<void>;
  runSelectedDeviceAction: (
    actionKey: string,
    handler: (deviceId: number | string) => Promise<DeviceActionResponse>,
  ) => Promise<void>;
}

interface UseDevicesControllerOptions {
  sharedSelectedDeviceId?: number | string | null;
  onSelectionChange?: (deviceId: number | string | null, label: string | null) => void;
}

function isPresent<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined;
}

function describeDevice(device: DeviceSummary): string {
  return (
    (typeof device.friendly_name === 'string' && device.friendly_name) ||
    (typeof device.device_name === 'string' && device.device_name) ||
    (typeof device.name === 'string' && device.name) ||
    `Device ${String(device.id ?? 'unknown')}`
  );
}

export function useDevicesController(
  client: NanoDlnaApiClient,
  options?: UseDevicesControllerOptions,
): DevicesController {
  const sharedSelectedDeviceId = options?.sharedSelectedDeviceId;
  const onSelectionChange = options?.onSelectionChange;
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [discoveryStatus, setDiscoveryStatus] = useState<DiscoveryStatus | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | string | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<DeviceDetail | null>(null);
  const [controlMode, setControlMode] = useState<DeviceControlMode | null>(null);
  const [discoveryBackends, setDiscoveryBackends] = useState<DiscoveryBackendSummary[]>([]);
  const [unifiedDiscoveryCapabilities, setUnifiedDiscoveryCapabilities] =
    useState<DiscoveryCapabilities | null>(null);
  const [unifiedDiscoveryStatus, setUnifiedDiscoveryStatus] =
    useState<DiscoverySystemStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoadingKey, setActionLoadingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const loadRequestRef = useRef(0);
  const detailRequestRef = useRef(0);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    const requestId = ++loadRequestRef.current;
    setLoading(true);
    setError(null);
    try {
      const [healthPayload, devicePayload, discoveryPayload, unifiedStatusResult, unifiedCapabilitiesResult, backendsResult] = await Promise.all([
        client.getHealth(),
        client.listDevices(),
        client.getDiscoveryStatus(),
        client.getUnifiedDiscoveryStatus(),
        client.getUnifiedDiscoveryCapabilities(),
        client.listDiscoveryBackends(),
      ]);

      if (!mountedRef.current || requestId !== loadRequestRef.current) {
        return;
      }

      setHealth(healthPayload);
      setDevices(devicePayload);
      setDiscoveryStatus(discoveryPayload);
      setUnifiedDiscoveryStatus(unifiedStatusResult);
      setUnifiedDiscoveryCapabilities(unifiedCapabilitiesResult);
      setDiscoveryBackends(backendsResult);
      setSelectedDeviceId((current) => {
        if (current === null) {
          return devicePayload[0]?.id ?? null;
        }
        return devicePayload.some((device) => String(device.id) === String(current))
          ? current
          : (devicePayload[0]?.id ?? null);
      });
    } catch (loadError) {
      if (!mountedRef.current || requestId !== loadRequestRef.current) {
        return;
      }
      setError(loadError instanceof Error ? loadError.message : 'Failed to load devices.');
    } finally {
      if (mountedRef.current && requestId === loadRequestRef.current) {
        setLoading(false);
      }
    }
  }, [client]);

  const loadSelectedDevice = useCallback(
    async (deviceId: number | string) => {
      const requestId = ++detailRequestRef.current;
      setDetailLoading(true);
      try {
        const [devicePayload, controlPayload] = await Promise.all([
          client.getDevice(deviceId),
          client.getDeviceControlMode(deviceId),
        ]);

        if (!mountedRef.current || requestId !== detailRequestRef.current) {
          return;
        }

        setSelectedDevice(devicePayload);
        setControlMode(controlPayload);
      } catch (loadError) {
        if (!mountedRef.current || requestId !== detailRequestRef.current) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : 'Failed to load device detail.');
      } finally {
        if (mountedRef.current && requestId === detailRequestRef.current) {
          setDetailLoading(false);
        }
      }
    },
    [client],
  );

  const refreshSelectedDevice = useCallback(async () => {
    if (!isPresent(selectedDeviceId)) {
      return;
    }
    await loadSelectedDevice(selectedDeviceId);
  }, [loadSelectedDevice, selectedDeviceId]);

  const handleDeviceAction = useCallback(
    async (
      actionKey: string,
      handler: () => Promise<DeviceActionResponse>,
      successFollowUp?: () => Promise<void>,
    ) => {
      setActionLoadingKey(actionKey);
      setError(null);
      setActionMessage(null);
      try {
        const response = await handler();
        if (!mountedRef.current) {
          return;
        }
        setActionMessage(response.message ?? 'Action completed.');
        await load();
        if (successFollowUp) {
          await successFollowUp();
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

  const discover = useCallback(async () => {
    setDiscovering(true);
    setError(null);
    try {
      await client.discoverDevices();
      await load();
    } catch (discoverError) {
      if (mountedRef.current) {
        setError(
          discoverError instanceof Error ? discoverError.message : 'Device discovery failed.',
        );
      }
    } finally {
      if (mountedRef.current) {
        setDiscovering(false);
      }
    }
  }, [client, load]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!isPresent(selectedDeviceId)) {
      setSelectedDevice(null);
      setControlMode(null);
      return;
    }
    void loadSelectedDevice(selectedDeviceId);
  }, [loadSelectedDevice, selectedDeviceId]);

  const selectedSummary = useMemo(
    () => devices.find((device) => String(device.id) === String(selectedDeviceId)) ?? null,
    [devices, selectedDeviceId],
  );

  useEffect(() => {
    if (
      sharedSelectedDeviceId !== undefined &&
      String(sharedSelectedDeviceId) !== String(selectedDeviceId)
    ) {
      setSelectedDeviceId(sharedSelectedDeviceId);
    }
  }, [sharedSelectedDeviceId, selectedDeviceId]);

  useEffect(() => {
    onSelectionChange?.(selectedDeviceId, selectedSummary ? describeDevice(selectedSummary) : null);
  }, [onSelectionChange, selectedDeviceId, selectedSummary]);

  const activeDeviceId = selectedSummary?.id ?? selectedDeviceId;
  const discoveryPaused = Boolean(discoveryStatus?.paused);

  const runDiscoveryToggle = useCallback(async () => {
    await handleDeviceAction(
      discoveryPaused ? 'resume-discovery' : 'pause-discovery',
      () => (discoveryPaused ? client.resumeDiscovery() : client.pauseDiscovery()),
    );
  }, [client, discoveryPaused, handleDeviceAction]);

  const runDiscoveryBackendToggle = useCallback(
    async (backendName: string, enabled: boolean | null | undefined) => {
      if (!backendName) {
        return;
      }

      await handleDeviceAction(
        `${enabled ? 'disable' : 'enable'}-backend-${backendName}`,
        () =>
          enabled
            ? client.disableDiscoveryBackend(backendName)
            : client.enableDiscoveryBackend(backendName),
      );
    },
    [client, handleDeviceAction],
  );

  const runSelectedDeviceAction = useCallback(
    async (
      actionKey: string,
      handler: (deviceId: number | string) => Promise<DeviceActionResponse>,
    ) => {
      if (!isPresent(activeDeviceId)) {
        return;
      }
      await handleDeviceAction(actionKey, () => handler(activeDeviceId), refreshSelectedDevice);
    },
    [activeDeviceId, handleDeviceAction, refreshSelectedDevice],
  );

  return {
    actionLoadingKey,
    actionMessage,
    activeDeviceId,
    controlMode,
    detailLoading,
    devices,
    discovering,
    discoveryPaused,
    discoveryStatus,
    discoveryBackends,
    error,
    health,
    loading,
    selectedDevice,
    selectedDeviceId,
    unifiedDiscoveryCapabilities,
    unifiedDiscoveryStatus,
    selectDevice: setSelectedDeviceId,
    load,
    discover,
    refreshSelectedDevice,
    runDiscoveryBackendToggle,
    runDiscoveryToggle,
    runSelectedDeviceAction,
  };
}
