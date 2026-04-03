import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { emulatorConnectionNotes } from '../data/features';
import { useSettingsController } from '../features/settings/useSettingsController';
import type { ControlPlaneClient } from '../control-plane/client';
import type { AppMode } from '../control-plane/localState';
import { colors } from '../theme';

interface SettingsScreenProps {
  apiBaseUrl: string;
  appMode: AppMode;
  client: ControlPlaneClient;
  hydrated: boolean;
  onApplyApiBaseUrl: (value: string) => void;
  onApplyAppMode: (mode: AppMode) => void;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

export function SettingsScreen({
  apiBaseUrl,
  appMode,
  client,
  hydrated,
  onApplyApiBaseUrl,
  onApplyAppMode,
}: SettingsScreenProps) {
  const {
    actionMessage,
    draftValue,
    error,
    health,
    loading,
    normalized,
    refreshConnection,
    setDraftValue,
    unifiedDiscovery,
  } = useSettingsController(client, { apiBaseUrl, appMode });

  return (
    <>
      <Panel
        title="Control-plane mode"
        subtitle="Local mode keeps the app useful with no backend. Remote mode preserves the existing FastAPI adapter for fallback and migration."
      >
        <View style={styles.modeRow}>
          {(['local', 'remote'] as AppMode[]).map((mode) => {
            const active = mode === appMode;
            return (
              <Pressable
                key={mode}
                accessibilityRole="button"
                onPress={() => onApplyAppMode(mode)}
                style={[styles.modeCard, active && styles.modeCardActive]}
              >
                <Text style={[styles.modeTitle, active && styles.modeTitleActive]}>{mode}</Text>
                <Text style={styles.modeBody}>
                  {mode === 'local'
                    ? 'On-device control plane, saved config, local-safe workflows, and no backend requirement.'
                    : 'Use the existing FastAPI control plane through the migration adapter.'}
                </Text>
              </Pressable>
            );
          })}
        </View>
        {!hydrated ? <Text style={styles.noteText}>Restoring saved control-plane preferences…</Text> : null}
      </Panel>

      <Panel
        title="Remote fallback target"
        subtitle="Keep the backend URL ready for remote mode. The app normalizes the value to an /api endpoint."
      >
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          onChangeText={setDraftValue}
          placeholder="http://127.0.0.1:8000/api"
          placeholderTextColor={colors.mutedText}
          returnKeyType="done"
          style={styles.input}
          value={draftValue}
        />
        <Text style={styles.normalizedLabel}>Normalized: {normalized}</Text>
        <View style={styles.actionsRow}>
          <ActionButton label="Apply base URL" onPress={() => onApplyApiBaseUrl(draftValue)} />
          <ActionButton
            label={loading ? 'Checking...' : appMode === 'local' ? 'Check local mode' : 'Test remote mode'}
            onPress={() => void refreshConnection()}
            disabled={loading}
            variant="secondary"
          />
        </View>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Control-plane diagnostics"
        subtitle="Use the active mode to confirm local readiness or remote connectivity before running device, media, or operations workflows."
      >
        <View style={styles.metricGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(health?.status, 'unknown')}</Text>
            <Text style={styles.metricLabel}>Health</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(appMode)}</Text>
            <Text style={styles.metricLabel}>Mode</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(unifiedDiscovery?.online_devices)}</Text>
            <Text style={styles.metricLabel}>Devices</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(unifiedDiscovery?.active_sessions)}</Text>
            <Text style={styles.metricLabel}>Sessions</Text>
          </View>
        </View>
        <Text style={styles.noteText}>
          Registered backends:{' '}
          {formatValue(
            unifiedDiscovery?.backends ? Object.keys(unifiedDiscovery.backends).length : 0,
          )}
        </Text>
      </Panel>

      <Panel
        title="Connection notes"
        subtitle="Remote fallback still matters because simulator, emulator, and physical hardware resolve localhost differently."
      >
        {emulatorConnectionNotes.map((note) => (
          <View key={note} style={styles.noteRow}>
            <View style={styles.noteDot} />
            <Text style={styles.noteText}>{note}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Execution lane"
        subtitle="This iteration follows the approved local-first plan: shared seam, local persistence, reduced operations subset, and deferred advanced receiver/rendering features."
      >
        <Text style={styles.commandText}>Source of truth: .omx/plans/prd-local-control-plane-mobile-rewrite.md</Text>
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  modeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  modeCard: {
    minWidth: 180,
    flexGrow: 1,
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    gap: 6,
  },
  modeCardActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  modeTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    textTransform: 'capitalize',
  },
  modeTitleActive: {
    color: colors.accent,
  },
  modeBody: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
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
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  normalizedLabel: {
    color: colors.accent,
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
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricCard: {
    minWidth: 110,
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
    textTransform: 'capitalize',
  },
  metricLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: '600',
  },
  noteRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
  },
  noteDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: colors.accent,
    marginTop: 6,
  },
  noteText: {
    flex: 1,
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  commandText: {
    color: colors.text,
    fontFamily: 'Courier',
    fontSize: 13,
    lineHeight: 20,
  },
});
