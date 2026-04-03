import { StyleSheet, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { emulatorConnectionNotes } from '../data/features';
import { useSettingsController } from '../features/settings/useSettingsController';
import { NanoDlnaApiClient } from '../services/api';
import { colors } from '../theme';

interface SettingsScreenProps {
  apiBaseUrl: string;
  client: NanoDlnaApiClient;
  onApplyApiBaseUrl: (value: string) => void;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

export function SettingsScreen({
  apiBaseUrl,
  client,
  onApplyApiBaseUrl,
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
  } = useSettingsController(client, { apiBaseUrl });

  return (
    <>
      <Panel
        title="Backend connection"
        subtitle="Set the FastAPI base URL used by the mobile rewrite. The app always normalizes the value to an /api endpoint."
      >
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          onChangeText={setDraftValue}
          placeholder="http://127.0.0.1:8000/api"
          placeholderTextColor={colors.mutedText}
          style={styles.input}
          value={draftValue}
        />
        <Text style={styles.normalizedLabel}>Normalized: {normalized}</Text>
        <View style={styles.actionsRow}>
          <ActionButton label="Apply base URL" onPress={() => onApplyApiBaseUrl(draftValue)} />
          <ActionButton
            label={loading ? 'Checking...' : 'Test connection'}
            onPress={() => void refreshConnection()}
            disabled={loading}
            variant="secondary"
          />
        </View>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Connection diagnostics"
        subtitle="Use the current mobile API target to confirm backend health and unified discovery status before running device or operations workflows."
      >
        <View style={styles.metricGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(health?.status, 'unknown')}</Text>
            <Text style={styles.metricLabel}>Health</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>
              {formatValue(unifiedDiscovery?.discovery_running)}
            </Text>
            <Text style={styles.metricLabel}>Discovery running</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>
              {formatValue(unifiedDiscovery?.online_devices)}
            </Text>
            <Text style={styles.metricLabel}>Online devices</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>
              {formatValue(unifiedDiscovery?.active_sessions)}
            </Text>
            <Text style={styles.metricLabel}>Discovery sessions</Text>
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
        subtitle="These defaults matter because localhost behaves differently on simulator, emulator, and physical hardware."
      >
        {emulatorConnectionNotes.map((note) => (
          <View key={note} style={styles.noteRow}>
            <View style={styles.noteDot} />
            <Text style={styles.noteText}>{note}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="OMX team kickoff"
        subtitle="Use the installed oh-my-codex runtime to continue the rewrite with a durable coordinated team."
      >
        <Text style={styles.commandText}>
          omx team 3:executor "Continue the nano-dlna mobile rewrite in mobile-app using the
          existing FastAPI endpoints as the control plane."
        </Text>
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
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
