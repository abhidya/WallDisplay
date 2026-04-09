import { useCallback, useEffect, useMemo, useState } from 'react';

import type { ControlPlaneClient } from '../../control-plane/client.ts';
import type { AppMode } from '../../control-plane/localState.ts';
import { normalizeApiBaseUrl } from '../../services/api.ts';
import type { DiscoverySystemStatus, HealthResponse, JsonRecord } from '../../types/api';
import {
  createRedirectRule,
  DEFAULT_PROJECTOR_REDIRECT_TARGET,
  normalizeProjectorRedirectConfig,
  selectPreferredIncidentId,
  type ProjectorRedirectConfig,
  type ProjectorRedirectRule,
} from './helpers.ts';

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function asArray(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) as JsonRecord[]
    : [];
}

export interface SettingsController {
  actionMessage: string | null;
  adminError: string | null;
  adminLoading: boolean;
  diagnosticsLoading: boolean;
  draftValue: string;
  error: string | null;
  globalApiConfigs: JsonRecord;
  health: HealthResponse | null;
  incidentDetailLoading: boolean;
  loading: boolean;
  normalized: string;
  projectorRedirect: ProjectorRedirectConfig;
  recentProjectorRequests: JsonRecord[];
  selectedIncidentDetail: JsonRecord | null;
  selectedIncidentId: string;
  serviceDiagnostics: JsonRecord | null;
  unifiedDiscovery: DiscoverySystemStatus | null;
  setDraftValue: (value: string) => void;
  refreshConnection: () => Promise<void>;
  refreshRemoteAdmin: (preserveSelection?: boolean) => Promise<void>;
  saveRemoteAdmin: () => Promise<void>;
  setSelectedIncidentId: (incidentId: string) => void;
  updateGlobalApiConfig: (key: string, value: string) => void;
  updateProjectorRedirectRule: (ruleId: string, patch: Partial<ProjectorRedirectRule>) => void;
  addProjectorRedirectRule: () => void;
  removeProjectorRedirectRule: (ruleId: string) => void;
  toggleProjectorRedirectEnabled: (enabled: boolean) => void;
}

interface UseSettingsControllerOptions {
  apiBaseUrl: string;
  appMode: AppMode;
}

