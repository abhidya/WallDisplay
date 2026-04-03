import { useCallback, useMemo, useState } from 'react';

import {
  DEFAULT_API_BASE_URL,
  NanoDlnaApiClient,
  normalizeApiBaseUrl,
} from '../../services/api';

export type TabKey = 'overview' | 'devices' | 'media' | 'operations' | 'settings';

export interface TabDefinition {
  key: TabKey;
  label: string;
}

export interface AppShellController {
  activeTab: TabKey;
  apiBaseUrl: string;
  client: NanoDlnaApiClient;
  selectedDeviceId: number | string | null;
  selectedDeviceLabel: string | null;
  setActiveTab: (tab: TabKey) => void;
  applyApiBaseUrl: (value: string) => void;
  selectDevice: (deviceId: number | string | null, label: string | null) => void;
}

export const tabs: TabDefinition[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'devices', label: 'Devices' },
  { key: 'media', label: 'Media' },
  { key: 'operations', label: 'Ops' },
  { key: 'settings', label: 'Settings' },
];

export function useAppShell(): AppShellController {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | string | null>(null);
  const [selectedDeviceLabel, setSelectedDeviceLabel] = useState<string | null>(null);

  const client = useMemo(() => new NanoDlnaApiClient(apiBaseUrl), [apiBaseUrl]);

  const applyApiBaseUrl = useCallback((value: string) => {
    setApiBaseUrl(normalizeApiBaseUrl(value));
  }, []);

  const selectDevice = useCallback((deviceId: number | string | null, label: string | null) => {
    setSelectedDeviceId(deviceId);
    setSelectedDeviceLabel(label);
  }, []);

  return {
    activeTab,
    apiBaseUrl,
    client,
    selectedDeviceId,
    selectedDeviceLabel,
    setActiveTab,
    applyApiBaseUrl,
    selectDevice,
  };
}
