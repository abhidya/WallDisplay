import { useCallback, useEffect, useMemo, useState } from 'react';

import { createServiceModules } from '../../services/api.ts';
import type { AppMode } from '../../control-plane/localState.ts';
import type { JsonRecord } from '../../types/api.ts';

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

export interface StructuredLightingController {
  actionLoading: boolean;
  actionMessage: string | null;
  capabilities: JsonRecord | null;
  captures: JsonRecord[];
  createSession: () => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  error: string | null;
  form: {
    name: string;
    projector_device_id: string;
    camera_index: string;
    projector_width: string;
    projector_height: string;
    presentation_mode: string;
    hold_ms: string;
    notes: string;
  };
  loading: boolean;
  projectors: JsonRecord[];
  refresh: () => Promise<void>;
  runtime: JsonRecord | null;
  selectedSessionId: string;
  selectSession: (sessionId: string) => void;
  sessions: JsonRecord[];
  startSession: (sessionId: string) => Promise<void>;
  status: JsonRecord | null;
  updateForm: (key: string, value: string) => void;
}

interface UseStructuredLightingControllerOptions {
  apiBaseUrl: string;
  appMode: AppMode;
}

const defaultForm = {
  name: 'Wall Calibration',
  projector_device_id: '',
  camera_index: '1',
  projector_width: '1280',
  projector_height: '720',
  presentation_mode: 'dlna_step',
  hold_ms: '1200',
  notes: '',
};

export function useStructuredLightingController(
  options: UseStructuredLightingControllerOptions,
): StructuredLightingController {
  const services = useMemo(() => createServiceModules(options.apiBaseUrl), [options.apiBaseUrl]);
  const [capabilities, setCapabilities] = useState<JsonRecord | null>(null);
  const [status, setStatus] = useState<JsonRecord | null>(null);
  const [sessions, setSessions] = useState<JsonRecord[]>([]);
  const [projectors, setProjectors] = useState<JsonRecord[]>([]);
  const [runtime, setRuntime] = useState<JsonRecord | null>(null);
  const [captures, setCaptures] = useState<JsonRecord[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [form, setForm] = useState(defaultForm);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (options.appMode !== 'remote') {
      setCapabilities(null);
      setStatus(null);
      setSessions([]);
      setProjectors([]);
      setRuntime(null);
      setCaptures([]);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [capabilitiesPayload, statusPayload, sessionsPayload, projectorPayload] =
        await Promise.all([
          services.structuredLightingApi.getCapabilities(),
          services.structuredLightingApi.getStatus(),
          services.structuredLightingApi.listSessions(),
          services.discoveryV2Api.getDevices({ casting_method: 'dlna' }),
        ]);

      const nextSessions = asArray(sessionsPayload);
      const nextProjectors = asArray(projectorPayload);
      setCapabilities(asRecord(capabilitiesPayload));
      setStatus(asRecord(statusPayload));
      setSessions(nextSessions);
      setProjectors(nextProjectors);
      setSelectedSessionId((current) => current || String(nextSessions[0]?.session_id ?? ''));
      setForm((current) =>
        current.projector_device_id || nextProjectors.length === 0
          ? current
          : {
              ...current,
              projector_device_id: String(
                nextProjectors[0]?.device_id ?? nextProjectors[0]?.id ?? '',
              ),
            },
      );
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : 'Failed to load structured lighting data.',
      );
    } finally {
      setLoading(false);
    }
  }, [options.appMode, services]);

  const refreshSessionDetails = useCallback(async () => {
    if (options.appMode !== 'remote' || !selectedSessionId) {
      setRuntime(null);
      setCaptures([]);
      return;
    }

    try {
      const [runtimePayload, capturesPayload] = await Promise.all([
        services.structuredLightingApi.getRuntime(selectedSessionId),
        services.structuredLightingApi.listCaptures(selectedSessionId),
      ]);
      setRuntime(asRecord(runtimePayload));
      setCaptures(asArray(capturesPayload));
    } catch {
      setRuntime(null);
      setCaptures([]);
    }
  }, [options.appMode, selectedSessionId, services]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    void refreshSessionDetails();
  }, [refreshSessionDetails]);

  const runAction = useCallback(
    async (handler: () => Promise<unknown>, successMessage: string) => {
      if (options.appMode !== 'remote') {
        setError('Structured lighting is remote-only in this mobile slice.');
        return;
      }

      setActionLoading(true);
      setError(null);
      setActionMessage(null);
      try {
        await handler();
        setActionMessage(successMessage);
        await refresh();
        await refreshSessionDetails();
      } catch (actionError) {
        setError(actionError instanceof Error ? actionError.message : 'Structured lighting action failed.');
      } finally {
        setActionLoading(false);
      }
    },
    [options.appMode, refresh, refreshSessionDetails],
  );

  const createSession = useCallback(async () => {
    await runAction(
      () =>
        services.structuredLightingApi.createSession({
          name: form.name,
          projector_device_id: form.projector_device_id,
          camera_index: Number(form.camera_index || 1),
          projector_width: Number(form.projector_width || 1280),
          projector_height: Number(form.projector_height || 720),
          presentation_mode: form.presentation_mode,
          hold_ms: Number(form.hold_ms || 1200),
          notes: form.notes,
        }),
      'Structured lighting session created.',
    );
  }, [form, runAction, services]);

  const startSession = useCallback(
    async (sessionId: string) => {
      await runAction(
        () => services.structuredLightingApi.startSession(sessionId),
        `Structured lighting session ${sessionId} started.`,
      );
    },
    [runAction, services],
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      await runAction(
        () => services.structuredLightingApi.deleteSession(sessionId),
        `Structured lighting session ${sessionId} deleted.`,
      );
      setSelectedSessionId((current) => (current === sessionId ? '' : current));
    },
    [runAction, services],
  );

  const updateForm = useCallback((key: string, value: string) => {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }, []);

  const selectSession = useCallback((sessionId: string) => {
    setSelectedSessionId(sessionId);
  }, []);

  return {
    actionLoading,
    actionMessage,
    capabilities,
    captures,
    createSession,
    deleteSession,
    error,
    form,
    loading,
    projectors,
    refresh,
    runtime,
    selectedSessionId,
    selectSession,
    sessions,
    startSession,
    status,
    updateForm,
  };
}