const defaultGlobalApiConfigs: JsonRecord = {
  weather_api_key: '',
  transit_stop_id: '13915',
  timezone: 'America/Los_Angeles',
};

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

  const [adminLoading, setAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [incidentDetailLoading, setIncidentDetailLoading] = useState(false);
  const [globalApiConfigs, setGlobalApiConfigs] = useState<JsonRecord>(defaultGlobalApiConfigs);
  const [projectorRedirect, setProjectorRedirect] = useState<ProjectorRedirectConfig>(
    normalizeProjectorRedirectConfig(null),
  );
  const [recentProjectorRequests, setRecentProjectorRequests] = useState<JsonRecord[]>([]);
  const [serviceDiagnostics, setServiceDiagnostics] = useState<JsonRecord | null>(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState('');
  const [selectedIncidentDetail, setSelectedIncidentDetail] = useState<JsonRecord | null>(null);

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

  const refreshRemoteAdmin = useCallback(
    async (preserveSelection = true) => {
      if (options.appMode !== 'remote') {
        setAdminError(null);
        setServiceDiagnostics(null);
        setSelectedIncidentId('');
        setSelectedIncidentDetail(null);
        return;
      }

      setAdminLoading(true);
      setDiagnosticsLoading(true);
      setAdminError(null);
      try {
        const [
          apiConfigsPayload,
          projectorRedirectPayload,
          recentRequestsPayload,
          diagnosticsPayload,
        ] = await Promise.all([
          client.getGlobalApiConfigs(),
          client.getProjectorRedirectConfig(),
          client.getRecentProjectorRedirectRequests(),
          client.getServiceDiagnostics({
            incident_limit: 8,
            run_limit: 8,
            supervisor_limit: 8,
          }),
        ]);

        setGlobalApiConfigs({
          ...defaultGlobalApiConfigs,
          ...(asRecord(apiConfigsPayload) ?? {}),
        });
        setProjectorRedirect(normalizeProjectorRedirectConfig(projectorRedirectPayload));
        setRecentProjectorRequests(
          asArray(asRecord(recentRequestsPayload)?.items ?? recentRequestsPayload),
        );
        const diagnosticsRecord = asRecord(diagnosticsPayload);
        setServiceDiagnostics(diagnosticsRecord);
        setSelectedIncidentId((current) =>
          selectPreferredIncidentId(diagnosticsRecord, current, preserveSelection),
        );
      } catch (adminLoadError) {
        setAdminError(
          adminLoadError instanceof Error
            ? adminLoadError.message
            : 'Failed to load remote admin settings.',
        );
      } finally {
        setAdminLoading(false);
        setDiagnosticsLoading(false);
      }
    },
    [client, options.appMode],
  );

  const saveRemoteAdmin = useCallback(async () => {
    if (options.appMode !== 'remote') {
      setAdminError('Switch to remote mode before saving backend admin settings.');
      return;
    }

    setAdminLoading(true);
    setAdminError(null);
    setActionMessage(null);
    try {
      await Promise.all([
        client.updateGlobalApiConfigs(globalApiConfigs),
        client.updateProjectorRedirectConfig(projectorRedirect),
      ]);
      setActionMessage('Remote settings saved.');
      await refreshRemoteAdmin(true);
    } catch (saveError) {
      setAdminError(saveError instanceof Error ? saveError.message : 'Failed to save remote settings.');
    } finally {
      setAdminLoading(false);
    }
  }, [client, globalApiConfigs, options.appMode, projectorRedirect, refreshRemoteAdmin]);

  const updateGlobalApiConfig = useCallback((key: string, value: string) => {
    setGlobalApiConfigs((current) => ({
      ...current,
      [key]: value,
    }));
  }, []);

  const updateProjectorRedirectRule = useCallback(
    (ruleId: string, patch: Partial<ProjectorRedirectRule>) => {
      setProjectorRedirect((current) => {
        const rules = current.rules.map((rule) =>
          rule.id === ruleId ? { ...rule, ...patch } : rule,
        );
        const activeRule = rules.find((rule) => rule.enabled) ?? rules[0];
        return {
          ...current,
          rules,
          enabled: current.enabled && rules.some((rule) => rule.enabled),
          client_ip: activeRule?.client_ip ?? '',
          target_path: activeRule?.target_path ?? DEFAULT_PROJECTOR_REDIRECT_TARGET,
        };
      });
    },
    [],
  );

  const addProjectorRedirectRule = useCallback(() => {
    setProjectorRedirect((current) => ({
      ...current,
      rules: [...current.rules, createRedirectRule(current.rules.length + 1)],
    }));
  }, []);

  const removeProjectorRedirectRule = useCallback((ruleId: string) => {
    setProjectorRedirect((current) => {
      const rules = current.rules.filter((rule) => rule.id !== ruleId);
      const safeRules = rules.length > 0 ? rules : [createRedirectRule()];
      const activeRule = safeRules.find((rule) => rule.enabled) ?? safeRules[0];
      return {
        ...current,
        rules: safeRules,
        enabled: safeRules.some((rule) => rule.enabled),
        client_ip: activeRule?.client_ip ?? '',
        target_path: activeRule?.target_path ?? DEFAULT_PROJECTOR_REDIRECT_TARGET,
      };
    });
  }, []);

  const toggleProjectorRedirectEnabled = useCallback((enabled: boolean) => {
    setProjectorRedirect((current) => ({
      ...current,
      enabled,
    }));
  }, []);

  useEffect(() => {
    void refreshConnection();
  }, [refreshConnection]);

  useEffect(() => {
    void refreshRemoteAdmin(false);
  }, [refreshRemoteAdmin]);

  useEffect(() => {
    if (options.appMode !== 'remote' || !selectedIncidentId) {
      setSelectedIncidentDetail(null);
      return;
    }

    let cancelled = false;

    void (async () => {
      setIncidentDetailLoading(true);
      try {
        const detailPayload = await client.getIncidentDetail(selectedIncidentId, {
          context_minutes: 3,
        });
        if (!cancelled) {
          setSelectedIncidentDetail(asRecord(detailPayload));
        }
      } catch {
        if (!cancelled) {
          setSelectedIncidentDetail(null);
        }
      } finally {
        if (!cancelled) {
          setIncidentDetailLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [client, options.appMode, selectedIncidentId]);

  return useMemo(
    () => ({
      actionMessage,
      adminError,
      adminLoading,
      diagnosticsLoading,
      draftValue,
      error,
      globalApiConfigs,
      health,
      incidentDetailLoading,
      loading,
      normalized: normalizeApiBaseUrl(draftValue),
      projectorRedirect,
      recentProjectorRequests,
      refreshConnection,
      refreshRemoteAdmin,
      saveRemoteAdmin,
      selectedIncidentDetail,
      selectedIncidentId,
      serviceDiagnostics,
      setDraftValue,
      setSelectedIncidentId,
      toggleProjectorRedirectEnabled,
      unifiedDiscovery,
      updateGlobalApiConfig,
      updateProjectorRedirectRule,
      addProjectorRedirectRule,
      removeProjectorRedirectRule,
    }),
    [
      actionMessage,
      adminError,
      adminLoading,
      diagnosticsLoading,
      draftValue,
      error,
      globalApiConfigs,
      health,
      incidentDetailLoading,
      loading,
      projectorRedirect,
      recentProjectorRequests,
      refreshConnection,
      refreshRemoteAdmin,
      saveRemoteAdmin,
      selectedIncidentDetail,
      selectedIncidentId,
      serviceDiagnostics,
      toggleProjectorRedirectEnabled,
      unifiedDiscovery,
      updateGlobalApiConfig,
      updateProjectorRedirectRule,
      addProjectorRedirectRule,
      removeProjectorRedirectRule,
    ],
  );
}
