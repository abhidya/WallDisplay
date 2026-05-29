import { useCallback, useMemo, useState } from 'react';

import { createControlPlaneClient } from '../../control-plane/client.ts';
import type { AppMode } from '../../control-plane/localState.ts';
import type { JsonRecord } from '../../types/api.ts';
import {
  buildStructuredLightingCaptureFormData,
  markStepCaptured,
  markStepFailed,
  markStepUploaded,
  normalizeCapturePlan,
  type StructuredLightingCaptureFile,
  type StructuredLightingCaptureState,
} from './structuredLightingCapture.ts';

interface UseStructuredLightingCaptureControllerOptions {
  apiBaseUrl: string;
  appMode: AppMode;
  captures: JsonRecord[];
  selectedSessionId: string;
  onRefreshSession?: () => Promise<void>;
}

export interface StructuredLightingCaptureController {
  captureState: StructuredLightingCaptureState | null;
  currentStepIndex?: number;
  decodeSession: () => Promise<void>;
  error: string | null;
  loadCapturePlan: () => Promise<void>;
  loading: boolean;
  publishMappingScene: () => Promise<void>;
  recordCapturedFrame: (stepIndex: number, localUri: string) => void;
  resetError: () => void;
  uploadStepFile: (stepIndex: number, file: StructuredLightingCaptureFile) => Promise<void>;
  working: boolean;
}

export function useStructuredLightingCaptureController(
  options: UseStructuredLightingCaptureControllerOptions,
): StructuredLightingCaptureController {
  const { apiBaseUrl, appMode, captures, onRefreshSession, selectedSessionId } = options;
  const client = useMemo(
    () => createControlPlaneClient(appMode, apiBaseUrl),
    [apiBaseUrl, appMode],
  );
  const [captureState, setCaptureState] = useState<StructuredLightingCaptureState | null>(null);
  const [loading, setLoading] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCapturePlan = useCallback(async () => {
    if (appMode !== 'remote' || !selectedSessionId) {
      setCaptureState(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = await client.getStructuredLightingCapturePlan(selectedSessionId);
      setCaptureState(normalizeCapturePlan(selectedSessionId, payload, captures));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load capture plan.');
    } finally {
      setLoading(false);
    }
  }, [appMode, captures, client, selectedSessionId]);

  const recordCapturedFrame = useCallback((stepIndex: number, localUri: string) => {
    setCaptureState((current) => (current ? markStepCaptured(current, stepIndex, localUri) : current));
  }, []);

  const uploadStepFile = useCallback(
    async (stepIndex: number, file: StructuredLightingCaptureFile) => {
      if (appMode !== 'remote' || !selectedSessionId) {
        setError('Structured lighting capture upload is remote-only.');
        return;
      }

      setWorking(true);
      setError(null);
      setCaptureState((current) => (current ? markStepCaptured(current, stepIndex, file.uri) : current));
      try {
        await client.uploadStructuredLightingCapture(
          selectedSessionId,
          buildStructuredLightingCaptureFormData(stepIndex, file),
        );
        setCaptureState((current) => (current ? markStepUploaded(current, stepIndex) : current));
        await onRefreshSession?.();
      } catch (uploadError) {
        const message = uploadError instanceof Error ? uploadError.message : 'Capture upload failed.';
        setError(message);
        setCaptureState((current) => (current ? markStepFailed(current, stepIndex, message) : current));
      } finally {
        setWorking(false);
      }
    },
    [appMode, client, onRefreshSession, selectedSessionId],
  );

  const runSessionAction = useCallback(
    async (handler: () => Promise<JsonRecord>, fallback: string) => {
      if (appMode !== 'remote' || !selectedSessionId) {
        setError('Select a remote structured-lighting session first.');
        return;
      }
      setWorking(true);
      setError(null);
      try {
        await handler();
        await onRefreshSession?.();
      } catch (actionError) {
        setError(actionError instanceof Error ? actionError.message : fallback);
      } finally {
        setWorking(false);
      }
    },
    [appMode, onRefreshSession, selectedSessionId],
  );

  const decodeSession = useCallback(
    () => runSessionAction(
      () => client.decodeStructuredLightingSession(selectedSessionId, {}),
      'Decode failed.',
    ),
    [client, runSessionAction, selectedSessionId],
  );

  const publishMappingScene = useCallback(
    () => runSessionAction(
      () => client.publishStructuredLightingMappingScene(selectedSessionId, {}),
      'Publish mapping scene failed.',
    ),
    [client, runSessionAction, selectedSessionId],
  );

  return {
    captureState,
    currentStepIndex: captureState?.currentStepIndex,
    decodeSession,
    error,
    loadCapturePlan,
    loading,
    publishMappingScene,
    recordCapturedFrame,
    resetError: () => setError(null),
    uploadStepFile,
    working,
  };
}
