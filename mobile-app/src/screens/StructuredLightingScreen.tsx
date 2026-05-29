import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { StructuredLightingCamera } from '../components/StructuredLightingCamera';
import { useStructuredLightingCaptureController } from '../features/lighting/useStructuredLightingCaptureController';
import { useStructuredLightingController } from '../features/lighting/useStructuredLightingController';
import type { AppMode } from '../control-plane/localState';
import { colors } from '../theme';
import type { JsonRecord } from '../types/api';

interface StructuredLightingScreenProps {
  apiBaseUrl: string;
  appMode: AppMode;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function describeProjector(projector: JsonRecord): string {
  return String(projector.name ?? projector.friendly_name ?? projector.device_id ?? projector.id ?? 'Projector');
}

function describeSession(session: JsonRecord): string {
  return String(session.name ?? session.session_id ?? 'Structured lighting session');
}

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

export function StructuredLightingScreen({
  apiBaseUrl,
  appMode,
}: StructuredLightingScreenProps) {
  const {
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
  } = useStructuredLightingController({ apiBaseUrl, appMode });
  const captureController = useStructuredLightingCaptureController({
    apiBaseUrl,
    appMode,
    captures,
    selectedSessionId,
    onRefreshSession: refresh,
  });
  const worker = asRecord(status?.worker);
  const runtimeSession = asRecord(runtime?.session);
  const currentStep = asRecord(runtime?.current_step);

  if (appMode === 'local') {
    return (
      <Panel
        title="Structured lighting"
        subtitle="This workflow remains remote-only for now because it depends on backend worker/runtime orchestration and projector/camera coordination."
      >
        <Text style={styles.noteText}>
          Switch to remote mode to inspect sessions, worker status, and run structured-lighting actions against the existing FastAPI backend.
        </Text>
      </Panel>
    );
  }

  return (
    <>
      <Panel
        title="Structured lighting"
        subtitle="Mobile now surfaces a compact operator console for the backend structured-lighting workflow."
      >
        <View style={styles.actionsRow}>
          <ActionButton
            label={loading ? 'Refreshing...' : 'Refresh'}
            onPress={() => void refresh()}
            disabled={loading}
          />
          <ActionButton
            label={actionLoading ? 'Working...' : 'Create session'}
            onPress={() => void createSession()}
            disabled={actionLoading}
            variant="secondary"
          />
        </View>
        <View style={styles.metricGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{String(sessions.length)}</Text>
            <Text style={styles.metricLabel}>Sessions</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{String(projectors.length)}</Text>
            <Text style={styles.metricLabel}>Projectors</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>
              {formatValue(worker?.status ?? status?.status, 'unknown')}
            </Text>
            <Text style={styles.metricLabel}>Worker status</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{String(captures.length)}</Text>
            <Text style={styles.metricLabel}>Captures</Text>
          </View>
        </View>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Session creation"
        subtitle="Create a calibration session using the remote service code already ported into the mobile app."
      >
        <View style={styles.fieldGroup}>
          <Text style={styles.fieldLabel}>Session name</Text>
          <TextInput
            onChangeText={(value) => updateForm('name', value)}
            style={styles.input}
            value={form.name}
          />
        </View>
        <View style={styles.fieldGroup}>
          <Text style={styles.fieldLabel}>Projector device ID</Text>
          <TextInput
            onChangeText={(value) => updateForm('projector_device_id', value)}
            placeholder={projectors[0] ? describeProjector(projectors[0]) : 'dlna-projector-id'}
            placeholderTextColor={colors.mutedText}
            style={styles.input}
            value={form.projector_device_id}
          />
          {projectors.length > 0 ? (
            <Text style={styles.noteText}>
              Available: {projectors.slice(0, 3).map(describeProjector).join(' • ')}
            </Text>
          ) : null}
        </View>
        <View style={styles.fieldGroup}>
          <Text style={styles.fieldLabel}>Presentation mode</Text>
          <TextInput
            onChangeText={(value) => updateForm('presentation_mode', value)}
            style={styles.input}
            value={form.presentation_mode}
          />
        </View>
        <View style={styles.row}>
          <View style={styles.halfField}>
            <Text style={styles.fieldLabel}>Camera index</Text>
            <TextInput
              keyboardType="numeric"
              onChangeText={(value) => updateForm('camera_index', value)}
              style={styles.input}
              value={form.camera_index}
            />
          </View>
          <View style={styles.halfField}>
            <Text style={styles.fieldLabel}>Hold ms</Text>
            <TextInput
              keyboardType="numeric"
              onChangeText={(value) => updateForm('hold_ms', value)}
              style={styles.input}
              value={form.hold_ms}
            />
          </View>
        </View>
      </Panel>

      <Panel
        title="Session inventory"
        subtitle="Select a session to inspect runtime state and trigger start/delete actions."
      >
        {sessions.length === 0 ? (
          <Text style={styles.emptyText}>No structured-lighting sessions available yet.</Text>
        ) : null}
        {sessions.map((session) => {
          const sessionId = String(session.session_id ?? '');
          const selected = sessionId === selectedSessionId;
          return (
            <Pressable
              key={sessionId || describeSession(session)}
              accessibilityRole="button"
              onPress={() => selectSession(sessionId)}
              style={[styles.selectionCard, selected && styles.selectionCardActive]}
            >
              <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                {describeSession(session)}
              </Text>
              <Text style={styles.detailText}>
                Status: {formatValue(session.status)} • Mode: {formatValue(session.presentation_mode)}
              </Text>
              <Text style={styles.detailText}>
                Projector: {formatValue(session.projector_device_id)}
              </Text>
              {sessionId ? (
                <View style={styles.actionsRow}>
                  <ActionButton
                    label={
                      actionLoading && selected ? 'Working...' : 'Start session'
                    }
                    onPress={() => void startSession(sessionId)}
                    disabled={actionLoading}
                    variant="secondary"
                  />
                  <ActionButton
                    label={actionLoading && selected ? 'Working...' : 'Delete'}
                    onPress={() => void deleteSession(sessionId)}
                    disabled={actionLoading}
                    variant="secondary"
                  />
                </View>
              ) : null}
            </Pressable>
          );
        })}
      </Panel>

      <Panel
        title="Selected session runtime"
        subtitle="A compact mobile view of runtime worker/session detail and capture progress."
      >
        {runtime ? (
          <>
            <Text style={styles.detailText}>
              Session status: {formatValue(runtimeSession?.status)}
            </Text>
            <Text style={styles.detailText}>
              Current step: {formatValue(currentStep?.index)}
            </Text>
            <Text style={styles.detailText}>
              Decode status: {formatValue(asRecord(runtimeSession?.decode)?.status)}
            </Text>
            <Text style={styles.detailText}>
              Worker: {formatValue(worker?.worker_id)} • Last heartbeat:{' '}
              {formatValue(worker?.last_heartbeat_at)}
            </Text>
          </>
        ) : (
          <Text style={styles.emptyText}>Select a session to inspect runtime data.</Text>
        )}
        <Text style={styles.sectionTitle}>Capture count</Text>
        <Text style={styles.detailText}>{String(captures.length)} capture records loaded.</Text>
        <View style={styles.actionsRow}>
          <ActionButton
            label={captureController.loading ? 'Loading plan...' : 'Load capture plan'}
            onPress={() => void captureController.loadCapturePlan()}
            disabled={!selectedSessionId || captureController.loading}
            variant="secondary"
          />
          <ActionButton
            label={captureController.working ? 'Working...' : 'Decode'}
            onPress={() => void captureController.decodeSession()}
            disabled={!selectedSessionId || captureController.working}
            variant="secondary"
          />
          <ActionButton
            label={captureController.working ? 'Working...' : 'Publish mapping'}
            onPress={() => void captureController.publishMappingScene()}
            disabled={!selectedSessionId || captureController.working}
            variant="secondary"
          />
        </View>
        {captureController.error ? (
          <Text style={styles.errorText}>{captureController.error}</Text>
        ) : null}
        {captureController.captureState ? (
          <>
            <Text style={styles.sectionTitle}>Capture plan</Text>
            {captureController.captureState.steps.length === 0 ? (
              <Text style={styles.emptyText}>Capture plan has no steps.</Text>
            ) : null}
            {captureController.captureState.steps.map((step) => (
              <View key={step.index} style={styles.captureStepRow}>
                <Text style={styles.detailText}>
                  Step {step.index}: {step.label} • {step.status}
                </Text>
                {step.error ? <Text style={styles.errorText}>{step.error}</Text> : null}
              </View>
            ))}
            <StructuredLightingCamera
              disabled={captureController.working}
              onUploadStep={(stepIndex, uri) =>
                void captureController.uploadStepFile(stepIndex, { uri })
              }
              selectedSessionId={selectedSessionId}
              selectedStepIndex={captureController.currentStepIndex}
              steps={captureController.captureState.steps}
            />
          </>
        ) : (
          <Text style={styles.emptyText}>Load the capture plan to upload mobile captures.</Text>
        )}
      </Panel>

      <Panel
        title="Capability snapshot"
        subtitle="Capabilities and health are exposed through the ported structured-lighting service module."
      >
        <Text style={styles.detailText}>
          Capability keys: {capabilities ? Object.keys(capabilities).join(' • ') : 'none returned'}
        </Text>
        <Text style={styles.detailText}>
          Status keys: {status ? Object.keys(status).join(' • ') : 'none returned'}
        </Text>
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricCard: {
    minWidth: 100,
    flexGrow: 1,
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    gap: 4,
  },
  metricValue: {
    color: colors.accent,
    fontSize: 20,
    fontWeight: '700',
  },
  metricLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: '600',
  },
  noteText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  successText: {
    color: colors.success,
    fontSize: 13,
    lineHeight: 18,
  },
  errorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 18,
  },
  fieldGroup: {
    gap: 8,
  },
  fieldLabel: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
  },
  input: {
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    color: colors.text,
    fontSize: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  halfField: {
    minWidth: 120,
    flexGrow: 1,
    gap: 8,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  selectionCard: {
    gap: 6,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.elevatedPanel,
  },
  selectionCardActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  selectionTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  selectionTitleActive: {
    color: colors.accent,
  },
  detailText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  captureStepRow: {
    gap: 4,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 10,
    backgroundColor: colors.elevatedPanel,
  },
});
