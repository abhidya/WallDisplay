import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  createControlPlaneClient,
  DEFAULT_REMOTE_API_BASE_URL,
  type ControlPlaneClient,
} from '../../control-plane/client.ts';
import {
  defaultAppState,
  type AppMode,
  loadLocalControlPlaneState,
  updateLocalControlPlaneState,
  updateSelectedDeviceInState,
} from '../../control-plane/localState.ts';
import { normalizeApiBaseUrl } from '../../services/api.ts';

export type TabKey =
  | 'overview'
  | 'devices'
  | 'media'
  | 'operations'
  | 'lighting'
  | 'depth'
  | 'projection'
  | 'overlay'
  | 'logs'
  | 'settings';

export interface TabDefinition {
  key: TabKey;
  label: string;
}

export interface AppShellController {
  activeTab: TabKey;
  appMode: AppMode;
  apiBaseUrl: string;
  client: ControlPlaneClient;
  hydrated: boolean;
  selectedDeviceId: number | string | null;
  selectedDeviceLabel: string | null;
  setActiveTab: (tab: TabKey) => void;
  applyApiBaseUrl: (value: string) => void;
  applyAppMode: (mode: AppMode) => void;
  selectDevice: (deviceId: number | string | null, label: string | null) => void;
}

export const tabs: TabDefinition[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'devices', label: 'Devices' },
  { key: 'media', label: 'Media' },
  { key: 'operations', label: 'Ops' },
  { key: 'lighting', label: 'Lighting' },
  { key: 'depth', label: 'Depth' },
  { key: 'projection', label: 'Projection' },
  { key: 'overlay', label: 'Overlay' },
  { key: 'logs', label: 'Logs' },
  { key: 'settings', label: 'Settings' },
];

export function useAppShell(): AppShellController {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [hydrated, setHydrated] = useState(false);
  const [appMode, setAppMode] = useState<AppMode>(defaultAppState.mode);
  const [apiBaseUrl, setApiBaseUrl] = useState(
    normalizeApiBaseUrl(defaultAppState.apiBaseUrl || DEFAULT_REMOTE_API_BASE_URL),
  );
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | string | null>(
    defaultAppState.selectedDeviceId,
  );
  const [selectedDeviceLabel, setSelectedDeviceLabel] = useState<string | null>(
    defaultAppState.selectedDeviceLabel,
  );

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const state = await loadLocalControlPlaneState();
      if (cancelled) {
        return;
      }
      setAppMode(state.app.mode);
      setApiBaseUrl(normalizeApiBaseUrl(state.app.apiBaseUrl || DEFAULT_REMOTE_API_BASE_URL));
      setSelectedDeviceId(state.app.selectedDeviceId);
      setSelectedDeviceLabel(state.app.selectedDeviceLabel);
      setHydrated(true);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const client = useMemo(() => createControlPlaneClient(appMode, apiBaseUrl), [appMode, apiBaseUrl]);

  const applyApiBaseUrl = useCallback((value: string) => {
    const normalized = normalizeApiBaseUrl(value);
    setApiBaseUrl(normalized);
    void updateLocalControlPlaneState((state) => ({
      ...state,
      app: {
        ...state.app,
        apiBaseUrl: normalized,
      },
    }));
  }, []);

  const applyAppMode = useCallback((mode: AppMode) => {
    setAppMode(mode);
    void updateLocalControlPlaneState((state) => ({
      ...state,
      app: {
        ...state.app,
        mode,
      },
    }));
  }, []);

  const selectDevice = useCallback((deviceId: number | string | null, label: string | null) => {
    setSelectedDeviceId(deviceId);
    setSelectedDeviceLabel(label);
    void updateLocalControlPlaneState((state) => updateSelectedDeviceInState(state, deviceId, label));
  }, []);

  return {
    activeTab,
    appMode,
    apiBaseUrl,
    client,
    hydrated,
    selectedDeviceId,
    selectedDeviceLabel,
    setActiveTab,
    applyApiBaseUrl,
    applyAppMode,
    selectDevice,
  };
}
